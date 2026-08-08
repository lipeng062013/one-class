"""Shared role sets for staffing / teaching / 学管.

负责人 (admin) 同时可担任授课老师与学管师，须出现在排课、班级老师、
学员学管等下拉与搜索结果中。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.user import User

# 可被指派为班级/排课/点名「上课老师」
TEACHING_STAFF_ROLES: frozenset[str] = frozenset(
    {"admin", "teacher", "cr", "academic_manager"}
)

# 可被指派为学员「学管师」
ACADEMIC_MANAGER_ROLES: frozenset[str] = frozenset(
    {"admin", "cr", "academic_manager"}
)

# 财务数据按「名下学员」收窄的角色（学管师）
FINANCE_SCOPED_ROLES: frozenset[str] = frozenset({"cr", "academic_manager"})

ROLE_DISPLAY_LABEL: dict[str, str] = {
    "admin": "负责人",
    "operator": "运营",
    "teacher": "老师",
    "cr": "CR（班主任，学管师）",
    "academic_manager": "CR（班主任，学管师）",
}


def is_teaching_staff(role: str | None) -> bool:
    return bool(role) and role in TEACHING_STAFF_ROLES


def is_academic_manager_role(role: str | None) -> bool:
    return bool(role) and role in ACADEMIC_MANAGER_ROLES


def is_finance_scoped_role(role: str | None) -> bool:
    """学管师等：财务/报名仅可见 academic_manager_id = 自己 的学员。"""
    return bool(role) and role in FINANCE_SCOPED_ROLES


def is_operator_finance_scoped(role: str | None) -> bool:
    """运营：财务仅见自己相关订单 / 自己相关学员课消。"""
    return role == "operator"


def operator_related_student_ids(db: "Session", user: "User") -> set[int]:
    """运营相关学员：本人建档，或来源线索主责为自己。"""
    from app.models.lead import Lead
    from app.models.student import Student

    created = {
        int(r[0])
        for r in db.query(Student.id).filter(Student.created_by == user.id).all()
    }
    from_leads = {
        int(r[0])
        for r in (
            db.query(Student.id)
            .join(Lead, Lead.id == Student.source_lead_id)
            .filter(Lead.owner_id == user.id)
            .all()
        )
    }
    return created | from_leads


def managed_student_ids(db: "Session", user: "User") -> set[int] | None:
    """财务/报名单据的学员范围。

    - 返回 None：不限制（负责人等全机构）
    - 返回 set：仅这些学员 id（学管师名下 / 运营相关学员；可为空）
    """
    if is_finance_scoped_role(user.role):
        from app.models.student import Student

        rows = (
            db.query(Student.id)
            .filter(Student.academic_manager_id == user.id)
            .all()
        )
        return {int(r[0]) for r in rows}
    if is_operator_finance_scoped(user.role):
        return operator_related_student_ids(db, user)
    return None
