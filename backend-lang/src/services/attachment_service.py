"""Comprobantes de pago: archivos (JPG, PNG, WebP, PDF) adjuntos a un movimiento.

Seguridad (backend.md §2):
- El tipo se decide por los primeros bytes del archivo, nunca por el Content-Type ni la extensión que envía el cliente.
- En disco el archivo se llama <uuid>.<ext>; el nombre original solo se guarda como metadato (no toca rutas).
- Toda ruta resuelta debe quedar dentro de UPLOADS_DIR.
"""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings

log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
MAX_PER_MOVEMENT = 5
_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}
_COLUMNS = "id, movement_id, original_name, content_type, size_bytes, created_at"


def detect_content_type(data: bytes) -> Optional[str]:
    """Identifica el tipo real por la firma del archivo. None si no es uno de los permitidos."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def clean_filename(name: Optional[str]) -> str:
    """Nombre solo para mostrar: sin carpetas, sin caracteres de control, máx. 120 caracteres."""
    base = (name or "comprobante").replace("\\", "/").split("/")[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip()
    return (base or "comprobante")[:120]


def _root() -> Path:
    return Path(get_settings().uploads_dir).resolve()


def resolve_path(storage_key: str) -> Path:
    """Ruta absoluta de un archivo, garantizando que no salga de UPLOADS_DIR."""
    root = _root()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ruta de archivo inválida.")
    return path


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


async def store_file(workspace_id: str, data: bytes, content_type: str, folder: str = "") -> str:
    """Escribe un archivo ya validado bajo UPLOADS_DIR/<workspace>/[folder/]<uuid>.<ext> y devuelve su storage_key.

    `content_type` debe venir de detect_content_type (nunca del remitente); `folder` es un literal del código.
    """
    prefix = f"{workspace_id}/{folder}/" if folder else f"{workspace_id}/"
    storage_key = f"{prefix}{uuid.uuid4()}{_EXTENSIONS[content_type]}"
    await asyncio.to_thread(_write, resolve_path(storage_key), data)
    return storage_key


async def read_file(storage_key: str) -> bytes:
    """Contenido de un archivo guardado. FileNotFoundError si ya no está en disco."""
    return await asyncio.to_thread(resolve_path(storage_key).read_bytes)


def remove_file(storage_key: str) -> None:
    """Borra un archivo guardado (no falla si ya no existe)."""
    resolve_path(storage_key).unlink(missing_ok=True)


async def save_attachment(
    db: AsyncSession, workspace_id: str, movement_id: str, filename: Optional[str],
    data: bytes, user_id: Optional[str],
) -> dict:
    """Valida y guarda un comprobante en un movimiento no anulado del workspace."""
    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El archivo está vacío.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="El archivo supera 5 MB.")
    content_type = detect_content_type(data)
    if not content_type:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Formato no permitido. Usa JPG, PNG, WebP o PDF.")

    movement = (await db.execute(
        text("SELECT voided_at FROM movements WHERE id = :m AND workspace_id = :w FOR UPDATE"),
        {"m": movement_id, "w": workspace_id},
    )).mappings().fetchone()
    if not movement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimiento no encontrado.")
    if movement["voided_at"] is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El movimiento está anulado.")
    count = (await db.execute(
        text("SELECT COUNT(*) FROM movement_attachments WHERE movement_id = :m"), {"m": movement_id},
    )).scalar_one()
    if count >= MAX_PER_MOVEMENT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Máximo {MAX_PER_MOVEMENT} comprobantes por movimiento.")

    storage_key = f"{workspace_id}/{uuid.uuid4()}{_EXTENSIONS[content_type]}"
    path = resolve_path(storage_key)
    await asyncio.to_thread(_write, path, data)
    try:
        row = (await db.execute(
            text(f"""
                INSERT INTO movement_attachments (workspace_id, movement_id, original_name, content_type,
                                                  size_bytes, storage_key, uploaded_by)
                VALUES (:w, :m, :name, :ctype, :size, :key, :by) RETURNING {_COLUMNS}
            """),
            {"w": workspace_id, "m": movement_id, "name": clean_filename(filename), "ctype": content_type,
             "size": len(data), "key": storage_key, "by": user_id},
        )).mappings().one()
        await db.commit()
    except Exception:
        await db.rollback()
        path.unlink(missing_ok=True)  # no dejar archivos huérfanos si la BD falla
        raise
    log.info("[accounting] comprobante guardado | workspace=%s | movement=%s | bytes=%d",
             workspace_id, movement_id, len(data))
    return dict(row)


async def list_attachments(db: AsyncSession, workspace_id: str, movement_id: str) -> list[dict]:
    """Comprobantes de un movimiento, más antiguos primero."""
    rows = (await db.execute(
        text(f"SELECT {_COLUMNS} FROM movement_attachments WHERE movement_id = :m AND workspace_id = :w ORDER BY created_at"),
        {"m": movement_id, "w": workspace_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def get_file(db: AsyncSession, workspace_id: str, attachment_id: str) -> tuple[dict, Path]:
    """Metadato + ruta en disco de un comprobante del workspace. 404 si no existe o falta el archivo."""
    row = (await db.execute(
        text(f"SELECT {_COLUMNS}, storage_key FROM movement_attachments WHERE id = :a AND workspace_id = :w"),
        {"a": attachment_id, "w": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado.")
    path = resolve_path(row["storage_key"])
    if not path.is_file():
        log.error("[accounting] archivo de comprobante ausente en disco | attachment=%s", attachment_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo ya no está disponible.")
    return dict(row), path


async def delete_attachment(db: AsyncSession, workspace_id: str, attachment_id: str) -> None:
    """Elimina el registro y el archivo. 404 si no existe."""
    row = (await db.execute(
        text("DELETE FROM movement_attachments WHERE id = :a AND workspace_id = :w RETURNING storage_key"),
        {"a": attachment_id, "w": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado.")
    await db.commit()
    resolve_path(row["storage_key"]).unlink(missing_ok=True)
