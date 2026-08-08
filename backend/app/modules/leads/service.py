"""线索跟进：详情、协作人、动态时间线。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadActivity, LeadCollaborator
from app.models.student import Student
from app.models.user import User
from app.core.timeutil import now as _utcnow

SOURCES = {"referral", "dianping", "wechat", "walkin", "other"}
STATUSES = {"new", "contacted", "visited", "enrolled", "lost"}
CONTACT_METHODS = {"", "phone", "wechat", "visit", "sms", "other"}

SOURCE_LABELS = {
    "referral": "老带新",
    "dianping": "大众点评",
    "wechat": "微信",
    "walkin": "到店",
    "other": "其他",
}
STATUS_LABELS = {
    "new": "新建",
    "contacted": "已联系",
    "visited": "已到访",
    "enrolled": "已报名",
    "lost": "已流失",
}
CONTACT_LABELS = {
    "phone": "电话",
    "wechat": "微信",
    "visit": "到访/面谈",
    "sms": "短信",
    "other": "其他",
}
KIND_LABELS = {
    "create": "建档",
    "update": "资料变更",
    "follow": "跟进记录",
    "owner": "主责变更",
    "collaborator": "协作变动",
    "system": "系统",
}
FIELD_LABELS = {
    "student_or_parent_name": "姓名",
    "phone": "电话",
    "external_code": "编号",
    "school": "学校",
    "grade": "年级",
    "age": "年龄",
    "campus": "校区",
    "imported_creator_name": "导入创建人",
    "source": "来源",
    "referrer_name": "介绍人",
    "channel_note": "渠道备注",
    "need": "需求",
    "status": "状态",
    "next_follow_at": "下次跟进",
    "owner_id": "主跟进人",
    "notes": "备注",
}

def _user_name(db: Session, user_id: int | None) -> str:
    if not user_id:
        return ""
    u = db.get(User, user_id)
    if not u:
        return ""
    return (u.display_name or u.username or "").strip()

def _role_label(role: str) -> str:
    return {
        "admin": "负责人",
        "operator": "运营",
        "teacher": "教师",
        "cr": "CR（班主任，学管师）",
        "academic_manager": "CR（班主任，学管师）",
    }.get(role, role)

def _parse_meta(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _dump_meta(data: dict | None) -> str:
    try:
        return json.dumps(data or {}, ensure_ascii=False)
    except Exception:
        return "{}"

def _fmt_value(field: str, value: Any, db: Session) -> str:
    if value is None or value == "":
        return "—"
    if field == "status":
        return STATUS_LABELS.get(str(value), str(value))
    if field == "source":
        return SOURCE_LABELS.get(str(value), str(value))
    if field == "owner_id":
        return _user_name(db, int(value)) if value else "—"
    if field == "next_follow_at":
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        return str(value)
    return str(value)

def add_activity(
    db: Session,
    *,
    lead_id: int,
    actor: User | None,
    kind: str,
    title: str,
    content: str = "",
    contact_method: str = "",
    meta: dict | None = None,
    commit: bool = False,
) -> LeadActivity:
    row = LeadActivity(
        lead_id=lead_id,
        actor_id=actor.id if actor else None,
        kind=kind,
        title=title or KIND_LABELS.get(kind, "动态"),
        content=content or "",
        contact_method=contact_method or "",
        meta_json=_dump_meta(meta),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row

def list_followers(db: Session, lead: Lead) -> list[dict]:
    """主跟进人 + 协作人，主跟进人排前。"""
    rows: list[dict] = []
    seen: set[int] = set()

    if lead.owner_id:
        owner = db.get(User, lead.owner_id)
        if owner:
            seen.add(owner.id)
            rows.append(
                {
                    "id": 0,
                    "user_id": owner.id,
                    "name": (owner.display_name or owner.username or "").strip(),
                    "role": "owner",
                    "role_label": "主跟进人",
                    "note": "",
                    "joined_at": lead.created_at,
                    "is_owner": True,
                }
            )

    collabs = (
        db.query(LeadCollaborator)
        .filter(LeadCollaborator.lead_id == lead.id)
        .order_by(LeadCollaborator.joined_at.asc())
        .all()
    )
    for c in collabs:
        if c.user_id in seen:
            continue
        u = db.get(User, c.user_id)
        name = (u.display_name or u.username or "").strip() if u else f"用户#{c.user_id}"
        seen.add(c.user_id)
        rows.append(
            {
                "id": c.id,
                "user_id": c.user_id,
                "name": name,
                "role": c.role or "collaborator",
                "role_label": "协作跟进人",
                "note": c.note or "",
                "joined_at": c.joined_at,
                "is_owner": False,
            }
        )
    return rows

def serialize_lead(
    db: Session,
    lead: Lead,
    *,
    include_followers: bool = True,
    user_names: dict[int, str] | None = None,
    collaborator_counts: dict[int, int] | None = None,
) -> dict:
    followers = list_followers(db, lead) if include_followers else []
    if include_followers:
        collab_n = max(0, len(followers) - (1 if lead.owner_id else 0))
    elif collaborator_counts is not None:
        collab_n = collaborator_counts.get(lead.id, 0)
    else:
        collab_n = (
            db.query(LeadCollaborator)
            .filter(LeadCollaborator.lead_id == lead.id)
            .count()
        )

    def resolved_user_name(user_id: int | None) -> str:
        if user_names is not None:
            return user_names.get(user_id or 0, "")
        return _user_name(db, user_id)

    linked = (
        db.query(Student.id)
        .filter(Student.source_lead_id == lead.id)
        .order_by(Student.id.desc())
        .first()
    )
    converted_student_id = int(linked[0]) if linked else None
    locked = lead.status == "enrolled"

    return {
        "id": lead.id,
        "student_or_parent_name": lead.student_or_parent_name,
        "phone": lead.phone,
        "external_code": lead.external_code,
        "school": lead.school or "",
        "grade": lead.grade or "",
        "age": lead.age,
        "campus": lead.campus or "",
        "imported_creator_name": lead.imported_creator_name or "",
        "source": lead.source,
        "referrer_name": lead.referrer_name,
        "channel_note": lead.channel_note or "",
        "need": lead.need or "",
        "status": lead.status,
        "next_follow_at": lead.next_follow_at,
        "owner_id": lead.owner_id,
        "owner_name": resolved_user_name(lead.owner_id),
        "notes": lead.notes or "",
        "last_contact_at": getattr(lead, "last_contact_at", None),
        "last_contact_by": getattr(lead, "last_contact_by", None),
        "last_contact_by_name": resolved_user_name(getattr(lead, "last_contact_by", None)),
        "last_contact_method": getattr(lead, "last_contact_method", None) or "",
        "collaborator_count": collab_n,
        "followers": followers if include_followers else [],
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
        "locked": locked,
        "converted_student_id": converted_student_id,
    }


def is_admin_user(user: User) -> bool:
    return getattr(user, "role", None) == "admin"


def assert_lead_mutable(
    lead: Lead,
    user: User,
    *,
    action: str,
) -> str | None:
    """已报名线索锁定。返回错误文案，None 表示允许。

    action: edit | follow | team | status
    """
    if lead.status != "enrolled":
        return None
    if action == "status":
        if is_admin_user(user):
            return None
        return "仅负责人可变更已报名线索的状态"
    if action == "edit":
        if is_admin_user(user):
            return None
        return "该线索已报名，信息已锁定；如需变更请联系负责人"
    if action == "follow":
        return "该线索已报名，不可再写跟进"
    if action == "team":
        return "该线索已报名，跟进团队已冻结；如需调整请负责人先变更状态"
    return "该线索已报名，操作已锁定"


def find_student_by_lead(db: Session, lead_id: int) -> Student | None:
    return (
        db.query(Student)
        .filter(Student.source_lead_id == lead_id)
        .order_by(Student.id.desc())
        .first()
    )


def convert_lead_on_enrolled(db: Session, lead: Lead, user: User) -> dict:
    """线索变为已报名时幂等建档。不发调配待办、不设学管。"""
    existing = find_student_by_lead(db, lead.id)
    if existing:
        return {
            "converted_student_id": existing.id,
            "conversion_status": "already_linked",
        }

    name = (lead.student_or_parent_name or "").strip()
    if not name:
        return {
            "converted_student_id": None,
            "conversion_status": "incomplete",
            "message": "姓名为空，无法自动建档，请完善线索后再转",
        }

    grade = (lead.grade or "").strip() or "待完善"
    note_parts = [f"来源线索#{lead.id}"]
    if (lead.need or "").strip():
        note_parts.append(f"需求：{lead.need.strip()}")
    if (lead.notes or "").strip():
        note_parts.append(f"备注：{lead.notes.strip()}")
    if (lead.campus or "").strip():
        note_parts.append(f"校区：{lead.campus.strip()}")
    if (lead.source or "").strip():
        note_parts.append(f"获客来源：{SOURCE_LABELS.get(lead.source, lead.source)}")

    student = Student(
        name=name,
        grade=grade,
        school=(lead.school or "").strip(),
        phone=lead.phone,
        parent_name=None,
        academic_manager_id=None,
        status="active",
        source_lead_id=lead.id,
        notes="；".join(note_parts),
        linked_courses="[]",
        created_by=user.id,
    )
    db.add(student)
    db.flush()

    add_activity(
        db,
        lead_id=lead.id,
        actor=user,
        kind="system",
        title="已自动转为学员",
        content=f"已创建学员「{student.name}」#{student.id}，请完成报名收费；报名成功后由负责人分配学管。",
        meta={"student_id": student.id, "conversion": "created"},
    )
    return {
        "converted_student_id": student.id,
        "conversion_status": "created",
    }

def list_leads(
    db: Session,
    *,
    source: str | None = None,
    status: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    from app.core.pagination import clamp_page, clamp_page_size, page_payload, paginate_query

    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    q = db.query(Lead)
    if source:
        q = q.filter(Lead.source == source)
    if status:
        q = q.filter(Lead.status == status)
    if name:
        q = q.filter(Lead.student_or_parent_name.contains(name))
    if phone:
        q = q.filter(Lead.phone.contains(phone))
    q = q.order_by(Lead.id.desc())
    leads, total = paginate_query(q, page=page, page_size=page_size)
    lead_ids = [lead.id for lead in leads]
    user_ids = {
        user_id
        for lead in leads
        for user_id in (lead.owner_id, getattr(lead, "last_contact_by", None))
        if user_id
    }
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_names = {
        user.id: (user.display_name or user.username or "").strip()
        for user in users
    }
    collaborator_counts = (
        {
            lead_id: int(count)
            for lead_id, count in db.query(
                LeadCollaborator.lead_id,
                func.count(LeadCollaborator.id),
            )
            .filter(LeadCollaborator.lead_id.in_(lead_ids))
            .group_by(LeadCollaborator.lead_id)
            .all()
        }
        if lead_ids
        else {}
    )
    items = [
        serialize_lead(
            db,
            lead,
            include_followers=False,
            user_names=user_names,
            collaborator_counts=collaborator_counts,
        )
        for lead in leads
    ]
    return page_payload(items, total=total, page=page, page_size=page_size)

def get_lead(db: Session, lead_id: int) -> Lead | None:
    return db.get(Lead, lead_id)

def create_lead(db: Session, data: dict, user: User) -> Lead:
    owner_id = data.get("owner_id")
    if owner_id is None:
        owner_id = user.id

    lead = Lead(
        student_or_parent_name=(data.get("student_or_parent_name") or "").strip(),
        phone=data.get("phone"),
        external_code=(data.get("external_code") or "").strip() or None,
        school=(data.get("school") or "").strip(),
        grade=(data.get("grade") or "").strip(),
        age=data.get("age"),
        campus=(data.get("campus") or "").strip(),
        imported_creator_name=(data.get("imported_creator_name") or "").strip(),
        source=data.get("source") or "other",
        referrer_name=data.get("referrer_name"),
        channel_note=(data.get("channel_note") or "").strip(),
        need=(data.get("need") or "").strip(),
        status=data.get("status") or "new",
        next_follow_at=data.get("next_follow_at"),
        owner_id=int(owner_id) if owner_id else None,
        notes=(data.get("notes") or "").strip(),
    )
    db.add(lead)
    db.flush()

    add_activity(
        db,
        lead_id=lead.id,
        actor=user,
        kind="create",
        title="新建线索",
        content=f"创建线索「{lead.student_or_parent_name}」",
        meta={"status": lead.status, "source": lead.source, "owner_id": lead.owner_id},
    )
    db.commit()
    db.refresh(lead)
    return lead

def update_lead(
    db: Session, lead: Lead, data: dict, user: User
) -> tuple[Lead, dict | None] | str:
    """更新线索。成功返回 (lead, conversion_meta|None)，失败返回错误文案。"""
    changes: list[dict] = []
    track_fields = [
        "student_or_parent_name",
        "phone",
        "external_code",
        "school",
        "grade",
        "age",
        "campus",
        "imported_creator_name",
        "source",
        "referrer_name",
        "channel_note",
        "need",
        "status",
        "next_follow_at",
        "owner_id",
        "notes",
    ]
    old_owner = lead.owner_id
    was_enrolled = lead.status == "enrolled"
    becoming_enrolled = False

    def _norm_cmp(key: str, new_val: Any, old_val: Any) -> tuple[Any, Any, Any]:
        """返回 (new_val_normalized, old_cmp, new_cmp)。"""
        if key in (
            "student_or_parent_name",
            "external_code",
            "school",
            "grade",
            "campus",
            "imported_creator_name",
            "channel_note",
            "need",
            "notes",
        ):
            nv = (new_val or "").strip() if new_val is not None else ""
            return nv, (old_val or "").strip() if old_val is not None else "", nv
        if key == "owner_id":
            nv = int(new_val) if new_val is not None else None
            return nv, old_val, nv
        return new_val, old_val, new_val

    # 预检已报名锁定（仅对真正会变更的字段）
    if was_enrolled:
        for key in track_fields:
            if key not in data:
                continue
            _, old_cmp, new_cmp = _norm_cmp(key, data[key], getattr(lead, key))
            if old_cmp == new_cmp:
                continue
            if key == "status":
                err = assert_lead_mutable(lead, user, action="status")
            elif key == "owner_id":
                err = assert_lead_mutable(lead, user, action="team")
            else:
                err = assert_lead_mutable(lead, user, action="edit")
            if err:
                return err

    for key in track_fields:
        if key not in data:
            continue
        old_val = getattr(lead, key)
        new_val, old_cmp, new_cmp = _norm_cmp(key, data[key], old_val)

        if old_cmp == new_cmp:
            continue

        if key == "status" and new_cmp == "enrolled" and old_cmp != "enrolled":
            becoming_enrolled = True

        changes.append(
            {
                "field": key,
                "label": FIELD_LABELS.get(key, key),
                "from": _fmt_value(key, old_val, db),
                "to": _fmt_value(key, new_val, db),
            }
        )
        setattr(lead, key, new_val)

    conversion: dict | None = None
    if becoming_enrolled:
        conversion = convert_lead_on_enrolled(db, lead, user)

    if not changes:
        db.commit()
        db.refresh(lead)
        # 已是 enrolled 时仍返回已关联学员 id，便于前端「去报名」
        if lead.status == "enrolled" and conversion is None:
            linked = find_student_by_lead(db, lead.id)
            if linked:
                conversion = {
                    "converted_student_id": linked.id,
                    "conversion_status": "already_linked",
                }
        return lead, conversion

    # 主责变更单独记一条，更醒目
    owner_change = next((c for c in changes if c["field"] == "owner_id"), None)
    other_changes = [c for c in changes if c["field"] != "owner_id"]

    if owner_change:
        add_activity(
            db,
            lead_id=lead.id,
            actor=user,
            kind="owner",
            title="主跟进人变更",
            content=f"{owner_change['from']} → {owner_change['to']}",
            meta={"changes": [owner_change], "old_owner_id": old_owner, "new_owner_id": lead.owner_id},
        )

    if other_changes:
        lines = [f"{c['label']}：{c['from']} → {c['to']}" for c in other_changes]
        add_activity(
            db,
            lead_id=lead.id,
            actor=user,
            kind="update",
            title="资料已更新",
            content="\n".join(lines),
            meta={"changes": other_changes},
        )

    db.commit()
    db.refresh(lead)
    return lead, conversion

def ensure_collaborator(
    db: Session,
    lead: Lead,
    user: User,
    *,
    note: str = "",
    actor: User | None = None,
    log: bool = True,
) -> LeadCollaborator | None:
    """将用户加入协作（已是主责或已在协作表则跳过）。"""
    if lead.owner_id and lead.owner_id == user.id:
        return None
    existing = (
        db.query(LeadCollaborator)
        .filter(LeadCollaborator.lead_id == lead.id, LeadCollaborator.user_id == user.id)
        .first()
    )
    if existing:
        return existing

    row = LeadCollaborator(
        lead_id=lead.id,
        user_id=user.id,
        role="collaborator",
        note=(note or "").strip()[:255],
        joined_by=(actor or user).id if (actor or user) else None,
    )
    db.add(row)
    db.flush()
    if log:
        who = _user_name(db, user.id) or f"用户#{user.id}"
        add_activity(
            db,
            lead_id=lead.id,
            actor=actor or user,
            kind="collaborator",
            title="加入协作跟进",
            content=f"{who} 加入本线索协作"
            + (f"（{(note or '').strip()}）" if (note or "").strip() else "")
            + "。多人跟进请先看最新动态再联系家长，避免重复沟通。",
            meta={"user_id": user.id, "action": "join"},
        )
    return row

def remove_collaborator(
    db: Session,
    lead: Lead,
    user_id: int,
    actor: User,
) -> str | None:
    err = assert_lead_mutable(lead, actor, action="team")
    if err:
        return err
    if lead.owner_id == user_id:
        return "主跟进人请通过「更换主责」调整，不能直接移出协作"
    row = (
        db.query(LeadCollaborator)
        .filter(LeadCollaborator.lead_id == lead.id, LeadCollaborator.user_id == user_id)
        .first()
    )
    if not row:
        return "该用户不在协作名单中"
    name = _user_name(db, user_id) or f"用户#{user_id}"
    db.delete(row)
    add_activity(
        db,
        lead_id=lead.id,
        actor=actor,
        kind="collaborator",
        title="退出协作跟进",
        content=f"{name} 已退出本线索协作",
        meta={"user_id": user_id, "action": "leave"},
    )
    db.commit()
    return None

def add_collaborator(
    db: Session,
    lead: Lead,
    user_id: int,
    actor: User,
    note: str = "",
) -> str | None:
    err = assert_lead_mutable(lead, actor, action="team")
    if err:
        return err
    target = db.get(User, user_id)
    if not target or not target.is_active:
        return "用户不存在或已停用"
    if target.role not in {"admin", "operator"}:
        return "仅可添加负责人或运营为协作人"
    if lead.owner_id == user_id:
        return "该用户已是主跟进人"
    ensure_collaborator(db, lead, target, note=note, actor=actor, log=True)
    db.commit()
    return None


def remove_collaborator_guard(lead: Lead, actor: User) -> str | None:
    return assert_lead_mutable(lead, actor, action="team")


def create_follow_activity(
    db: Session,
    lead: Lead,
    user: User,
    *,
    content: str,
    contact_method: str = "",
    next_follow_at: datetime | None = None,
    status: str | None = None,
    join_as_collaborator: bool = True,
) -> LeadActivity | tuple[LeadActivity, dict | None] | str:
    """写跟进。已报名一律拒绝。未报名且 status→enrolled 时建档。

    成功返回 activity，或 (activity, conversion)；失败返回错误文案。
    """
    err = assert_lead_mutable(lead, user, action="follow")
    if err:
        return err

    method = (contact_method or "").strip()
    if method and method not in CONTACT_METHODS:
        method = "other"

    # 顺带更新状态 / 下次跟进
    side_changes: list[str] = []
    becoming_enrolled = False
    if status and status in STATUSES and status != lead.status:
        old = STATUS_LABELS.get(lead.status, lead.status)
        lead.status = status
        side_changes.append(f"状态：{old} → {STATUS_LABELS.get(status, status)}")
        if status == "enrolled":
            becoming_enrolled = True
    if next_follow_at is not None:
        lead.next_follow_at = next_follow_at
        side_changes.append(f"下次跟进：{next_follow_at.strftime('%Y-%m-%d %H:%M')}")

    lead.last_contact_at = _utcnow()
    lead.last_contact_by = user.id
    lead.last_contact_method = method

    conversion: dict | None = None
    if becoming_enrolled:
        conversion = convert_lead_on_enrolled(db, lead, user)

    if join_as_collaborator:
        ensure_collaborator(
            db,
            lead,
            user,
            note="写跟进自动加入",
            actor=user,
            log=True,
        )

    body = (content or "").strip()
    if side_changes:
        body = body + ("\n" if body else "") + "；".join(side_changes)

    method_label = CONTACT_LABELS.get(method, "")
    title = "跟进记录" + (f" · {method_label}" if method_label else "")

    act = add_activity(
        db,
        lead_id=lead.id,
        actor=user,
        kind="follow",
        title=title,
        content=body,
        contact_method=method,
        meta={
            "status": lead.status,
            "next_follow_at": lead.next_follow_at.isoformat() if lead.next_follow_at else None,
        },
    )
    db.commit()
    db.refresh(act)
    db.refresh(lead)
    if conversion is not None:
        return act, conversion
    return act

def serialize_activity(db: Session, row: LeadActivity) -> dict:
    return {
        "id": row.id,
        "lead_id": row.lead_id,
        "actor_id": row.actor_id,
        "actor_name": _user_name(db, row.actor_id),
        "kind": row.kind,
        "kind_label": KIND_LABELS.get(row.kind, row.kind),
        "title": row.title or KIND_LABELS.get(row.kind, "动态"),
        "content": row.content or "",
        "contact_method": row.contact_method or "",
        "contact_method_label": CONTACT_LABELS.get(row.contact_method or "", ""),
        "meta": _parse_meta(row.meta_json),
        "created_at": row.created_at,
    }

def list_activities(
    db: Session,
    lead_id: int,
    *,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    from app.core.pagination import clamp_page, clamp_page_size, page_payload, paginate_query

    page = clamp_page(page)
    # 动态允许稍大页（上限 200）
    try:
        ps = int(page_size)
    except (TypeError, ValueError):
        ps = 50
    page_size = max(1, min(ps, 200))
    q = db.query(LeadActivity).filter(LeadActivity.lead_id == lead_id)
    if kind and kind != "all":
        q = q.filter(LeadActivity.kind == kind)
    q = q.order_by(LeadActivity.id.desc())
    rows, total = paginate_query(q, page=page, page_size=page_size)
    items = [serialize_activity(db, r) for r in rows]
    return page_payload(items, total=total, page=page, page_size=page_size)

def list_assignees(db: Session) -> list[dict]:
    """可指派为主责/协作的人员：负责人 + 运营。"""
    users = (
        db.query(User)
        .filter(User.is_active.is_(True), User.role.in_(["admin", "operator", "cr", "academic_manager"]))
        .order_by(User.role.asc(), User.id.asc())
        .all()
    )
    return [
        {
            "id": u.id,
            "name": (u.display_name or u.username or "").strip(),
            "role": u.role,
            "role_label": _role_label(u.role),
        }
        for u in users
    ]
