from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.responses import ok
from app.models.lead import Lead
from app.models.user import User
from app.modules.leads.schemas import LeadCreate, LeadOut, LeadUpdate

router = APIRouter(prefix="/leads", tags=["leads"])

SOURCES = {"referral", "dianping", "wechat", "walkin", "other"}
STATUSES = {"new", "contacted", "visited", "enrolled", "lost"}


def _serialize(lead: Lead) -> dict:
    return LeadOut.model_validate(lead).model_dump()


def _validate_source(source: str) -> None:
    if source not in SOURCES:
        raise HTTPException(status_code=400, detail="Invalid source")


def _validate_status(status_val: str) -> None:
    if status_val not in STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")


@router.get("")
def list_leads(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "operator")),
):
    leads = db.query(Lead).order_by(Lead.id.desc()).all()
    return ok([_serialize(lead) for lead in leads])


@router.post("")
def create_lead(
    body: LeadCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "operator")),
):
    _validate_source(body.source)
    _validate_status(body.status)
    lead = Lead(
        student_or_parent_name=body.student_or_parent_name,
        phone=body.phone,
        source=body.source,
        referrer_name=body.referrer_name,
        channel_note=body.channel_note or "",
        need=body.need or "",
        status=body.status,
        next_follow_at=body.next_follow_at,
        owner_id=body.owner_id,
        notes=body.notes or "",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return ok(_serialize(lead))


@router.patch("/{lead_id}")
def patch_lead(
    lead_id: int,
    body: LeadUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "operator")),
):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    data = body.model_dump(exclude_unset=True)
    if "source" in data and data["source"] is not None:
        _validate_source(data["source"])
    if "status" in data and data["status"] is not None:
        _validate_status(data["status"])

    for key, value in data.items():
        setattr(lead, key, value)

    db.commit()
    db.refresh(lead)
    return ok(_serialize(lead))
