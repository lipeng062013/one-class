from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.content import GeneratedCopy
from app.models.knowledge import KnowledgeEntry
from app.models.lead import Lead
from app.models.material import Material
from app.models.poster import GeneratedPoster
from app.models.student import LearningRecord, Student
from app.models.template import CopyTemplate
from app.models.todo import TodoItem
from app.models.user import User

VALID_ROLES = {"admin", "operator", "teacher"}


def list_users(
    db: Session,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    username: str | None = None,
    display_name: str | None = None,
) -> list[User]:
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if is_active is not None:
        q = q.filter(User.is_active.is_(is_active))
    if username:
        q = q.filter(User.username.contains(username))
    if display_name:
        q = q.filter(User.display_name.contains(display_name))
    return q.order_by(User.id.asc()).all()


def create_user(db: Session, *, username: str, display_name: str, role: str, password: str) -> User | str:
    if role not in VALID_ROLES:
        return "角色无效"
    exists = db.query(User).filter(User.username == username).first()
    if exists:
        return "用户名已存在"
    user = User(
        username=username,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user: User,
    *,
    display_name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> User | str:
    if display_name is not None:
        user.display_name = display_name
    if role is not None:
        if role not in VALID_ROLES:
            return "角色无效"
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()


def delete_user(db: Session, user: User, *, actor: User) -> str | None:
    """
    Hard-delete a user account. Detach or reassign related rows so FKs stay valid.
    Returns error message string on failure, None on success.
    """
    if user.id == actor.id:
        return "不能删除当前登录账号"
    if user.role == "admin":
        other_admins = (
            db.query(User).filter(User.role == "admin", User.id != user.id).count()
        )
        if other_admins == 0:
            return "不能删除唯一的负责人账号"

    uid = user.id
    reassign_to = actor.id

    # Non-null FKs: reassign to the admin performing the delete
    db.query(Material).filter(Material.uploader_id == uid).update(
        {Material.uploader_id: reassign_to}, synchronize_session=False
    )
    db.query(LearningRecord).filter(LearningRecord.teacher_id == uid).update(
        {LearningRecord.teacher_id: reassign_to}, synchronize_session=False
    )

    # Personal todos go away with the account
    db.query(TodoItem).filter(TodoItem.user_id == uid).delete(synchronize_session=False)

    # Nullable FKs: clear reference
    db.query(Student).filter(Student.academic_manager_id == uid).update(
        {Student.academic_manager_id: None}, synchronize_session=False
    )
    db.query(Student).filter(Student.created_by == uid).update(
        {Student.created_by: None}, synchronize_session=False
    )
    db.query(Lead).filter(Lead.owner_id == uid).update(
        {Lead.owner_id: None}, synchronize_session=False
    )
    db.query(GeneratedCopy).filter(GeneratedCopy.created_by == uid).update(
        {GeneratedCopy.created_by: None}, synchronize_session=False
    )
    db.query(GeneratedPoster).filter(GeneratedPoster.created_by == uid).update(
        {GeneratedPoster.created_by: None}, synchronize_session=False
    )
    db.query(CopyTemplate).filter(CopyTemplate.created_by == uid).update(
        {CopyTemplate.created_by: None}, synchronize_session=False
    )
    db.query(KnowledgeEntry).filter(KnowledgeEntry.updated_by == uid).update(
        {KnowledgeEntry.updated_by: None}, synchronize_session=False
    )

    db.delete(user)
    db.commit()
    return None
