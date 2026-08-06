from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.storage import Storage
from app.core.timeutil import now as _utcnow
from app.models.academic import Course
from app.models.enrollment import EnrollmentRecord
from app.models.finance import FinanceOrder, FinanceTransaction
from app.models.student import Student
from app.models.user import User
from app.modules.academic import service as academic_svc
from app.modules.enrollments.schemas import PAY_METHOD_OPTIONS

def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (TypeError, json.JSONDecodeError):
        return []

def generate_order_no(db: Session, *, kind: str = "enroll") -> str:
    """生成业务订单号：EN/RN + yyyymmdd + 6 位随机，冲突则重试。"""
    prefix = "EN" if kind == "enroll" else "RN"
    day = _utcnow().strftime("%Y%m%d")
    for _ in range(12):
        no = f"{prefix}{day}{uuid.uuid4().hex[:6].upper()}"
        exists = (
            db.query(EnrollmentRecord.id).filter(EnrollmentRecord.order_no == no).first()
            or db.query(FinanceOrder.id).filter(FinanceOrder.order_no == no).first()
        )
        if not exists:
            return no
    return f"{prefix}{day}{uuid.uuid4().hex[:10].upper()}"

def record_to_dict(db: Session, row: EnrollmentRecord) -> dict:
    student = db.get(Student, row.student_id)
    creator = db.get(User, row.created_by) if row.created_by else None
    order = (
        db.query(FinanceOrder.id)
        .filter(FinanceOrder.enrollment_id == row.id)
        .order_by(FinanceOrder.id.desc())
        .first()
    )
    return {
        "id": row.id,
        "order_id": order[0] if order else None,
        "student_id": row.student_id,
        "student_name": student.name if student else None,
        "student_grade": student.grade if student else None,
        "student_phone": student.phone if student else None,
        "kind": row.kind,
        "handled_at": row.handled_at,
        "amount": float(row.amount or 0),
        "order_no": getattr(row, "order_no", None) or "",
        "pay_methods": _parse_json_list(getattr(row, "pay_methods", None)),
        "pay_other": getattr(row, "pay_other", None) or "",
        "courses": _parse_json_list(getattr(row, "courses", None)),
        "attributions": _parse_json_list(row.attributions),
        "internal_notes": row.internal_notes or "",
        "external_notes": row.external_notes or "",
        "internal_images": _parse_json_list(row.internal_images),
        "created_by": row.created_by,
        "created_by_name": (creator.display_name or creator.username) if creator else None,
        "created_at": row.created_at,
    }

def list_records(
    db: Session,
    *,
    student_id: int | None = None,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 20,
    viewer: User | None = None,
) -> dict:
    from app.core.roles import managed_student_ids

    q = db.query(EnrollmentRecord)
    scope = managed_student_ids(db, viewer) if viewer is not None else None
    if scope is not None:
        if not scope:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        q = q.filter(EnrollmentRecord.student_id.in_(scope))
    if student_id is not None:
        if scope is not None and student_id not in scope:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        q = q.filter(EnrollmentRecord.student_id == student_id)
    if kind:
        q = q.filter(EnrollmentRecord.kind == kind)
    total = q.count()
    rows = (
        q.order_by(EnrollmentRecord.handled_at.desc(), EnrollmentRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [record_to_dict(db, r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

def create_record(db: Session, user: User, data: dict) -> EnrollmentRecord | str:
    from app.core.roles import managed_student_ids

    student = db.get(Student, data["student_id"])
    if not student:
        return "学员不存在"
    scope = managed_student_ids(db, user)
    if scope is not None and student.id not in scope:
        return "仅可为自己绑定的学员办理报名/续费"

    kind = data.get("kind") or "enroll"
    if kind not in {"enroll", "renew"}:
        return "类型须为报名或续费"

    courses_in = data.get("courses") or []
    if not courses_in:
        return "请至少选择一门关联课程"
    if len(courses_in) > 20:
        return "关联课程最多 20 门"

    handled_at = data.get("handled_at") or _utcnow()
    courses: list[dict] = []
    seen_course_ids: set[int] = set()
    for item in courses_in:
        name = str(item.get("name") or "").strip()
        cid = item.get("id")
        course_obj: Course | None = None
        if cid is not None:
            try:
                course_obj = db.get(Course, int(cid))
            except (TypeError, ValueError):
                course_obj = None
            if not course_obj:
                return f"课程 {cid} 不存在"
            if not course_obj.enabled:
                return f"课程「{course_obj.name}」已停用，不能报名或续费"
            if course_obj.id in seen_course_ids:
                return f"课程「{course_obj.name}」重复选择"
            seen_course_ids.add(course_obj.id)
            name = course_obj.name
        if not name:
            return "课程名称不能为空"
        hours = float(item.get("hours") or 10)
        if hours <= 0:
            return "购课时数须大于 0"
        unit_price = item.get("unit_price")
        if unit_price is None and course_obj is not None:
            unit_price = float(course_obj.unit_price or 0)
        unit_price = float(unit_price or 0)
        type_label = str(item.get("type") or "").strip()
        if not type_label and course_obj is not None:
            type_label = "一对一" if course_obj.course_type == "one_to_one" else "一对多"
        price_label = str(item.get("price_label") or "").strip()
        if not price_label and unit_price:
            price_label = f"单价({unit_price:g}元/课时)"
        total = hours * unit_price
        discount_type = str(item.get("discount_type") or "reduce")
        discount_value = float(item.get("discount_value") or 0)
        if discount_type == "rate":
            if discount_value > 10:
                return f"课程「{name}」折扣不能大于 10 折"
            discount = total * (1 - discount_value / 10)
        else:
            discount = discount_value or float(item.get("discount") or 0)
        course_row: dict = {
            "name": name[:128],
            "type": type_label[:32],
            "price_label": price_label[:128],
            "hours": hours,
            "unit_price": unit_price,
            "gift_hours": float(item.get("gift_hours") or 0),
            "price_standard": str(item.get("price_standard") or price_label)[:128],
            "discount_type": discount_type,
            "discount_value": discount_value,
            "discount": round(discount, 2),
        }
        if course_row["discount"] > total:
            return f"课程「{name}」优惠金额不能大于课程总价"
        course_row["subtotal"] = max(
            0.0,
            round(hours * unit_price - course_row["discount"], 2),
        )
        if course_obj is not None:
            course_row["id"] = course_obj.id
        elif cid is not None:
            try:
                course_row["id"] = int(cid)
            except (TypeError, ValueError):
                pass
        courses.append(course_row)

    attrs_in = data.get("attributions") or []
    if len(attrs_in) > 10:
        return "业绩归属人最多 10 人"

    attributions: list[dict] = []
    for item in attrs_in:
        uid = int(item["user_id"])
        staff = db.get(User, uid)
        if not staff or staff.deleted_at is not None:
            return f"业绩归属人 {uid} 不存在"
        amount = float(item.get("amount") or 0)
        if amount < 0:
            return "销售业绩不能为负数"
        attributions.append(
            {
                "user_id": uid,
                "display_name": staff.display_name or staff.username,
                "amount": amount,
            }
        )

    images = list(data.get("internal_images") or [])
    if len(images) > 3:
        return "对内备注图片最多 3 张"

    # 支付方式
    raw_methods = data.get("pay_methods") or []
    if not isinstance(raw_methods, list) or not raw_methods:
        return "请至少选择一种支付方式"
    pay_methods: list[str] = []
    for m in raw_methods:
        label = str(m or "").strip()
        if label not in PAY_METHOD_OPTIONS:
            return f"不支持的支付方式：{label}"
        if label not in pay_methods:
            pay_methods.append(label)
    pay_other = (data.get("pay_other") or "").strip()
    if "其他" in pay_methods and not pay_other:
        return "选择「其他」支付方式时请填写说明"
    if "其他" not in pay_methods:
        pay_other = ""

    payments_in = data.get("payments") or []
    payments: list[dict] = []
    for item in payments_in:
        method = str(item.get("method") or "").strip()
        if method not in pay_methods:
            return f"支付明细中的方式未勾选：{method}"
        payment_amount = float(item.get("amount") or 0)
        if payment_amount < 0:
            return "实收金额不能为负数"
        if payment_amount > 0:
            payments.append({"method": method, "amount": payment_amount})

    amount = float(data.get("amount") or 0)
    if amount <= 0 and attributions:
        amount = sum(float(a["amount"]) for a in attributions)
    if attributions and abs(sum(float(a["amount"]) for a in attributions) - amount) >= 0.01:
        return "销售业绩合计必须等于应收金额"
    received = sum(float(p["amount"]) for p in payments)
    # 兼容旧客户端：未传支付明细时，勾选的首个方式承担全额实收。
    if not payments_in and amount > 0:
        received = amount
        payments = [{"method": pay_methods[0], "amount": amount}]
    if received > amount:
        return "实收金额不能大于应收金额"
    arrears = max(0.0, amount - received)

    order_no = generate_order_no(db, kind=kind)
    pay_label = "、".join(pay_methods)
    if pay_other:
        pay_label = f"{pay_label}（{pay_other}）"

    row = EnrollmentRecord(
        student_id=student.id,
        kind=kind,
        handled_at=handled_at,
        amount=amount,
        order_no=order_no,
        pay_methods=json.dumps(pay_methods, ensure_ascii=False),
        pay_other=pay_other[:128],
        courses=json.dumps(courses, ensure_ascii=False),
        attributions=json.dumps(attributions, ensure_ascii=False),
        internal_notes=(data.get("internal_notes") or "").strip(),
        external_notes=(data.get("external_notes") or "").strip(),
        internal_images=json.dumps(images, ensure_ascii=False),
        created_by=user.id,
    )
    db.add(row)
    db.flush()  # 拿到 enrollment id 再写财务订单

    # 同步财务订单 + 待确认收支
    kind_label = "报名" if kind == "enroll" else "续费"
    course_names = "、".join(c["name"] for c in courses) or kind_label
    perf_owner = attributions[0]["user_id"] if attributions else None
    handled_dt = handled_at if isinstance(handled_at, datetime) else _utcnow()
    order = FinanceOrder(
        order_no=order_no,
        student_id=student.id,
        order_type=kind,
        item_summary=course_names[:500],
        courses=json.dumps(courses, ensure_ascii=False),
        receivable=amount,
        received=received,
        arrears=arrears,
        status=(
            "unpaid"
            if amount <= 0
            else "paid"
            if arrears <= 0
            else "partial"
            if received > 0
            else "unpaid"
        ),
        source="机构创建",
        performance_owner_id=perf_owner,
        handler_id=user.id,
        enrollment_id=row.id,
        pay_method=pay_label[:64],
        handled_at=handled_dt,
        paid_at=_utcnow() if received > 0 else None,
        created_by=user.id,
    )
    db.add(order)
    db.flush()
    try:
        from app.modules.finance.service import add_order_log

        add_order_log(
            db,
            order_id=order.id,
            action="create",
            user=user,
            detail=f"{kind_label}生成订单 {order_no}，金额 {amount:.2f}，支付 {pay_label}",
        )
    except Exception:
        pass

    for payment in payments:
        db.add(
            FinanceTransaction(
                handled_at=handled_dt,
                item="报名/续费",
                tx_type="income",
                status="pending",
                amount=float(payment["amount"]),
                pay_method=str(payment["method"]),
                handler_id=user.id,
                order_id=order.id,
                student_id=student.id,
                payer_name=student.name,
                remark=pay_label,
                created_by=user.id,
            )
        )

    # 写入课包；一对一自动建班
    for c in courses:
        cid = c.get("id")
        if not cid:
            continue
        course_obj = db.get(Course, int(cid))
        if not course_obj:
            continue
        purchased_hours = float(c.get("hours") or 10)
        gift_hours = float(c.get("gift_hours") or 0)
        hours = purchased_hours + gift_hours
        unit_price = float(c.get("unit_price") or course_obj.unit_price or 0)
        academic_svc.grant_course_package(
            db,
            student_id=student.id,
            course_id=course_obj.id,
            hours=hours,
            purchased_hours=purchased_hours,
            gift_hours=gift_hours,
            unit_price=unit_price,
            enrollment_id=row.id,
        )
        academic_svc.ensure_one_to_one_class(
            db, student=student, course=course_obj, user=user
        )

    # 报名/续费后默认置为在读；同步关联课程到学员档案
    if student.status in {"paused", "quit", "graduated"} or kind == "enroll":
        student.status = "active"
        student.updated_at = _utcnow()
    existing_links = _parse_json_list(getattr(student, "linked_courses", None))
    merged_links: dict[str, dict] = {}
    for link in [*existing_links, *courses]:
        key = f"id:{link.get('id')}" if link.get("id") else f"name:{link.get('name', '')}"
        if key not in merged_links:
            merged_links[key] = dict(link)
        else:
            merged_links[key].update(link)
    student.linked_courses = json.dumps(list(merged_links.values()), ensure_ascii=False)
    # 对内备注仅保存在报名记录，不写入学员档案 notes

    db.commit()
    db.refresh(row)
    return row

def save_note_image(storage: Storage, data: bytes, content_type: str) -> str:
    ext = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get(content_type, "jpg")
    rel = f"enrollments/notes/{uuid.uuid4().hex}.{ext}"
    return storage.save(rel, data)
