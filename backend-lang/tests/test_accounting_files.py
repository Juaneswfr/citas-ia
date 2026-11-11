"""Pruebas de comprobantes de pago: validación del archivo, seguridad de rutas y roles."""
import httpx
import pytest
from fastapi import FastAPI, HTTPException

from api.routes import accounting, accounting_files
from core.database import get_db
from core.security import get_current_user
from services import attachment_service
from services.attachment_service import MAX_BYTES, clean_filename, detect_content_type, resolve_path

pytestmark = pytest.mark.asyncio

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20
PDF = b"%PDF-1.7\n" + b"\x00" * 20


# ── Detección por contenido ───────────────────────────────────────────────────

@pytest.mark.parametrize("data,expected", [
    (JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp"), (PDF, "application/pdf"),
])
async def test_detects_allowed_types(data, expected):
    assert detect_content_type(data) == expected


@pytest.mark.parametrize("data", [
    b"<html><script>alert(1)</script></html>",
    b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>",
    b"MZ\x90\x00\x03",              # ejecutable de Windows
    b"GIF89a....",                   # formato no permitido
    b"RIFF\x00\x00\x00\x00WAVEfmt",  # RIFF pero no WebP
    b"",
])
async def test_rejects_other_types(data):
    assert detect_content_type(data) is None


# ── Nombres y rutas ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("recibo.pdf", "recibo.pdf"),
    ("../../etc/passwd", "passwd"),
    ("C:\\Users\\x\\foto.jpg", "foto.jpg"),
    ("a\x00b\x1f.png", "ab.png"),
    ("", "comprobante"),
    (None, "comprobante"),
])
async def test_clean_filename(raw, expected):
    assert clean_filename(raw) == expected


async def test_clean_filename_is_truncated():
    assert len(clean_filename("x" * 500 + ".jpg")) == 120


async def test_resolve_path_stays_inside_root(tmp_path, monkeypatch):
    monkeypatch.setattr(attachment_service, "_root", lambda: tmp_path.resolve())
    assert resolve_path("ws-1/abc.jpg") == (tmp_path / "ws-1" / "abc.jpg").resolve()
    for evil in ("../secreto.txt", "ws-1/../../secreto.txt", "/etc/passwd"):
        with pytest.raises(HTTPException) as err:
            resolve_path(evil)
        assert err.value.status_code == 400, evil


# ── Rutas ─────────────────────────────────────────────────────────────────────

class FailingDB:
    """Si la validación pasa y se llega a la BD, falla con 500; nunca con 4xx de validación."""

    async def execute(self, *a, **k):
        raise RuntimeError("db no disponible en la prueba")

    async def rollback(self):
        return None


def _app(role="manager", ws="ws-1") -> FastAPI:
    app = FastAPI()
    app.include_router(accounting.router)
    app.include_router(accounting_files.router)
    app.dependency_overrides[get_db] = lambda: FailingDB()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    return app


async def _call(app, method, path, **kwargs):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.request(method, path, **kwargs)


UPLOAD = "/workspaces/ws-1/accounting/movements/m-1/attachments"


async def test_upload_rejects_bad_files_before_touching_db():
    app = _app()
    html = await _call(app, "POST", UPLOAD, files={"file": ("x.jpg", b"<html></html>", "image/jpeg")})
    assert html.status_code == 415  # el Content-Type "image/jpeg" no engaña: se mira el contenido
    empty = await _call(app, "POST", UPLOAD, files={"file": ("x.pdf", b"", "application/pdf")})
    assert empty.status_code == 422
    big = await _call(app, "POST", UPLOAD, files={"file": ("x.pdf", PDF + b"0" * MAX_BYTES, "application/pdf")})
    assert big.status_code == 413
    missing = await _call(app, "POST", UPLOAD)
    assert missing.status_code == 422


async def test_valid_upload_reaches_the_database():
    resp = await _call(_app(), "POST", UPLOAD, files={"file": ("recibo.png", PNG, "image/png")})
    assert resp.status_code == 500  # pasó la validación y llegó a la BD de prueba, que falla


@pytest.mark.parametrize("role,ws,allowed", [
    ("manager", "ws-1", True), ("workspace_owner", "ws-1", True),
    ("staff", "ws-1", False), ("viewer", "ws-1", False), ("manager", "ws-2", False),
])
@pytest.mark.parametrize("method,path,kwargs", [
    ("POST", UPLOAD, {"files": {"file": ("r.png", PNG, "image/png")}}),
    ("GET", UPLOAD, {}),
    ("GET", "/workspaces/ws-1/accounting/attachments/a-1/file", {}),
    ("DELETE", "/workspaces/ws-1/accounting/attachments/a-1?confirmed=true", {}),
    ("GET", "/workspaces/ws-1/accounting/sales-orders/by-appointment/ap-1", {}),
])
async def test_attachment_routes_role_matrix(role, ws, allowed, method, path, kwargs):
    code = (await _call(_app(role, ws), method, path, **kwargs)).status_code
    assert (code != 403) == allowed, (role, ws, method, path, code)


async def test_delete_requires_confirmation():
    resp = await _call(_app(), "DELETE", "/workspaces/ws-1/accounting/attachments/a-1")
    assert resp.status_code == 422
