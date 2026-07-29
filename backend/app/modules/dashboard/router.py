from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.responses import ok
from app.models.content import GeneratedCopy
from app.models.lead import Lead
from app.models.material import Material
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "operator")),
):
    materials_new = db.query(func.count(Material.id)).filter(Material.status == "new").scalar() or 0

    today = date.today()
    day_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(today, time.max, tzinfo=timezone.utc)

    # Prefer next_follow_at on today; also count status==new as follow-ups
    leads_follow_today = (
        db.query(func.count(Lead.id))
        .filter(
            or_(
                and_(Lead.next_follow_at >= day_start, Lead.next_follow_at <= day_end),
                Lead.status == "new",
            )
        )
        .scalar()
        or 0
    )

    recent_copies = db.query(func.count(GeneratedCopy.id)).scalar() or 0

    return ok(
        {
            "materials_new": materials_new,
            "leads_follow_today": leads_follow_today,
            "recent_copies": recent_copies,
        }
    )
