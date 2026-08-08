"""
清库重测脚本：
- 清除全部业务数据
- 仅保留 role=admin 的负责人账号
- 写入 20 条线索 + 20 条学员
- 补 5 个学管师（CR）便于学员建档联调
- 恢复系统模板 / 示例知识库
- 其余业务列表不足 5 条的统一补到 5 条

用法（在 backend 目录）:
  python scripts/reset_demo_data.py
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 保证可从 backend/ 或项目根运行
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.timeutil import now as _utcnow
from app.models.lead import Lead
from app.models.student import Student
from app.models.user import User
from app.seed import (
    GIVEN,
    GRADES,
    LEAD_STATUSES,
    NEEDS,
    SCHOOLS,
    SOURCES,
    SURNAMES,
    seed_extra_crs,
    seed_demo_courses,
    seed_sample_knowledge,
    seed_system_templates,
)
from app.demo_seed import seed_demo_workspace

def main() -> None:
    db = SessionLocal()
    try:
        admins = (
            db.query(User)
            .filter(User.role == "admin", User.deleted_at.is_(None))
            .order_by(User.id.asc())
            .all()
        )
        if not admins:
            raise SystemExit("未找到负责人(admin)账号，中止清理")

        admin_ids = [a.id for a in admins]
        print("保留负责人:")
        for a in admins:
            print(f"  id={a.id}  username={a.username}  display={a.display_name}")

        # ── 清空业务表 + 非负责人用户 ──
        db.execute(text("PRAGMA foreign_keys = OFF"))
        tables = [
            r[0]
            for r in db.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ).fetchall()
        ]
        for t in tables:
            if t == "users":
                continue
            n = db.execute(text(f"DELETE FROM {t}")).rowcount
            print(f"  cleared {t}: {n}")

        non_admin = db.execute(
            text("DELETE FROM users WHERE role != :r"),
            {"r": "admin"},
        ).rowcount
        soft_admin = db.execute(
            text("DELETE FROM users WHERE role = :r AND deleted_at IS NOT NULL"),
            {"r": "admin"},
        ).rowcount
        print(f"  cleared non-admin users: {non_admin}")
        print(f"  cleared soft-deleted admins: {soft_admin}")
        db.commit()
        db.execute(text("PRAGMA foreign_keys = ON"))

        # ── 系统必备 ──
        seed_system_templates(db)
        seed_sample_knowledge(db)

        # 学管师：学员「学管师」字段需要 CR 账号
        seed_extra_crs(db, count=5)
        crs = (
            db.query(User)
            .filter(
                User.role == "cr",
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .order_by(User.id.asc())
            .all()
        )
        print("学管师账号 (密码=用户名):")
        for u in crs:
            print(f"  {u.username} / {u.display_name}")

        admin = db.get(User, admin_ids[0])

        # ── 20 条线索（覆盖近 20 天创建时间，便于按日观察）──
        rng = random.Random(20260804)
        for _ in range(20):
            day_offset = rng.randint(0, 19)
            created = _utcnow() - timedelta(days=day_offset, hours=rng.randint(0, 12))
            db.add(
                Lead(
                    student_or_parent_name=f"{rng.choice(SURNAMES)}{rng.choice(GIVEN)}家长",
                    phone=f"139{rng.randint(10000000, 99999999)}",
                    source=rng.choice(SOURCES),
                    referrer_name=rng.choice(["李同学", "王妈妈", "老学员", None]),
                    channel_note=rng.choice(["朋友圈", "地推", "转介绍", ""]),
                    need=rng.choice(NEEDS),
                    status=rng.choice(LEAD_STATUSES),
                    owner_id=admin.id if admin else None,
                    next_follow_at=_utcnow() + timedelta(days=rng.randint(-1, 7)),
                    notes=rng.choice(["已加微信", "待回访", "意向一般", ""]),
                    created_at=created,
                    updated_at=created,
                )
            )
        db.commit()

        # ── 20 条学员 ──
        statuses = ["active"] * 14 + ["paused"] * 3 + ["graduated"] * 3
        rng2 = random.Random(20260805)
        for i in range(20):
            m = crs[i % len(crs)] if crs else None
            db.add(
                Student(
                    name=f"{rng2.choice(SURNAMES)}{rng2.choice(GIVEN)}",
                    grade=rng2.choice(GRADES),
                    school=rng2.choice(SCHOOLS),
                    phone=f"138{rng2.randint(10000000, 99999999)}",
                    parent_name=f"{rng2.choice(SURNAMES)}妈妈",
                    academic_manager_id=m.id if m else None,
                    status=statuses[i % len(statuses)],
                    notes=rng2.choice(["注意力需加强", "作业习惯好", "家长沟通顺畅", ""]),
                    created_by=admin.id if admin else None,
                )
            )
        db.commit()

        # 课程、班级、排课、点名、报名、财务、素材、文案、海报、学情、
        # 待办等列表统一补齐；已有达到 5 条的表不会继续追加。
        seed_demo_courses(db)
        seed_demo_workspace(db)

        print("--- 结果 ---")
        users = (
            db.query(User)
            .filter(User.deleted_at.is_(None))
            .order_by(User.id.asc())
            .all()
        )
        print(f"users: {len(users)}")
        for u in users:
            print(f"  [{u.role}] {u.username} / {u.display_name}")
        print(f"leads: {db.query(Lead).count()}")
        print(f"students: {db.query(Student).count()}")
        for label, sql in (
            ("courses", "SELECT COUNT(*) FROM courses"),
            ("class_rooms", "SELECT COUNT(*) FROM class_rooms"),
            ("class_records", "SELECT COUNT(*) FROM class_records"),
            ("enrollment_records", "SELECT COUNT(*) FROM enrollment_records"),
            ("materials", "SELECT COUNT(*) FROM materials"),
        ):
            print(f"{label}: {db.execute(text(sql)).scalar()}")
        print("完成：可用负责人账号登录后开始重测。")
    finally:
        db.close()

if __name__ == "__main__":
    main()
