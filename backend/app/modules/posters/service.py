from __future__ import annotations

import io
import json
import uuid
from typing import Any

from fastapi import HTTPException, status
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.core.storage import LocalStorage
from app.integrations import image_api
from app.integrations.image_api import ImageApiUnavailable
from app.models.material import Material
from app.models.poster import GeneratedPoster
from app.models.template import PosterTemplate
from app.models.user import User
from app.modules.posters.schemas import GeneratePosterRequest

MODES = {"layout", "ai_image"}


def _parse_color(value: str | None, default: tuple[int, int, int] = (255, 255, 255)) -> tuple[int, int, int]:
    if not value:
        return default
    s = value.strip()
    if s.startswith("#") and len(s) == 7:
        try:
            return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
        except ValueError:
            return default
    return default


def _load_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    # Prefer common TrueType fonts; fall back to PIL default.
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",  # Microsoft YaHei (Chinese)
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_layout_png(
    layout: dict[str, Any],
    title: str,
    payload: dict[str, Any],
) -> bytes:
    """Render a poster PNG from layout_json fields and text values."""
    width = int(layout.get("width") or 750)
    height = int(layout.get("height") or 1000)
    bg = _parse_color(layout.get("background"), default=(23, 107, 77))

    image = Image.new("RGB", (width, height), color=bg)
    draw = ImageDraw.Draw(image)

    # Merge title into values so a field with key "title" can pick it up.
    values: dict[str, Any] = dict(payload or {})
    if title:
        values.setdefault("title", title)

    fields = layout.get("fields") or []
    for field in fields:
        if not isinstance(field, dict):
            continue
        key = field.get("key") or ""
        text = values.get(key)
        if text is None and key == "title":
            text = title
        if text is None or text == "":
            continue
        x = int(field.get("x") or 0)
        y = int(field.get("y") or 0)
        font_size = int(field.get("font_size") or 32)
        fill = _parse_color(field.get("fill"), default=(255, 255, 255))
        font = _load_font(font_size)
        draw.text((x, y), str(text), fill=fill, font=font)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def serialize_poster(poster: GeneratedPoster) -> dict[str, Any]:
    return {
        "id": poster.id,
        "material_id": poster.material_id,
        "template_id": poster.template_id,
        "mode": poster.mode,
        "title": poster.title,
        "payload_json": poster.payload_json,
        "file_path": poster.file_path,
        "created_by": poster.created_by,
        "created_at": poster.created_at.isoformat() if poster.created_at else None,
    }


def generate_poster(db: Session, user: User, body: GeneratePosterRequest) -> dict[str, Any]:
    if user.role == "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if user.role not in {"admin", "operator"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    mode = body.mode or "layout"
    if mode not in MODES:
        raise HTTPException(status_code=400, detail="Invalid mode")

    if body.material_id is not None:
        material = db.get(Material, body.material_id)
        if not material:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    template: PosterTemplate | None = None
    if body.template_id is not None:
        template = db.get(PosterTemplate, body.template_id)
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    title = body.title or ""
    payload = body.payload or {}
    payload_json = json.dumps(payload, ensure_ascii=False)

    if mode == "layout":
        if template is None:
            raise HTTPException(status_code=400, detail="template_id is required for layout mode")
        try:
            layout = json.loads(template.layout_json or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid template layout_json") from exc
        if not isinstance(layout, dict):
            raise HTTPException(status_code=400, detail="Invalid template layout_json")
        png_bytes = render_layout_png(layout, title, payload)
    else:
        # ai_image
        prompt = body.prompt or title or "poster"
        if payload:
            extra = "；".join(f"{k}: {v}" for k, v in payload.items() if v is not None)
            if extra:
                prompt = f"{prompt}。{extra}"
        try:
            png_bytes = image_api.generate_image(prompt=prompt, title=title)
        except ImageApiUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Image API unavailable: {exc}",
            ) from exc

    storage = LocalStorage()
    relative_path = f"posters/{uuid.uuid4().hex}.png"
    storage.save(relative_path, png_bytes)

    poster = GeneratedPoster(
        material_id=body.material_id,
        template_id=body.template_id,
        mode=mode,
        title=title,
        payload_json=payload_json,
        file_path=relative_path,
        created_by=user.id,
    )
    db.add(poster)
    db.commit()
    db.refresh(poster)
    return serialize_poster(poster)


def list_posters(db: Session) -> list[GeneratedPoster]:
    return db.query(GeneratedPoster).order_by(GeneratedPoster.id.desc()).all()


def get_poster(db: Session, poster_id: int) -> GeneratedPoster:
    poster = db.get(GeneratedPoster, poster_id)
    if not poster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster not found")
    return poster
