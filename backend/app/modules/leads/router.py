from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.responses import fail, ok
from app.models.lead import Lead
from app.models.user import User
from app.modules.leads import service as svc
from app.modules.leads.schemas import (
    LeadActivityCreate,
    LeadCollaboratorAdd,
    LeadCreate,
    LeadUpdate,
)

router = APIRouter(prefix="/leads", tags=["leads"])


def _validate_source(source: str) -> None:
    if source not in svc.SOURCES:
        raise HTTPException(status_code=400, detail="Invalid source")


def _validate_status(status_val: str) -> None:
    if status_val not in svc.STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")


@router.get("/assignees")
def lead_assignees(
    db: Session = Depends(get_db),
        _: User = Depends(require_permissions("leads.read", "leads.write")),
):
    """可指派主责/协作的运营与负责人列表。"""
    return ok(svc.list_assignees(db))


@router.get("")
def list_leads(
    source: str | None = None,
    status: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions("leads.read", "leads.write")),
):
    if source:
        _validate_source(source)
    if status:
        _validate_status(status)
    return ok(
        svc.list_leads(
            db,
            source=source,
            status=status,
            name=name,
            phone=phone,
            page=page,
            page_size=page_size,
        )
    )


@router.post("")
def create_lead(
    body: LeadCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("leads.read", "leads.write")),
):
    _validate_source(body.source)
    _validate_status(body.status)
    lead = svc.create_lead(db, body.model_dump(), user)
    return ok(svc.serialize_lead(db, lead), status_code=201)


@router.get("/{lead_id}")
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions("leads.read", "leads.write")),
):
    lead = svc.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return ok(svc.serialize_lead(db, lead, include_followers=True))


@router.patch("/{lead_id}")
def patch_lead(
    lead_id: int,
    body: LeadUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("leads.read", "leads.write")),
):
    lead = svc.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    data = body.model_dump(exclude_unset=True)
    if "source" in data and data["source"] is not None:
        _validate_source(data["source"])
    if "status" in data and data["status"] is not None:
        _validate_status(data["status"])

    lead = svc.update_lead(db, lead, data, user)
    return ok(svc.serialize_lead(db, lead, include_followers=True))


@router.get("/{lead_id}/activities")
def list_activities(
    lead_id: int,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 50,
    limit: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions("leads.read", "leads.write")),
):
    lead = svc.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    # 兼容旧 limit：等价于第一页 page_size=limit
    if limit is not None and limit > 0:
        page = 1
        page_size = min(int(limit), 200)
    return ok(svc.list_activities(db, lead_id, kind=kind, page=page, page_size=page_size))


@router.post("/{lead_id}/activities")
def post_activity(
    lead_id: int,
    body: LeadActivityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("leads.read", "leads.write")),
):
    lead = svc.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    if body.status:
        _validate_status(body.status)
    content = (body.content or "").strip()
    if not content:
        return fail("INVALID", "请填写跟进内容", status_code=400)

    act = svc.create_follow_activity(
        db,
        lead,
        user,
        content=content,
        contact_method=body.contact_method or "",
        next_follow_at=body.next_follow_at,
        status=body.status,
        join_as_collaborator=body.join_as_collaborator,
    )
    return ok(
        {
            "activity": svc.serialize_activity(db, act),
            "lead": svc.serialize_lead(db, lead, include_followers=True),
        },
        status_code=201,
    )


@router.post("/{lead_id}/collaborators")
def add_collaborator(
    lead_id: int,
    body: LeadCollaboratorAdd,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("leads.read", "leads.write")),
):
    lead = svc.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    err = svc.add_collaborator(db, lead, body.user_id, user, note=body.note or "")
    if err:
        return fail("COLLAB_FAILED", err, status_code=400)
    db.refresh(lead)
    return ok(svc.serialize_lead(db, lead, include_followers=True))


@router.post("/{lead_id}/collaborators/me")
def join_as_collaborator(
    lead_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("leads.read", "leads.write")),
):
    """当前用户主动加入协作，避免无人登记却私下联系。"""
    lead = svc.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    if lead.owner_id == user.id:
        return ok(svc.serialize_lead(db, lead, include_followers=True))
    svc.ensure_collaborator(db, lead, user, note="主动加入协作", actor=user, log=True)
    db.commit()
    db.refresh(lead)
    return ok(svc.serialize_lead(db, lead, include_followers=True))


@router.delete("/{lead_id}/collaborators/{user_id}")
def remove_collaborator(
    lead_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("leads.read", "leads.write")),
):
    lead = svc.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    # 本人可退出；负责人可移除他人；主责可移除协作
    if user_id != user.id and user.role != "admin" and lead.owner_id != user.id:
        return fail("FORBIDDEN", "仅主跟进人或负责人可移除其他协作人", status_code=403)
    err = svc.remove_collaborator(db, lead, user_id, user)
    if err:
        return fail("COLLAB_FAILED", err, status_code=400)
    db.refresh(lead)
    return ok(svc.serialize_lead(db, lead, include_followers=True))
