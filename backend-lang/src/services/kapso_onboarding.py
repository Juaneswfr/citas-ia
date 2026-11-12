"""
Onboarding Kapso (P2): cliente de Platform API + servicio que enlaza workspace ↔ customer Kapso.

Rutas/esquemas verificados contra openapi-platform.yaml (POST /customers, POST
/customers/{id}/setup_links). El transporte HTTP se inyecta para probar sin red.
Principio XI: la API key y la URL del setup link no se registran en logs.
"""
import logging
import secrets
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import text

log = logging.getLogger(__name__)


# Eventos del webhook de cada número. "sent" trae lo que el negocio responde desde la app de
# WhatsApp Business (coexistencia). Los números conectados antes de agregar un evento se ponen al
# día con sync_kapso_webhooks.py.
NUMBER_WEBHOOK_EVENTS = ["whatsapp.message.received", "whatsapp.message.sent"]


class KapsoError(Exception):
    """Error de la Platform API; el mensaje solo lleva el código HTTP, nunca cuerpos ni claves."""


class KapsoPlatformClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.kapso.ai",
        transport: Optional[httpx.AsyncBaseTransport] = None,
        timeout: float = 10.0,
    ):
        self._api_key = api_key
        self._base = base_url.rstrip("/") + "/platform/v1"
        self._transport = transport
        self._timeout = timeout

    async def _request(self, method: str, path: str, body: Optional[dict] = None):
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as c:
                resp = await c.request(
                    method, self._base + path, json=body, headers={"X-API-Key": self._api_key}
                )
        except httpx.HTTPError as e:
            raise KapsoError(f"network_error:{type(e).__name__}") from None
        if resp.status_code >= 400:
            raise KapsoError(f"http_{resp.status_code}")
        return resp

    async def _post(self, path: str, body: dict) -> dict:
        return (await self._request("POST", path, body)).json()["data"]

    async def create_phone_number_webhook(
        self, phone_number_id: str, *, url: str, secret_key: str, events: list[str]
    ) -> dict:
        return await self._post(
            f"/whatsapp/phone_numbers/{phone_number_id}/webhooks",
            {"whatsapp_webhook": {
                "url": url, "secret_key": secret_key, "events": events,
                "kind": "kapso", "payload_version": "v2", "active": True,
            }},
        )

    async def update_phone_number_webhook(
        self, phone_number_id: str, webhook_id: str, *, events: list[str]
    ) -> None:
        """Cambia los eventos de un webhook ya creado (PATCH .../webhooks/{id}, docs.kapso.ai)."""
        await self._request(
            "PATCH", f"/whatsapp/phone_numbers/{phone_number_id}/webhooks/{webhook_id}",
            {"whatsapp_webhook": {"events": events}},
        )

    async def delete_phone_number_webhook(self, phone_number_id: str, webhook_id: str) -> None:
        await self._request(
            "DELETE", f"/whatsapp/phone_numbers/{phone_number_id}/webhooks/{webhook_id}"
        )

    async def get_phone_number(self, phone_number_id: str) -> dict:
        """Estado del número en Kapso: `business_account_id`, `is_coexistence`, `status` (docs.kapso.ai).

        GET /whatsapp/phone_numbers/{phone_number_id} → data. Un número que ya no existe da
        KapsoError("http_404"). Respuesta sin `data` → {}.
        """
        resp = await self._request("GET", f"/whatsapp/phone_numbers/{phone_number_id}")
        try:
            data = resp.json().get("data")
        except (ValueError, AttributeError):
            return {}
        return data if isinstance(data, dict) else {}

    async def get_business_account_id(self, phone_number_id: str) -> Optional[str]:
        """ID de la cuenta de WhatsApp (WABA) dueña del número; las plantillas viven en ella."""
        value = (await self.get_phone_number(phone_number_id)).get("business_account_id")
        return str(value) if value else None

    async def create_customer(self, *, name: str, external_customer_id: str) -> dict:
        return await self._post(
            "/customers",
            {"customer": {"name": name, "external_customer_id": external_customer_id}},
        )

    async def create_setup_link(
        self, customer_id: str, *, success_redirect_url: str, failure_redirect_url: str,
        allowed_origins: list[str],
    ) -> dict:
        return await self._post(
            f"/customers/{customer_id}/setup_links",
            {"setup_link": {
                "success_redirect_url": success_redirect_url,
                "failure_redirect_url": failure_redirect_url,
                "allowed_origins": allowed_origins,
                "allowed_connection_types": ["coexistence"],
                "meta_billing_mode": "partner_managed",
            }},
        )


class KapsoSandboxClient:
    """Client for https://app.kapso.ai/api/v1 — sandbox sessions."""

    def __init__(self, api_key: str, base_url: str = "https://app.kapso.ai/api/v1"):
        self._api_key = api_key
        self._base = base_url.rstrip("/")

    async def _request(self, method: str, path: str, body: Optional[dict] = None):
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.request(
                    method, self._base + path, json=body,
                    headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
                )
        except httpx.HTTPError as e:
            raise KapsoError(f"network_error:{type(e).__name__}") from None
        if resp.status_code >= 400:
            raise KapsoError(f"http_{resp.status_code}")
        return resp.json()

    async def create_session(self, phone_number: str) -> dict:
        return await self._request("POST", "/sandbox_sessions", {
            "whatsapp_sandbox_session": {"phone_number": phone_number},
        })

    async def list_sessions(self) -> list:
        return await self._request("GET", "/sandbox_sessions")

    async def get_session(self, session_id: str) -> dict:
        return await self._request("GET", f"/sandbox_sessions/{session_id}")


class KapsoOnboardingService:
    def __init__(self, client: KapsoPlatformClient, frontend_url: str):
        self._client = client
        self._frontend = frontend_url.rstrip("/")

    async def create_onboarding_link(self, db, workspace_id: str) -> dict:
        """Crea (o reutiliza) el customer Kapso del workspace y genera un setup link nuevo."""
        customer_id = (await db.execute(
            text("SELECT kapso_customer_id FROM kapso_customers WHERE workspace_id = :workspace_id"),
            {"workspace_id": workspace_id},
        )).scalar_one_or_none()
        if not customer_id:
            name = (await db.execute(
                text("SELECT name FROM workspaces WHERE id = :workspace_id"),
                {"workspace_id": workspace_id},
            )).scalar_one_or_none()
            if not name:
                raise LookupError("workspace")
            # shortcut: sin recuperar por external_customer_id si dos requests crean a la vez; usar GET /customers?external_customer_id= si pasa.
            customer_id = (await self._client.create_customer(
                name=name, external_customer_id=workspace_id))["id"]
            await db.execute(
                text(
                    "INSERT INTO kapso_customers (workspace_id, kapso_customer_id) VALUES (:workspace_id, :customer_id) "
                    "ON CONFLICT (workspace_id) DO NOTHING"
                ),
                {"workspace_id": workspace_id, "customer_id": customer_id},
            )
            await db.commit()
        parts = urlparse(self._frontend)
        link = await self._client.create_setup_link(
            customer_id,
            success_redirect_url=f"{self._frontend}/settings?kapso=success",
            failure_redirect_url=f"{self._frontend}/settings?kapso=failed",
            allowed_origins=[f"{parts.scheme}://{parts.netloc}"],
        )
        expires = link.get("expires_at")
        await db.execute(
            text(
                "UPDATE kapso_customers SET setup_link_id=:setup_link_id, setup_link_url=:setup_link_url, "
                "setup_link_expires_at=:expires, setup_status='pending', updated_at=now() "
                "WHERE workspace_id=:workspace_id"
            ),
            {
                "workspace_id": workspace_id, "setup_link_id": link["id"], "setup_link_url": link["url"],
                "expires": datetime.fromisoformat(expires.replace("Z", "+00:00")) if expires else None,
            },
        )
        await db.commit()
        log.info("[kapso/onboarding] setup link creado | workspace=%s", workspace_id)
        return {"url": link["url"], "expires_at": expires}

    @staticmethod
    async def handle_phone_number_created(db, item: dict) -> bool:
        """Enlaza el número al workspace del customer. Idempotente; nunca reasigna un número ajeno.

        SUPUESTO (sin verificar): el esquema del payload no está en las specs; se asumen los campos
        phone_number_id, phone_number (o display_phone_number), customer_id | customer.id |
        external_customer_id (= workspace_id) y connection_type.
        """
        pid = item.get("phone_number_id")
        customer_id = item.get("customer_id") or (item.get("customer") or {}).get("id")
        if not pid:
            log.error("[kapso/onboarding] phone_number.created sin phone_number_id")
            return False
        workspace_id = (await db.execute(
            text("SELECT workspace_id FROM kapso_customers WHERE kapso_customer_id = :customer_id"),
            {"customer_id": customer_id},
        )).scalar_one_or_none() if customer_id else None
        if not workspace_id and item.get("external_customer_id"):
            workspace_id = (await db.execute(
                text("SELECT workspace_id FROM kapso_customers WHERE workspace_id::text = :ext_id"),
                {"ext_id": str(item["external_customer_id"])},
            )).scalar_one_or_none()
        if not workspace_id:
            log.error("[kapso/onboarding] customer desconocido para phone_number_id=%s", pid)
            return False
        phone = item.get("phone_number") or item.get("display_phone_number") or str(pid)
        conn_type = item.get("connection_type") or "coexistence"
        row = (await db.execute(
            text("""
            INSERT INTO channels (workspace_id, channel_type, provider, phone_number,
                phone_number_id, display_name, status, coexistence_enabled, connection_type)
            VALUES (:workspace_id, 'whatsapp', 'kapso', :phone, :pid, :phone, 'active', :coex, :conn_type)
            ON CONFLICT (phone_number_id) DO UPDATE SET phone_number = EXCLUDED.phone_number,
                connection_type = EXCLUDED.connection_type, status = 'active', updated_at = now()
            WHERE channels.workspace_id = EXCLUDED.workspace_id
            RETURNING id
            """),
            {
                "workspace_id": workspace_id, "phone": phone, "pid": str(pid),
                "coex": conn_type != "dedicated", "conn_type": conn_type,
            },
        )).scalar_one_or_none()
        if row is None:
            log.error("[kapso/onboarding] número ya asociado a otro workspace | phone_number_id=%s | workspace=%s",
                      pid, workspace_id)
            return False
        await db.execute(
            text("UPDATE kapso_customers SET setup_status='connected', updated_at=now() WHERE workspace_id=:workspace_id"),
            {"workspace_id": workspace_id},
        )
        await db.commit()
        log.info("[kapso/onboarding] canal enlazado | workspace=%s | phone_number_id=%s", workspace_id, pid)
        return True


def encrypt_secret(key: str, plain: str) -> str:
    return Fernet(key.encode()).encrypt(plain.encode()).decode()


def decrypt_secret(key: str, token: str) -> str:
    return Fernet(key.encode()).decrypt(token.encode()).decode()


async def provision_number_webhook(
    db, client: KapsoPlatformClient, *, phone_number_id: str, base_url: str, secrets_key: str
) -> bool:
    """Crea el webhook del número (una sola vez por canal). True si lo creó.

    Reclama el canal con un UPDATE condicional (webhook_token IS NULL) antes de llamar a Kapso,
    así dos eventos concurrentes no crean dos webhooks. Si Kapso falla, se libera el reclamo.
    """
    token, secret = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
    pid = str(phone_number_id)
    claimed = (await db.execute(
        text(
            "UPDATE channels SET webhook_token=:token, webhook_secret_encrypted=:secret, updated_at=now() "
            "WHERE phone_number_id=:pid AND webhook_token IS NULL RETURNING id"
        ),
        {"token": token, "secret": encrypt_secret(secrets_key, secret), "pid": pid},
    )).scalar_one_or_none()
    if claimed is None:
        return False
    await db.commit()
    try:
        wh = await client.create_phone_number_webhook(
            pid, url=f"{base_url.rstrip('/')}/webhooks/kapso/n/{token}", secret_key=secret,
            events=NUMBER_WEBHOOK_EVENTS,
        )
        await db.execute(
            text("UPDATE channels SET kapso_webhook_id=:webhook_id WHERE id=:claimed"),
            {"webhook_id": str(wh["id"]), "claimed": claimed},
        )
        await db.commit()
    except Exception as e:
        # shortcut: si Kapso creó el webhook pero falló el UPDATE queda huérfano; reconciliar con GET .../webhooks si pasa.
        await db.execute(
            text("UPDATE channels SET webhook_token=NULL, webhook_secret_encrypted=NULL WHERE id=:claimed"),
            {"claimed": claimed},
        )
        await db.commit()
        log.error("[kapso/webhook] no se pudo crear el webhook | phone_number_id=%s | err=%s",
                  pid, e if isinstance(e, KapsoError) else type(e).__name__)
        return False
    log.info("[kapso/webhook] webhook de número creado | phone_number_id=%s", pid)
    return True


async def deprovision_number_webhook(db, client: KapsoPlatformClient, *, phone_number_id: str) -> bool:
    """Borra el webhook del número en Kapso (404 = ya no existe) y limpia token/secreto del canal."""
    pid = str(phone_number_id)
    row = (await db.execute(
        text("SELECT id, kapso_webhook_id FROM channels WHERE phone_number_id=:pid"),
        {"pid": pid},
    )).mappings().fetchone()
    if row is None:
        return False
    if row["kapso_webhook_id"]:
        try:
            await client.delete_phone_number_webhook(pid, row["kapso_webhook_id"])
        except KapsoError as e:
            if str(e) != "http_404":
                log.error("[kapso/webhook] no se pudo borrar el webhook | phone_number_id=%s | err=%s", pid, e)
                return False
    await db.execute(
        text(
            "UPDATE channels SET webhook_token=NULL, kapso_webhook_id=NULL, "
            "webhook_secret_encrypted=NULL, updated_at=now() WHERE id=:channel_id"
        ),
        {"channel_id": row["id"]},
    )
    await db.commit()
    log.info("[kapso/webhook] webhook de número eliminado | phone_number_id=%s", pid)
    return True
