from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.responses import ok
from app.core.storage import LocalStorage
from app.models.user import User
from app.modules.posters import service
from app.modules.posters.schemas import GeneratePosterRequest

router = APIRouter(tags=["posters"])

_ops = require_roles("admin", "operator")


@router.post("/posters/generate")
def generate_poster(
    body: GeneratePosterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_ops),
):
    return ok(service.generate_poster(db, user, body))


@router.get("/posters")
def list_posters(
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    items = service.list_posters(db)
    return ok([service.serialize_poster(p) for p in items])


@router.get("/files/posters/{poster_id}")
def stream_poster_file(
    poster_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    poster = service.get_poster(db, poster_id)
    if not poster.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster file not found")

    storage = LocalStorage()
    try:
        data = storage.read(poster.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster file not found") from exc

    # Infer content type from extension; default to PNG.
    suffix = Path(poster.file_path).suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/png")

    return StreamingResponse(iter([data]), media_type=media_type)
