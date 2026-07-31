from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.image_thumb import DEFAULT_THUMB_EDGE, read_image_variant
from app.core.responses import ok
from app.core.storage import get_storage
from app.models.user import User
from app.modules.posters import service
from app.modules.posters.schemas import GeneratePosterRequest, PosterBulkDelete

router = APIRouter(tags=["posters"])

_ops = require_roles("admin", "operator")

_MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # 12MB


@router.post("/posters/generate")
def generate_poster(
    body: GeneratePosterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_ops),
):
    return ok(service.generate_poster(db, user, body))


@router.post("/posters/upload")
async def upload_poster(
    file: UploadFile = File(...),
    title: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(_ops),
):
    """Manually add a poster image (PNG/JPG/WebP/GIF) to the poster list."""
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="单文件不能超过 12MB")
    return ok(
        service.upload_poster(
            db,
            user,
            title=title,
            content=data,
            content_type=file.content_type or "application/octet-stream",
            filename=file.filename,
        ),
        status_code=201,
    )


@router.get("/posters")
def list_posters(
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    items = service.list_posters(db)
    return ok([service.serialize_poster(p) for p in items])


@router.post("/posters/bulk-delete")
def bulk_delete_posters(
    body: PosterBulkDelete,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    result = service.bulk_delete_posters(db, body.ids)
    return ok(result)


@router.delete("/posters/{poster_id}")
def remove_poster(
    poster_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    service.delete_poster(db, poster_id)
    return ok({"deleted": True, "id": poster_id})


@router.get("/files/posters/{poster_id}")
def stream_poster_file(
    poster_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    thumb: bool = Query(False, description="返回列表用缩略图（JPEG，更小更快）"),
    w: int | None = Query(
        None,
        ge=64,
        le=1280,
        description="缩略图最长边像素；仅 thumb=1 时生效，默认 640",
    ),
):
    poster = service.get_poster(db, poster_id)
    if not poster.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster file not found")

    storage = get_storage()
    try:
        data, media_type = read_image_variant(
            storage,
            poster.file_path,
            thumb=thumb,
            max_edge=w or DEFAULT_THUMB_EDGE,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster file not found") from exc

    headers = {}
    if thumb:
        headers["Cache-Control"] = "private, max-age=86400"
    # Prefer Content-Length via Response for faster client progress / connection reuse
    return Response(content=data, media_type=media_type, headers=headers)
