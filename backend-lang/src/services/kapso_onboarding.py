"""
Onboarding Kapso (P2): cliente de Platform API + servicio que enlaza workspace ↔ customer Kapso.

Rutas/esquemas verificados contra openapi-platform.yaml (POST /customers, POST
/customers/{id}/setup_links). El transporte HTTP se inyecta para probar sin red.
Principio XI: la API key y la URL del setup link no se registran en logs.
"""
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)


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

    async def _post(self, path: str, body: dict) -> dict:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as c:
                resp = await c.post(
                    self._base + path, json=body, headers={"X-API-Key": self._api_key}
                )
        except httpx.HTTPError as e:
            raise KapsoError(f"network_error:{type(e).__name__}") from None
        if resp.status_code >= 400:
            raise KapsoError(f"http_{resp.status_code}")
        return resp.json()["data"]

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


class KapsoOnboardingService:
    def __init__(self, client: KapsoPlatformClient, frontend_url: str):
        self._client = client
        self._frontend = frontend_url.rstrip("/")

    async def create_onboarding_link(self, db, workspace_id: str) -> dict:
        """Crea (o reutiliza) el customer Kapso del workspace y genera un setup link nuevo."""
        customer_id = await db.fetchval(
            "SELECT kapso_customer_id FROM kapso_customers WHERE workspace_id = $1", workspace_id
        )
        if not customer_id:
            name = await db.fetchval("SELECT name FROM workspaces WHERE id = $1", workspace_id)
            if not name:
                raise LookupError("workspace")
            # shortcut: sin recuperar por external_customer_id si dos requests crean a la vez; usar GET /customers?external_customer_id= si pasa.
            customer_id = (await self._client.create_customer(
                name=name, external_customer_id=workspace_id))["id"]
            await db.execute(
                "INSERT INTO kapso_customers (workspace_id, kapso_customer_id) VALUES ($1, $2) "
                "ON CONFLICT (workspace_id) DO NOTHING",
                workspace_id, customer_id,
            )
        parts = urlparse(self._frontend)
        link = await self._client.create_setup_link(
            customer_id,
            success_redirect_url=f"{self._frontend}/settings?kapso=success",
            failure_redirect_url=f"{self._frontend}/settings?kapso=failed",
            allowed_origins=[f"{parts.scheme}://{parts.netloc}"],
        )
        expires = link.get("expires_at")
        await db.execute(
            "UPDATE kapso_customers SET setup_link_id=$2, setup_link_url=$3, "
            "setup_link_expires_at=$4, setup_status='pending', updated_at=now() "
            "WHERE workspace_id=$1",
            workspace_id, link["id"], link["url"],
            datetime.fromisoformat(expires.replace("Z", "+00:00")) if expires else None,
        )
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
        workspace_id = await db.fetchval(
            "SELECT workspace_id FROM kapso_customers WHERE kapso_customer_id = $1", customer_id
        ) if customer_id else None
        if not workspace_id and item.get("external_customer_id"):
            workspace_id = await db.fetchval(
                "SELECT workspace_id FROM kapso_customers WHERE workspace_id::text = $1",
                str(item["external_customer_id"]),
            )
        if not workspace_id:
            log.error("[kapso/onboarding] customer desconocido para phone_number_id=%s", pid)
            return False
        phone = item.get("phone_number") or item.get("display_phone_number") or str(pid)
        conn_type = item.get("connection_type") or "coexistence"
        row = await db.fetchrow(
            """
            INSERT INTO channels (workspace_id, channel_type, provider, phone_number,
                phone_number_id, display_name, status, coexistence_enabled, connection_type)
            VALUES ($1, 'whatsapp', 'kapso', $2, $3, $2, 'active', $4, $5)
            ON CONFLICT (phone_number_id) DO UPDATE SET phone_number = EXCLUDED.phone_number,
                connection_type = EXCLUDED.connection_type, status = 'active', updated_at = now()
            WHERE channels.workspace_id = EXCLUDED.workspace_id
            RETURNING id
            """,
            workspace_id, phone, str(pid), conn_type != "dedicated", conn_type,
        )
        if row is None:
            log.error("[kapso/onboarding] número ya asociado a otro workspace | phone_number_id=%s | workspace=%s",
                      pid, workspace_id)
            return False
        await db.execute(
            "UPDATE kapso_customers SET setup_status='connected', updated_at=now() WHERE workspace_id=$1",
            workspace_id,
        )
        log.info("[kapso/onboarding] canal enlazado | workspace=%s | phone_number_id=%s", workspace_id, pid)
        return True
