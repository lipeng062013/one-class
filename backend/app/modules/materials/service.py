from sqlalchemy.orm import Session, joinedload

from app.core.storage import LocalStorage
from app.models.material import Material, MaterialFile
from app.models.user import User
from app.modules.materials.schemas import AUTH_STATUSES, STATUSES


def material_to_dict(m: Material) -> dict:
    return {
        "id": m.id,
        "uploader_id": m.uploader_id,
        "title": m.title,
        "grade": m.grade,
        "subject": m.subject,
        "pain_point": m.pain_point,
        "teacher_action": m.teacher_action,
        "next_step": m.next_step,
        "auth_status": m.auth_status,
        "status": m.status,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "files": [
            {
                "id": f.id,
                "file_path": f.file_path,
                "file_type": f.file_type,
                "sort_order": f.sort_order,
            }
            for f in (m.files or [])
        ],
    }


def list_materials(db: Session, user: User) -> list[Material]:
    q = db.query(Material).options(joinedload(Material.files)).order_by(Material.id.desc())
    if user.role == "teacher":
        q = q.filter(Material.uploader_id == user.id)
    return q.all()


def get_material(db: Session, material_id: int) -> Material | None:
    return (
        db.query(Material)
        .options(joinedload(Material.files))
        .filter(Material.id == material_id)
        .first()
    )


def can_view(user: User, material: Material) -> bool:
    if user.role in {"admin", "operator"}:
        return True
    return material.uploader_id == user.id


def can_upload_file(user: User, material: Material) -> bool:
    if user.role in {"admin", "operator"}:
        return True
    return material.uploader_id == user.id


def can_patch(user: User, material: Material) -> bool:
    if user.role in {"admin", "operator"}:
        return True
    # teacher may update own material content but not status transitions freely —
    # allow teacher to patch own content fields only in router
    return material.uploader_id == user.id


def create_material(db: Session, user: User, data: dict) -> Material | str:
    auth_status = data.get("auth_status") or "pending"
    if auth_status not in AUTH_STATUSES:
        return "授权状态无效"
    m = Material(
        uploader_id=user.id,
        title=data["title"],
        grade=data.get("grade"),
        subject=data.get("subject"),
        pain_point=data.get("pain_point"),
        teacher_action=data.get("teacher_action"),
        next_step=data.get("next_step"),
        auth_status=auth_status,
        status="new",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return get_material(db, m.id) or m


def update_material(db: Session, user: User, material: Material, data: dict) -> Material | str:
    if user.role == "teacher":
        # teachers cannot change status or others' materials
        if material.uploader_id != user.id:
            return "无权限"
        forbidden = {"status"}
        for key in forbidden:
            if key in data and data[key] is not None:
                return "老师不能修改素材业务状态"
    if "auth_status" in data and data["auth_status"] is not None:
        if data["auth_status"] not in AUTH_STATUSES:
            return "授权状态无效"
        material.auth_status = data["auth_status"]
    if "status" in data and data["status"] is not None:
        if data["status"] not in STATUSES:
            return "状态无效"
        material.status = data["status"]
    for field in ("title", "grade", "subject", "pain_point", "teacher_action", "next_step"):
        if field in data and data[field] is not None:
            setattr(material, field, data[field])
    db.add(material)
    db.commit()
    return get_material(db, material.id) or material


def add_file(
    db: Session,
    storage: LocalStorage,
    material: Material,
    *,
    filename: str,
    content: bytes,
    content_type: str,
) -> MaterialFile:
    sort_order = len(material.files or [])
    safe_name = filename.replace("/", "_").replace("\\", "_")
    rel = f"materials/{material.id}/{sort_order}_{safe_name}"
    storage.save(rel, content)
    mf = MaterialFile(
        material_id=material.id,
        file_path=rel,
        file_type=content_type or "application/octet-stream",
        sort_order=sort_order,
    )
    db.add(mf)
    db.commit()
    db.refresh(mf)
    return mf
