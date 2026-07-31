from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.responses import ok
from app.models.template import CopyTemplate, PosterTemplate
from app.models.user import User
from app.modules.templates.schemas import (
    CopyTemplateCreate,
    CopyTemplateOut,
    CopyTemplateUpdate,
    PosterTemplateCreate,
    PosterTemplateOut,
    PosterTemplateUpdate,
)

router = APIRouter(prefix="/templates", tags=["templates"])

_ops = require_roles("admin", "operator")


def _serialize_copy(tpl: CopyTemplate) -> dict:
    return CopyTemplateOut.model_validate(tpl).model_dump()


def _serialize_poster(tpl: PosterTemplate) -> dict:
    return PosterTemplateOut.model_validate(tpl).model_dump()


# ── copy templates ──────────────────────────────────────────────


@router.get("/copies")
def list_copy_templates(
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    items = db.query(CopyTemplate).order_by(CopyTemplate.id.asc()).all()
    return ok([_serialize_copy(t) for t in items])


@router.post("/copies")
def create_copy_template(
    body: CopyTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_ops),
):
    tpl = CopyTemplate(
        name=body.name,
        scene=body.scene,
        body=body.body or "",
        is_system=False,
        is_active=body.is_active,
        created_by=user.id,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return ok(_serialize_copy(tpl))


@router.get("/copies/{template_id}")
def get_copy_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    tpl = db.get(CopyTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copy template not found")
    return ok(_serialize_copy(tpl))


@router.patch("/copies/{template_id}")
def patch_copy_template(
    template_id: int,
    body: CopyTemplateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    tpl = db.get(CopyTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copy template not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(tpl, key, value)

    db.commit()
    db.refresh(tpl)
    return ok(_serialize_copy(tpl))


@router.delete("/copies/{template_id}")
def delete_copy_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    tpl = db.get(CopyTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copy template not found")
    if tpl.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete system template")
    db.delete(tpl)
    db.commit()
    return ok({"id": template_id})


# ── poster templates ────────────────────────────────────────────


@router.get("/posters")
def list_poster_templates(
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    items = db.query(PosterTemplate).order_by(PosterTemplate.id.asc()).all()
    return ok([_serialize_poster(t) for t in items])


@router.post("/posters")
def create_poster_template(
    body: PosterTemplateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    tpl = PosterTemplate(
        name=body.name,
        scene=body.scene,
        layout_json=body.layout_json or "{}",
        preview_path=body.preview_path,
        is_system=False,
        is_active=body.is_active,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return ok(_serialize_poster(tpl))


@router.get("/posters/{template_id}")
def get_poster_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    tpl = db.get(PosterTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster template not found")
    return ok(_serialize_poster(tpl))


@router.patch("/posters/{template_id}")
def patch_poster_template(
    template_id: int,
    body: PosterTemplateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    tpl = db.get(PosterTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster template not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(tpl, key, value)

    db.commit()
    db.refresh(tpl)
    return ok(_serialize_poster(tpl))


@router.delete("/posters/{template_id}")
def delete_poster_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    tpl = db.get(PosterTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster template not found")
    if tpl.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete system template")
    db.delete(tpl)
    db.commit()
    return ok({"id": template_id})
