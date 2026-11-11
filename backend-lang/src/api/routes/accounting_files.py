"""
Router /workspaces/{workspace_id}/accounting — Comprobantes de pago adjuntos a movimientos.

Subir, listar, descargar y eliminar. Solo owner/manager. La descarga exige el JWT (no hay URLs públicas):
el front la pide con fetch + Authorization y abre el blob. Eliminar exige confirmed=true (Principio IX).
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_workspace_access
from schemas.accounting import AttachmentOut
from services import attachment_service
from services.audit_service import AuditService

router = APIRouter(tags=["accounting"])
_manager = require_workspace_access("manager")
_BASE = "/workspaces/{workspace_id}/accounting"


@router.post(f"{_BASE}/movements/{{movement_id}}/attachments", response_model=AttachmentOut,
             status_code=status.HTTP_201_CREATED, summary="Adjuntar comprobante (JPG, PNG, WebP o PDF, máx. 5 MB)")
async def upload_attachment(
    workspace_id: str, movement_id: str, file: UploadFile = File(...),
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    # Se lee un byte de más para detectar el exceso sin cargar archivos enormes en memoria.
    data = await file.read(attachment_service.MAX_BYTES + 1)
    row = await attachment_service.save_attachment(db, workspace_id, movement_id, file.filename, data, user.get("sub"))
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=user.get("sub"), action="attachment.upload",
        entity_type="movement", entity_id=movement_id,
        after_data={"attachment_id": str(row["id"]), "size_bytes": row["size_bytes"]},
    )
    return row


@router.get(f"{_BASE}/movements/{{movement_id}}/attachments", response_model=list[AttachmentOut],
            summary="Listar comprobantes de un movimiento")
async def list_attachments(
    workspace_id: str, movement_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await attachment_service.list_attachments(db, workspace_id, movement_id)


@router.get(f"{_BASE}/attachments/{{attachment_id}}/file", summary="Descargar comprobante")
async def download_attachment(
    workspace_id: str, attachment_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    meta, path = await attachment_service.get_file(db, workspace_id, attachment_id)
    return FileResponse(
        path, media_type=meta["content_type"], filename=meta["original_name"],
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"},
    )


@router.delete(f"{_BASE}/attachments/{{attachment_id}}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar comprobante")
async def delete_attachment(
    workspace_id: str, attachment_id: str, confirmed: bool = Query(False),
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    if not confirmed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Esta acción requiere confirmación explícita. Pasa confirmed=true.")
    await attachment_service.delete_attachment(db, workspace_id, attachment_id)
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=user.get("sub"), action="attachment.delete",
        entity_type="attachment", entity_id=attachment_id,
    )
