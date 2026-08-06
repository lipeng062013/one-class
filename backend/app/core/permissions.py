"""Permission catalog and effective-permission helpers.

Roles provide default packs; admins can grant extra permission codes to any user.
Add new codes here first, then wire routers / frontend menus to them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from app.models.user import User


@dataclass(frozen=True)
class PermissionDef:
    code: str
    label: str
    group: str
    group_label: str
    description: str = ""


# ── Catalog (single source of truth; extend here for future modules) ──────────

PERMISSION_DEFS: tuple[PermissionDef, ...] = (
    # 系统
    PermissionDef("users.manage", "用户管理", "system", "系统", "新建/停用用户、重置密码、下发权限"),
    PermissionDef("dashboard.read", "工作台", "system", "系统", "查看工作台汇总数据"),
    PermissionDef("system.read", "系统集成状态", "system", "系统", "查看 AI 等集成配置状态"),
    # 素材
    PermissionDef("materials.read", "查看素材", "materials", "素材", "浏览素材库"),
    PermissionDef("materials.write", "上传/编辑素材", "materials", "素材", "上传与编辑素材"),
    PermissionDef("materials.manage", "管理全部素材", "materials", "素材", "处理任意素材状态与补图"),
    # 成长运营
    PermissionDef("copies.use", "文案生成", "growth", "成长运营", "生成与管理招生文案"),
    PermissionDef("posters.use", "海报生成", "growth", "成长运营", "生成与管理海报"),
    PermissionDef("ai_image.use", "GPT 生图", "growth", "成长运营", "使用 AI 生图工具"),
    PermissionDef("knowledge.read", "查看知识库", "growth", "成长运营", "查看话术/异议/禁用词"),
    PermissionDef("knowledge.write", "编辑知识库", "growth", "成长运营", "增删改知识库条目"),
    PermissionDef("templates.manage", "模板管理", "growth", "成长运营", "管理文案/海报模板"),
    PermissionDef("office.use", "综合办公表", "growth", "成长运营", "访问综合办公表"),
    # 获客
    PermissionDef("leads.read", "查看线索", "crm", "获客", "浏览线索列表与详情"),
    PermissionDef("leads.write", "编辑线索", "crm", "获客", "新建/跟进/协作线索"),
    # 教务
    PermissionDef("students.read", "查看学员", "academic", "教务", "浏览学员档案"),
    PermissionDef("students.write", "编辑学员", "academic", "教务", "新建与编辑学员"),
    PermissionDef("students.delete", "删除/转交学员", "academic", "教务", "删除学员或批量转交学管"),
    PermissionDef("learning.write", "录入学情", "academic", "教务", "提交与管理学情记录"),
    PermissionDef(
        "academic.read",
        "查看教务",
        "academic",
        "教务",
        "查看班级/课表/上课记录等；老师默认仅可查看自己所带课表",
    ),
    PermissionDef("academic.write", "管理教务", "academic", "教务", "排课、点名、班级管理等写操作"),
    PermissionDef("academic.courses_admin", "课程增删改", "academic", "教务", "新建/编辑/删除课程"),
    # 财务
    PermissionDef(
        "finance.read",
        "查看财务",
        "finance",
        "财务",
        "查看订单、收支、课消等（学管师仅可见自己绑定的学员）",
    ),
    PermissionDef("finance.write", "操作财务", "finance", "财务", "创建订单、确认收支等写操作"),
    PermissionDef(
        "finance.income_report",
        "确认收入报表",
        "finance",
        "财务",
        "查看机构级确认收入/待消课时报表（默认仅负责人）",
    ),
    PermissionDef("enrollments.manage", "报名/续费", "finance", "财务", "办理报名与续费"),
)

PERMISSION_CODES: frozenset[str] = frozenset(p.code for p in PERMISSION_DEFS)
PERMISSION_BY_CODE: dict[str, PermissionDef] = {p.code: p for p in PERMISSION_DEFS}

# Group order for UI
GROUP_ORDER: tuple[str, ...] = ("system", "materials", "growth", "crm", "academic", "finance")

# ── Role default packs (mirror historical role access) ────────────────────────

_ALL = frozenset(PERMISSION_CODES)

_OPERATOR = frozenset(
    {
        "dashboard.read",
        "system.read",
        "materials.read",
        "materials.write",
        "materials.manage",
        "copies.use",
        "posters.use",
        "ai_image.use",
        "knowledge.read",
        "templates.manage",
        "office.use",
        "leads.read",
        "leads.write",
    }
)

_TEACHER = frozenset(
    {
        "materials.read",
        "materials.write",
        "students.read",
        "learning.write",
        "academic.read",
    }
)

_CR = frozenset(
    {
        "dashboard.read",
        "materials.read",
        "materials.write",
        "leads.read",
        "leads.write",
        "students.read",
        "students.write",
        # 无 students.delete：删除/转交学员需负责人另行授权
        "learning.write",
        "academic.read",
        "academic.write",
        # 无 academic.courses_admin：课程增删改需负责人另行授权
        "finance.read",  # 仅名下学员（数据范围由 finance 服务约束）
        "finance.write",
        # 无 finance.income_report：不可看确认收入报表
        "enrollments.manage",
    }
)

ROLE_DEFAULT_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": _ALL,
    "operator": _OPERATOR,
    "teacher": _TEACHER,
    "cr": _CR,
    "academic_manager": _CR,  # legacy alias
}


def catalog_grouped() -> list[dict]:
    """Permission list grouped for admin grant UI."""
    groups: dict[str, dict] = {}
    for code in GROUP_ORDER:
        groups[code] = {"group": code, "group_label": "", "permissions": []}
    for p in PERMISSION_DEFS:
        g = groups.setdefault(
            p.group,
            {"group": p.group, "group_label": p.group_label, "permissions": []},
        )
        if not g["group_label"]:
            g["group_label"] = p.group_label
        g["permissions"].append(
            {
                "code": p.code,
                "label": p.label,
                "description": p.description,
            }
        )
    return [groups[g] for g in GROUP_ORDER if groups[g]["permissions"]]


def role_default_permissions(role: str) -> set[str]:
    return set(ROLE_DEFAULT_PERMISSIONS.get(role, frozenset()))


def parse_extra_permissions(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, str):
            continue
        code = item.strip()
        if code in PERMISSION_CODES and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def dump_extra_permissions(codes: Iterable[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for c in codes:
        if c in PERMISSION_CODES and c not in seen:
            seen.add(c)
            cleaned.append(c)
    return json.dumps(cleaned, ensure_ascii=False)


def get_user_extra_permissions(user: User) -> set[str]:
    raw = getattr(user, "extra_permissions", None)
    return set(parse_extra_permissions(raw))


def effective_permissions(user: User) -> set[str]:
    """Role defaults ∪ extra grants. Admin role always has full catalog."""
    if user.role == "admin":
        return set(PERMISSION_CODES)
    return role_default_permissions(user.role) | get_user_extra_permissions(user)


def has_permission(user: User, code: str) -> bool:
    if code not in PERMISSION_CODES:
        return False
    return code in effective_permissions(user)


def has_any_permission(user: User, codes: Iterable[str]) -> bool:
    eff = effective_permissions(user)
    return any(c in eff for c in codes)


def has_all_permissions(user: User, codes: Iterable[str]) -> bool:
    eff = effective_permissions(user)
    return all(c in eff for c in codes)


def validate_permission_codes(codes: Iterable[str]) -> tuple[list[str], str | None]:
    """Return (cleaned codes, error message)."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for c in codes:
        if not isinstance(c, str) or not c.strip():
            return [], "权限码无效"
        code = c.strip()
        if code not in PERMISSION_CODES:
            return [], f"未知权限：{code}"
        if code not in seen:
            seen.add(code)
            cleaned.append(code)
    return cleaned, None


def user_permission_payload(user: User) -> dict:
    role_defaults = sorted(role_default_permissions(user.role))
    extra = parse_extra_permissions(getattr(user, "extra_permissions", None))
    # Admin: extras unused; effective is full set
    if user.role == "admin":
        effective = sorted(PERMISSION_CODES)
        extra = []
    else:
        effective = sorted(set(role_defaults) | set(extra))
    return {
        "role": user.role,
        "role_defaults": role_defaults,
        "extra_permissions": extra,
        "effective_permissions": effective,
    }
