"""财务业务：订单、收支、课消、充值。"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.pagination import clamp_page, clamp_page_size, page_payload, paginate_query
from app.core.roles import managed_student_ids
from app.core.timeutil import now as _utcnow
from app.core.timeutil import today as business_today
from app.models.academic import (
    ClassAttendance,
    ClassMember,
    ClassRecord,
    ClassRoom,
    Course,
    StudentCoursePackage,
)
from app.models.enrollment import EnrollmentRecord
from app.models.finance import (
    CourseConsumption,
    FinanceOrder,
    FinanceTransaction,
    OrderOperationLog,
    RechargeRecord,
    StudentAccount,
)
from app.models.student import Student
from app.models.user import User

def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (TypeError, json.JSONDecodeError):
        return []

ORDER_TYPE_LABELS = {
    "enroll": "报名",
    "renew": "续费",
    "transfer": "转课",
    "drop": "退课",
    "recharge": "账户充值",
    "refund": "账户退款",
    "other": "其他",
}

ACTION_LABELS = {
    "create": "创建订单",
    "view": "查看订单",
    "print_receipt": "打印收据",
    "void": "作废订单",
    "update": "更新订单",
    "other": "其他操作",
}

def add_order_log(
    db: Session,
    *,
    order_id: int,
    action: str,
    user: User | None = None,
    detail: str = "",
    commit: bool = False,
) -> OrderOperationLog:
    """写入订单操作日志（默认不 commit，由调用方统一提交）。"""
    label = ACTION_LABELS.get(action, action)
    op_name = ""
    op_id = None
    if user is not None:
        op_id = user.id
        op_name = user.display_name or user.username or ""
    row = OrderOperationLog(
        order_id=order_id,
        action=action,
        action_label=label,
        detail=(detail or "").strip()[:2000],
        operator_id=op_id,
        operator_name=op_name,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row

def log_to_dict(row: OrderOperationLog) -> dict:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "action": row.action,
        "action_label": row.action_label or ACTION_LABELS.get(row.action, row.action),
        "detail": row.detail or "",
        "operator_id": row.operator_id,
        "operator_name": row.operator_name or "",
        "created_at": row.created_at,
    }

def list_order_logs(
    db: Session,
    order_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
) -> dict | str:
    order = db.get(FinanceOrder, order_id)
    if not order:
        return "订单不存在"
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    q = (
        db.query(OrderOperationLog)
        .filter(OrderOperationLog.order_id == order_id)
        .order_by(OrderOperationLog.id.desc())
    )
    rows, total = paginate_query(q, page=page, page_size=page_size)
    return page_payload(
        [log_to_dict(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )

def gen_order_no(db: Session) -> str:
    now = _utcnow()
    prefix = now.strftime("%Y%m%d%H%M%S")
    # 同秒内递增
    count = (
        db.query(FinanceOrder)
        .filter(FinanceOrder.order_no.like(f"{prefix}%"))
        .count()
    )
    return f"{prefix}{count + 1:04d}"

def _user_name(db: Session, uid: int | None) -> str:
    if not uid:
        return ""
    u = db.get(User, uid)
    if not u:
        return ""
    return u.display_name or u.username

def order_to_dict(db: Session, row: FinanceOrder) -> dict:
    student = db.get(Student, row.student_id)
    return {
        "id": row.id,
        "order_no": row.order_no,
        "student_id": row.student_id,
        "student": student.name if student else "",
        "phone": student.phone if student else "",
        "order_type": row.order_type,
        "order_type_label": ORDER_TYPE_LABELS.get(row.order_type, row.order_type),
        "item": row.item_summary or "",
        "item_summary": row.item_summary or "",
        "courses": _parse_json_list(row.courses),
        "receivable": float(row.receivable or 0),
        "received": float(row.received or 0),
        "arrears": float(row.arrears or 0),
        "status": row.status,
        "status_label": {
            "paid": "已支付",
            "partial": "部分支付",
            "unpaid": "未支付",
            "void": "已作废",
        }.get(row.status, row.status),
        "source": row.source or "",
        "performance_owner_id": row.performance_owner_id,
        "performance_owner": _user_name(db, row.performance_owner_id),
        "handler_id": row.handler_id,
        "handler": _user_name(db, row.handler_id),
        "enrollment_id": row.enrollment_id,
        "pay_method": row.pay_method or "",
        "handled_at": row.handled_at,
        "paid_at": row.paid_at,
        "creator": _user_name(db, row.created_by),
        "created_at": row.created_at,
    }

def _build_line_items(db: Session, row: FinanceOrder) -> list[dict]:
    """购买内容行：来自 courses 快照 + 课包课时。"""
    courses = _parse_json_list(row.courses)
    lines: list[dict] = []
    if not courses:
        # 充值等无课程订单
        if row.order_type == "recharge":
            lines.append(
                {
                    "name": row.item_summary or "账户充值",
                    "tag": "充值",
                    "price_label": "-",
                    "quantity_label": "1",
                    "total": float(row.receivable or 0),
                    "gift_qty": "-",
                    "leave_free": "-",
                    "discount": 0,
                    "subtotal": float(row.received or row.receivable or 0),
                    "coupon": "-",
                    "receivable": float(row.receivable or 0),
                    "class_name": "-",
                    "valid_until": "-",
                }
            )
        return lines

    n = len(courses)
    # 若行项目未带金额，按订单总额均分展示
    order_recv = float(row.receivable or 0)
    order_recv_each = (order_recv / n) if n else 0

    for c in courses:
        name = str(c.get("name") or "课程")
        hours = float(c.get("hours") or 0)
        unit = float(c.get("unit_price") or 0)
        if unit <= 0 and c.get("id"):
            course = db.get(Course, int(c["id"]))
            if course:
                unit = float(course.unit_price or 0)
        price_label = str(c.get("price_standard") or c.get("price_label") or "")
        if not price_label and unit:
            price_label = f"单价({unit:g}元/课时)"
        line_total = hours * unit if hours and unit else 0.0
        if line_total <= 0:
            line_total = order_recv_each
        qty_label = f"{hours:g}课时" if hours else "-"
        gift_hours = float(c.get("gift_hours") or 0)
        discount = float(c.get("discount") or 0)
        subtotal = float(c.get("subtotal") or max(0.0, line_total - discount))
        # 班级：一对一/班课关联
        class_name = "-"
        cid = c.get("id")
        if cid and row.student_id:
            cls = (
                db.query(ClassRoom)
                .filter(
                    ClassRoom.course_id == int(cid),
                    ClassRoom.primary_student_id == row.student_id,
                    ClassRoom.status == "active",
                )
                .first()
            )
            if not cls:
                # 班课：学员在成员里
                m = (
                    db.query(ClassMember)
                    .join(ClassRoom, ClassRoom.id == ClassMember.class_id)
                    .filter(
                        ClassMember.student_id == row.student_id,
                        ClassMember.status == "active",
                        ClassRoom.course_id == int(cid),
                        ClassRoom.status == "active",
                    )
                    .first()
                )
                if m:
                    cls = db.get(ClassRoom, m.class_id)
            if cls:
                class_name = cls.name

        tag = "报名"
        if row.order_type == "renew":
            tag = "续报"
        elif row.order_type == "recharge":
            tag = "充值"
        type_label = str(c.get("type") or "")
        if type_label:
            # 展示用
            pass

        lines.append(
            {
                "course_id": cid,
                "name": name,
                "tag": tag,
                "type": type_label,
                "price_label": price_label or "-",
                "quantity_label": qty_label,
                "hours": hours,
                "unit_price": unit,
                "total": round(line_total, 2),
                "gift_qty": f"{gift_hours:g}课时" if gift_hours else "-",
                "leave_free": "-",
                "discount": round(discount, 2),
                "subtotal": round(subtotal, 2),
                "coupon": "-",
                "receivable": round(subtotal, 2),
                "class_name": class_name,
                "valid_until": "-",
            }
        )
    return lines

def get_order_detail(db: Session, order_id: int) -> dict | str:
    row = db.get(FinanceOrder, order_id)
    if not row:
        return "订单不存在"
    base = order_to_dict(db, row)
    student = db.get(Student, row.student_id)
    base["student_grade"] = student.grade if student else ""
    base["student_school"] = student.school if student else ""
    base["parent_name"] = student.parent_name if student else ""
    base["gender"] = "-"  # 名册暂无性别字段

    internal_notes = ""
    external_notes = ""
    if row.enrollment_id:
        en = db.get(EnrollmentRecord, row.enrollment_id)
        if en:
            internal_notes = en.internal_notes or ""
            external_notes = en.external_notes or ""
    base["internal_notes"] = internal_notes
    base["external_notes"] = external_notes

    base["line_items"] = _build_line_items(db, row)
    base["line_receivable_sum"] = round(
        sum(float(x.get("receivable") or 0) for x in base["line_items"]), 2
    )

    pays = (
        db.query(FinanceTransaction)
        .filter(
            FinanceTransaction.order_id == row.id,
            FinanceTransaction.status != "void",
        )
        .order_by(FinanceTransaction.id.asc())
        .all()
    )
    base["payments"] = [tx_to_dict(db, p) for p in pays]
    return base

def get_order_detail_for_user(
    db: Session, order_id: int, user: User | None = None, *, log_view: bool = False
) -> dict | str:
    detail = get_order_detail(db, order_id)
    if isinstance(detail, str):
        return detail
    if user is not None:
        scope = managed_student_ids(db, user)
        if scope is not None:
            sid = detail.get("student_id")
            if sid is None or int(sid) not in scope:
                return "订单不存在或无权查看"
    if log_view and user is not None:
        add_order_log(
            db,
            order_id=order_id,
            action="view",
            user=user,
            detail=f"查看订单 {detail.get('order_no') or order_id}",
            commit=True,
        )
    return detail

def _sync_member_remain_hours(db: Session, student_id: int, course_id: int) -> None:
    """课包变更后同步班级成员剩余课时。"""
    pkgs = (
        db.query(StudentCoursePackage)
        .filter(
            StudentCoursePackage.student_id == student_id,
            StudentCoursePackage.course_id == course_id,
            StudentCoursePackage.status == "active",
        )
        .all()
    )
    remain = sum(float(p.remain_hours or 0) for p in pkgs)
    members = (
        db.query(ClassMember)
        .join(ClassRoom, ClassRoom.id == ClassMember.class_id)
        .filter(
            ClassMember.student_id == student_id,
            ClassMember.status == "active",
            ClassRoom.course_id == course_id,
        )
        .all()
    )
    for m in members:
        m.remain_hours = remain

def _revoke_packages_for_enrollment(db: Session, enrollment_id: int) -> int:
    """作废报名/续费订单时收回该报名写入的课包（剩余课时清零并标记 refunded）。"""
    pkgs = (
        db.query(StudentCoursePackage)
        .filter(
            StudentCoursePackage.enrollment_id == enrollment_id,
            StudentCoursePackage.status != "refunded",
        )
        .all()
    )
    n = 0
    for pkg in pkgs:
        pkg.remain_hours = 0.0
        pkg.status = "refunded"
        pkg.updated_at = _utcnow()
        _sync_member_remain_hours(db, pkg.student_id, pkg.course_id)
        n += 1
    return n

def _reverse_recharge_for_order(db: Session, order: FinanceOrder) -> str | None:
    """作废充值订单：扣回账户余额，充值记录标记 void。"""
    rows = (
        db.query(RechargeRecord)
        .filter(RechargeRecord.order_id == order.id, RechargeRecord.status != "void")
        .all()
    )
    if not rows:
        # 无充值明细时按订单实收回退
        amount = float(order.received or 0)
        if amount <= 0:
            return None
        acc = get_or_create_account(db, order.student_id)
        if float(acc.balance or 0) < amount - 1e-6:
            return f"账户余额不足，无法作废充值（余额 {acc.balance:g}，需回退 {amount:g}）"
        acc.balance = float(acc.balance or 0) - amount
        acc.updated_at = _utcnow()
        return None

    for r in rows:
        amount = float(r.amount or 0)
        if amount <= 0:
            r.status = "void"
            continue
        acc = get_or_create_account(db, r.student_id)
        if float(acc.balance or 0) < amount - 1e-6:
            return (
                f"账户余额不足，无法作废充值（余额 {float(acc.balance or 0):g}，"
                f"需回退 {amount:g}）"
            )
        acc.balance = float(acc.balance or 0) - amount
        acc.updated_at = _utcnow()
        r.status = "void"
    return None

def void_order(db: Session, order_id: int, user: User | None = None) -> dict | str:
    row = db.get(FinanceOrder, order_id)
    if not row:
        return "订单不存在"
    if user is not None:
        scope_err = assert_student_in_finance_scope(db, user, row.student_id)
        if scope_err:
            return scope_err
    if row.status == "void":
        return "订单已作废"

    extra_notes: list[str] = []

    # 充值单：先校验并回退余额
    if row.order_type == "recharge":
        err = _reverse_recharge_for_order(db, row)
        if err:
            return err
        extra_notes.append("已回退账户余额")

    # 报名/续费：收回关联课包
    if row.order_type in {"enroll", "renew"} and row.enrollment_id:
        revoked = _revoke_packages_for_enrollment(db, row.enrollment_id)
        if revoked:
            extra_notes.append(f"已收回 {revoked} 个课包")

    row.status = "void"
    # 关联收支一并作废
    for tx in db.query(FinanceTransaction).filter(FinanceTransaction.order_id == order_id).all():
        if tx.status != "void":
            tx.status = "void"

    detail_msg = f"作废订单 {row.order_no}，关联收支已同步作废"
    if extra_notes:
        detail_msg = f"{detail_msg}；" + "；".join(extra_notes)

    add_order_log(
        db,
        order_id=order_id,
        action="void",
        user=user,
        detail=detail_msg,
    )
    db.commit()
    db.refresh(row)
    return get_order_detail(db, order_id)

def list_orders(
    db: Session,
    *,
    order_no: str | None = None,
    student_q: str | None = None,
    order_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    viewer: User | None = None,
) -> dict:
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = db.query(FinanceOrder)
    scope = managed_student_ids(db, viewer) if viewer is not None else None
    if scope is not None:
        if not scope:
            return page_payload([], total=0, page=page, page_size=page_size)
        query = query.filter(FinanceOrder.student_id.in_(scope))
    if order_no:
        query = query.filter(FinanceOrder.order_no.contains(order_no.strip()))
    if order_type:
        query = query.filter(FinanceOrder.order_type == order_type)
    if student_q:
        qq = student_q.strip()
        sq = db.query(Student).filter((Student.name.contains(qq)) | (Student.phone.contains(qq)))
        if scope is not None:
            sq = sq.filter(Student.id.in_(scope))
        sids = [s.id for s in sq.all()]
        if not sids:
            return page_payload([], total=0, page=page, page_size=page_size)
        query = query.filter(FinanceOrder.student_id.in_(sids))
    query = query.order_by(FinanceOrder.id.desc())
    rows, total = paginate_query(query, page=page, page_size=page_size)
    return page_payload(
        [order_to_dict(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )

def create_order_from_enrollment(
    db: Session,
    *,
    user: User,
    student: Student,
    enrollment_id: int,
    kind: str,
    amount: float,
    courses: list[dict],
    handled_at: datetime | None,
    pay_method: str = "微信",
    performance_owner_id: int | None = None,
) -> FinanceOrder:
    """报名/续费落单 + 待确认收入。"""
    order_type = "enroll" if kind == "enroll" else "renew"
    names = [c.get("name") or "" for c in courses if c.get("name")]
    item = "；".join(names) if names else ORDER_TYPE_LABELS.get(order_type, order_type)
    for c in courses:
        pl = c.get("price_label") or ""
        if pl and c.get("name"):
            # 丰富摘要
            pass
    if courses:
        parts = []
        for c in courses:
            n = c.get("name") or ""
            pl = c.get("price_label") or ""
            parts.append(f"{n} {pl}".strip())
        item = "；".join(parts)

    order = FinanceOrder(
        order_no=gen_order_no(db),
        student_id=student.id,
        order_type=order_type,
        item_summary=item,
        courses=json.dumps(courses, ensure_ascii=False),
        receivable=float(amount or 0),
        received=float(amount or 0),
        arrears=0,
        status="paid" if amount and amount > 0 else "paid",
        source="机构创建",
        performance_owner_id=performance_owner_id or user.id,
        handler_id=user.id,
        enrollment_id=enrollment_id,
        pay_method=pay_method or "微信",
        handled_at=handled_at or _utcnow(),
        paid_at=_utcnow() if amount and amount > 0 else None,
        created_by=user.id,
    )
    db.add(order)
    db.flush()
    add_order_log(
        db,
        order_id=order.id,
        action="create",
        user=user,
        detail=f"报名/续费生成订单 {order.order_no}，金额 {_money_safe(amount)}",
    )

    if amount and amount > 0:
        db.add(
            FinanceTransaction(
                handled_at=handled_at or _utcnow(),
                item="报名/续费",
                tx_type="income",
                status="pending",
                amount=float(amount),
                pay_method=pay_method or "微信",
                account="",
                handler_id=user.id,
                order_id=order.id,
                student_id=student.id,
                payer_name=student.name,
                remark="",
                created_by=user.id,
            )
        )
    return order

def _money_safe(n) -> str:
    try:
        return f"{float(n or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"

def create_manual_order(db: Session, user: User, data: dict) -> FinanceOrder | str:
    student = db.get(Student, int(data["student_id"]))
    if not student:
        return "学员不存在"
    scope_err = assert_student_in_finance_scope(db, user, student.id)
    if scope_err:
        return scope_err
    receivable = float(data.get("receivable") or 0)
    received = float(data.get("received") or 0)
    arrears = max(0.0, receivable - received)
    status = "paid"
    if arrears > 0 and received > 0:
        status = "partial"
    elif received <= 0 and receivable > 0:
        status = "unpaid"
    order = FinanceOrder(
        order_no=gen_order_no(db),
        student_id=student.id,
        order_type=data.get("order_type") or "other",
        item_summary=(data.get("item_summary") or "").strip()
        or ORDER_TYPE_LABELS.get(data.get("order_type") or "other", "其他"),
        courses="[]",
        receivable=receivable,
        received=received,
        arrears=arrears,
        status=status,
        source="机构创建",
        performance_owner_id=data.get("performance_owner_id") or user.id,
        handler_id=user.id,
        pay_method=(data.get("pay_method") or "").strip(),
        handled_at=data.get("handled_at") or _utcnow(),
        paid_at=_utcnow() if received > 0 else None,
        created_by=user.id,
    )
    db.add(order)
    db.flush()
    add_order_log(
        db,
        order_id=order.id,
        action="create",
        user=user,
        detail=(
            f"手工建单 {order.order_no}，类型 {ORDER_TYPE_LABELS.get(order.order_type, order.order_type)}，"
            f"应收 {_money_safe(receivable)}，实收 {_money_safe(received)}"
        ),
    )
    if received > 0:
        item = "报名/续费"
        if order.order_type == "recharge":
            item = "账户充值"
        elif order.order_type in {"refund", "drop"}:
            item = "退费"
        db.add(
            FinanceTransaction(
                handled_at=order.handled_at or _utcnow(),
                item=item,
                tx_type="expense" if order.order_type in {"refund", "drop"} else "income",
                status="pending",
                amount=received,
                pay_method=order.pay_method or "微信",
                handler_id=user.id,
                order_id=order.id,
                student_id=student.id,
                payer_name=student.name,
                created_by=user.id,
            )
        )
    db.commit()
    db.refresh(order)
    return order

def tx_to_dict(db: Session, row: FinanceTransaction) -> dict:
    order = db.get(FinanceOrder, row.order_id) if row.order_id else None
    return {
        "id": row.id,
        "handled_at": row.handled_at,
        "item": row.item,
        "type": "收入" if row.tx_type == "income" else "支出",
        "tx_type": row.tx_type,
        "status": {"pending": "待确认", "confirmed": "已确认", "void": "已作废"}.get(
            row.status, row.status
        ),
        "status_code": row.status,
        "amount": float(row.amount or 0),
        "pay_method": row.pay_method or "",
        "account": row.account or "-",
        "handler": _user_name(db, row.handler_id),
        "order_id": row.order_id,
        "order_no": order.order_no if order else "",
        "student_id": row.student_id,
        "payer": row.payer_name or "",
        "voucher": row.voucher or "-",
        "flow_no": row.flow_no or "-",
        "remark": row.remark or "-",
        "created_at": row.created_at,
        "confirmed_at": row.confirmed_at,
    }

def list_transactions(
    db: Session,
    *,
    item: str | None = None,
    tx_type: str | None = None,
    status: str | None = None,
    include_void: bool = False,
    page: int = 1,
    page_size: int = 20,
    viewer: User | None = None,
) -> dict:
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    scope = managed_student_ids(db, viewer) if viewer is not None else None
    query = db.query(FinanceTransaction)
    if scope is not None:
        if not scope:
            empty = page_payload([], total=0, page=page, page_size=page_size)
            empty["summary"] = {
                "income": 0,
                "pending_income": 0,
                "expense": 0,
                "pending_expense": 0,
            }
            return empty
        query = query.filter(FinanceTransaction.student_id.in_(scope))
    if not include_void:
        query = query.filter(FinanceTransaction.status != "void")
    if item:
        query = query.filter(FinanceTransaction.item == item)
    if tx_type in {"income", "expense"}:
        query = query.filter(FinanceTransaction.tx_type == tx_type)
    if status:
        query = query.filter(FinanceTransaction.status == status)
    query = query.order_by(FinanceTransaction.handled_at.desc(), FinanceTransaction.id.desc())
    rows, total = paginate_query(query, page=page, page_size=page_size)

    # 汇总（当前筛选条件下，不分页）
    all_q = db.query(FinanceTransaction)
    if scope is not None:
        all_q = all_q.filter(FinanceTransaction.student_id.in_(scope))
    if not include_void:
        all_q = all_q.filter(FinanceTransaction.status != "void")
    if item:
        all_q = all_q.filter(FinanceTransaction.item == item)
    if tx_type in {"income", "expense"}:
        all_q = all_q.filter(FinanceTransaction.tx_type == tx_type)
    if status:
        all_q = all_q.filter(FinanceTransaction.status == status)
    all_rows = all_q.all()
    sum_income = sum(float(r.amount or 0) for r in all_rows if r.tx_type == "income" and r.status == "confirmed")
    sum_pending_income = sum(
        float(r.amount or 0) for r in all_rows if r.tx_type == "income" and r.status == "pending"
    )
    sum_expense = sum(float(r.amount or 0) for r in all_rows if r.tx_type == "expense" and r.status == "confirmed")
    sum_pending_expense = sum(
        float(r.amount or 0) for r in all_rows if r.tx_type == "expense" and r.status == "pending"
    )

    payload = page_payload(
        [tx_to_dict(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
    payload["summary"] = {
        "income": round(sum_income, 2),
        "pending_income": round(sum_pending_income, 2),
        "expense": round(sum_expense, 2),
        "pending_expense": round(sum_pending_expense, 2),
    }
    return payload

def confirm_transactions(db: Session, user: User, ids: list[int]) -> dict | str:
    if not ids:
        return "请选择记录"
    rows = db.query(FinanceTransaction).filter(FinanceTransaction.id.in_(ids)).all()
    if not rows:
        return "记录不存在"
    scope = managed_student_ids(db, user)
    n = 0
    for r in rows:
        if scope is not None and (r.student_id is None or int(r.student_id) not in scope):
            return "仅可操作自己绑定学员的收支"
        if r.status == "pending":
            r.status = "confirmed"
            r.confirmed_at = _utcnow()
            r.confirmed_by = user.id
            n += 1
    db.commit()
    return {"confirmed": n}

def void_transaction(
    db: Session, tx_id: int, user: User | None = None
) -> FinanceTransaction | str:
    row = db.get(FinanceTransaction, tx_id)
    if not row:
        return "记录不存在"
    if user is not None:
        if row.student_id is not None:
            scope_err = assert_student_in_finance_scope(db, user, row.student_id)
            if scope_err:
                return scope_err
    if row.status == "void":
        return "已作废"
    row.status = "void"
    db.commit()
    db.refresh(row)
    return row

def _status_label(status: str | None) -> str:
    return {"normal": "正常", "void": "已作废"}.get(status or "", status or "")

def _course_type_label(course_type: str | None) -> str:
    return {"group": "班课", "one_to_one": "一对一"}.get(course_type or "", course_type or "")

def _parse_ids(raw: str | None) -> list[int]:
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out: list[int] = []
    for item in data:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _teacher_names(db: Session, ids: list[int]) -> str:
    if not ids:
        return ""
    users = db.query(User).filter(User.id.in_(ids)).all()
    by_id = {u.id: (u.display_name or u.username) for u in users}
    return "、".join(by_id[i] for i in ids if i in by_id)


def _consumption_teacher_ids(db: Session, row: CourseConsumption) -> list[int]:
    """课消上课老师：优先取点名记录上的全部老师，其次落库的 teacher_id。"""
    if row.record_id:
        record = db.get(ClassRecord, row.record_id)
        if record:
            ids = _parse_ids(getattr(record, "teacher_ids", None))
            if ids:
                return ids
    if row.teacher_id:
        return [int(row.teacher_id)]
    return []


def consumption_to_dict(db: Session, row: CourseConsumption) -> dict:
    student = db.get(Student, row.student_id)
    cls = db.get(ClassRoom, row.class_id) if row.class_id else None
    course = db.get(Course, row.course_id) if row.course_id else None
    teacher_ids = _consumption_teacher_ids(db, row)
    hours = float(row.hours or 0)
    course_type = course.course_type if course else ""
    return {
        "id": row.id,
        "consumed_at": row.consumed_at,
        "student_id": row.student_id,
        "student": student.name if student else "",
        "student_phone": student.phone if student else "",
        "student_grade": student.grade if student else "",
        "class_id": row.class_id,
        "class_name": cls.name if cls else "",
        "course_id": row.course_id,
        "course_name": course.name if course else "",
        "course_type": course_type,
        "course_type_label": _course_type_label(course_type),
        "course_grade": course.grade if course else "",
        "subject": course.subject if course else "",
        "term": course.term if course else "",
        # 展示该课次全部上课老师（与点名/排课一致），不再只显示第一位
        "teacher": _teacher_names(db, teacher_ids),
        "teacher_id": teacher_ids[0] if teacher_ids else row.teacher_id,
        "teacher_ids": teacher_ids,
        "record_id": row.record_id,
        "consume_type": row.consume_type,
        "source": row.source,
        "hours": hours,
        "hours_label": f"消耗{hours:g}课时",
        "uncovered_hours": float(getattr(row, "uncovered_hours", 0) or 0),
        "amount": float(row.amount or 0),
        "status": row.status,
        "status_label": _status_label(row.status),
        "created_at": row.created_at,
    }

def _date_start(d: date | None) -> datetime | None:
    return datetime.combine(d, time.min) if d else None

def _date_end_exclusive(d: date | None) -> datetime | None:
    return datetime.combine(d + timedelta(days=1), time.min) if d else None

def _apply_consumption_filters(
    db: Session,
    query,
    *,
    student_q: str | None = None,
    class_id: int | None = None,
    course_id: int | None = None,
    course_type: str | None = None,
    teacher_id: int | None = None,
    consume_type: str | None = None,
    source: str | None = None,
    status: str | None = None,
    hide_void: bool = True,
    start_date: date | None = None,
    end_date: date | None = None,
    grade: str | None = None,
    subject: str | None = None,
    term: str | None = None,
    student_ids: set[int] | None = None,
):
    if student_ids is not None:
        if not student_ids:
            return query.filter(CourseConsumption.id == -1)
        query = query.filter(CourseConsumption.student_id.in_(student_ids))
    if hide_void:
        query = query.filter(CourseConsumption.status != "void")
    if status:
        query = query.filter(CourseConsumption.status == status)
    if class_id:
        query = query.filter(CourseConsumption.class_id == class_id)
    if course_id:
        query = query.filter(CourseConsumption.course_id == course_id)
    if teacher_id:
        # 匹配落库首位老师，或点名记录 teacher_ids 含该老师的课消
        from sqlalchemy import or_

        record_rows = db.query(ClassRecord.id, ClassRecord.teacher_ids).all()
        matched_record_ids = [
            rid for rid, raw in record_rows if teacher_id in _parse_ids(raw)
        ]
        if matched_record_ids:
            query = query.filter(
                or_(
                    CourseConsumption.teacher_id == teacher_id,
                    CourseConsumption.record_id.in_(matched_record_ids),
                )
            )
        else:
            query = query.filter(CourseConsumption.teacher_id == teacher_id)
    if consume_type:
        query = query.filter(CourseConsumption.consume_type == consume_type)
    if source:
        query = query.filter(CourseConsumption.source == source)
    start_dt = _date_start(start_date)
    end_dt = _date_end_exclusive(end_date)
    if start_dt:
        query = query.filter(CourseConsumption.consumed_at >= start_dt)
    if end_dt:
        query = query.filter(CourseConsumption.consumed_at < end_dt)
    if student_q:
        qq = student_q.strip()
        sq = db.query(Student).filter((Student.name.contains(qq)) | (Student.phone.contains(qq)))
        if student_ids is not None:
            sq = sq.filter(Student.id.in_(student_ids))
        sids = [s.id for s in sq.all()]
        if not sids:
            return query.filter(CourseConsumption.id == -1)
        query = query.filter(CourseConsumption.student_id.in_(sids))
    course_filters = []
    if course_type:
        course_filters.append(Course.course_type == course_type)
    if grade:
        course_filters.append(Course.grade == grade)
    if subject:
        course_filters.append(Course.subject == subject)
    if term:
        course_filters.append(Course.term == term)
    if course_filters:
        cids = [r[0] for r in db.query(Course.id).filter(*course_filters).all()]
        if not cids:
            return query.filter(CourseConsumption.id == -1)
        query = query.filter(CourseConsumption.course_id.in_(cids))
    return query

def list_consumptions(
    db: Session,
    *,
    student_q: str | None = None,
    class_id: int | None = None,
    course_id: int | None = None,
    course_type: str | None = None,
    teacher_id: int | None = None,
    consume_type: str | None = None,
    source: str | None = None,
    status: str | None = None,
    hide_void: bool = True,
    start_date: date | None = None,
    end_date: date | None = None,
    grade: str | None = None,
    subject: str | None = None,
    term: str | None = None,
    page: int = 1,
    page_size: int = 20,
    viewer: User | None = None,
) -> dict:
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    scope = managed_student_ids(db, viewer) if viewer is not None else None
    filter_kwargs = {
        "student_q": student_q,
        "class_id": class_id,
        "course_id": course_id,
        "course_type": course_type,
        "teacher_id": teacher_id,
        "consume_type": consume_type,
        "source": source,
        "status": status,
        "hide_void": hide_void,
        "start_date": start_date,
        "end_date": end_date,
        "grade": grade,
        "subject": subject,
        "term": term,
        "student_ids": scope,
    }
    query = _apply_consumption_filters(db, db.query(CourseConsumption), **filter_kwargs)
    query = query.order_by(CourseConsumption.consumed_at.desc(), CourseConsumption.id.desc())
    rows, total = paginate_query(query, page=page, page_size=page_size)

    sum_q = _apply_consumption_filters(
        db,
        db.query(func.coalesce(func.sum(CourseConsumption.amount), 0)),
        **filter_kwargs,
    )
    total_amount = float(sum_q.scalar() or 0)

    payload = page_payload(
        [consumption_to_dict(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
    payload["summary"] = {"amount": round(total_amount, 2)}
    return payload

def _package_order_info(db: Session, package: StudentCoursePackage | None) -> tuple[int | None, str]:
    if not package:
        return None, ""
    if not package.enrollment_id:
        return None, f"PKG-{package.id}"
    enrollment = db.get(EnrollmentRecord, package.enrollment_id)
    order_no = getattr(enrollment, "order_no", None) or ""
    order = (
        db.query(FinanceOrder)
        .filter(FinanceOrder.enrollment_id == package.enrollment_id)
        .first()
    )
    if order:
        return order.id, order.order_no or order_no
    return None, order_no or f"PKG-{package.id}"

def consumption_detail_to_dict(db: Session, row: CourseConsumption) -> dict:
    data = consumption_to_dict(db, row)
    record = db.get(ClassRecord, row.record_id) if row.record_id else None
    attendance = (
        db.query(ClassAttendance)
        .filter(
            ClassAttendance.record_id == row.record_id,
            ClassAttendance.student_id == row.student_id,
        )
        .first()
        if row.record_id
        else None
    )
    creator = db.get(User, row.created_by) if row.created_by else None
    allocations = _parse_json_list(getattr(row, "package_allocations", None))
    orders: list[dict] = []
    for allocation in allocations:
        package_id = allocation.get("package_id")
        package = db.get(StudentCoursePackage, int(package_id)) if package_id else None
        course = db.get(Course, package.course_id) if package else (db.get(Course, row.course_id) if row.course_id else None)
        order_id, order_no = _package_order_info(db, package)
        hours = float(allocation.get("hours") or 0)
        amount = float(allocation.get("amount") or 0)
        unit_price = float(package.unit_price if package else (course.unit_price if course else 0) or 0)
        orders.append(
            {
                "package_id": package_id,
                "order_id": order_id,
                "order_no": order_no,
                "course_name": course.name if course else data.get("course_name", ""),
                "unit_price": unit_price,
                "hours": hours,
                "gift_hours": 0,
                "amount": amount,
            }
        )
    if data["uncovered_hours"] > 0:
        course = db.get(Course, row.course_id) if row.course_id else None
        unit_price = float(course.unit_price or 0) if course else 0
        orders.append(
            {
                "package_id": None,
                "order_id": None,
                "order_no": "课包余额不足",
                "course_name": data.get("course_name", ""),
                "unit_price": unit_price,
                "hours": data["uncovered_hours"],
                "gift_hours": 0,
                "amount": round(data["uncovered_hours"] * unit_price, 2),
            }
        )
    data.update(
        {
            "class_start": record.class_start if record else None,
            "class_end": record.class_end if record else None,
            "roll_at": record.roll_at if record else None,
            "attendance_status": attendance.status if attendance else "",
            "attendance_status_label": {
                "present": "到课",
                "absent": "缺勤",
                "leave": "请假",
                "late": "迟到",
            }.get(attendance.status if attendance else "", ""),
            "operator": (creator.display_name or creator.username) if creator else "",
            "operation_time": row.created_at,
            "orders": orders,
        }
    )
    return data

def get_consumption_detail(
    db: Session, consumption_id: int, viewer: User | None = None
) -> dict | str:
    row = db.get(CourseConsumption, consumption_id)
    if not row:
        return "课消记录不存在"
    if viewer is not None:
        scope_err = assert_student_in_finance_scope(db, viewer, row.student_id)
        if scope_err:
            return "课消记录不存在或无权查看"
    return consumption_detail_to_dict(db, row)

def get_or_create_account(db: Session, student_id: int) -> StudentAccount:
    acc = db.query(StudentAccount).filter(StudentAccount.student_id == student_id).first()
    if acc:
        return acc
    acc = StudentAccount(student_id=student_id, balance=0)
    db.add(acc)
    db.flush()
    return acc

def recharge_to_dict(db: Session, row: RechargeRecord) -> dict:
    student = db.get(Student, row.student_id)
    return {
        "id": row.id,
        "student_id": row.student_id,
        "student": student.name if student else "",
        "phone": student.phone if student else "",
        "amount": float(row.amount or 0),
        "balance": float(row.balance_after or 0),
        "pay_method": row.pay_method or "",
        "handler": _user_name(db, row.handler_id),
        "status": "成功" if row.status == "success" else row.status,
        "remark": row.remark or "",
        "created_at": row.created_at,
    }

def list_recharges(
    db: Session,
    *,
    student_q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    viewer: User | None = None,
) -> dict:
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = db.query(RechargeRecord)
    scope = managed_student_ids(db, viewer) if viewer is not None else None
    if scope is not None:
        if not scope:
            return page_payload([], total=0, page=page, page_size=page_size)
        query = query.filter(RechargeRecord.student_id.in_(scope))
    if student_q:
        qq = student_q.strip()
        sq = db.query(Student).filter((Student.name.contains(qq)) | (Student.phone.contains(qq)))
        if scope is not None:
            sq = sq.filter(Student.id.in_(scope))
        sids = [s.id for s in sq.all()]
        if not sids:
            return page_payload([], total=0, page=page, page_size=page_size)
        query = query.filter(RechargeRecord.student_id.in_(sids))
    query = query.order_by(RechargeRecord.id.desc())
    rows, total = paginate_query(query, page=page, page_size=page_size)
    return page_payload(
        [recharge_to_dict(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )

def assert_student_in_finance_scope(db: Session, user: User, student_id: int) -> str | None:
    """返回错误文案；None 表示可操作该学员。"""
    scope = managed_student_ids(db, user)
    if scope is None:
        return None
    if int(student_id) not in scope:
        return "仅可操作自己绑定的学员"
    return None

def create_recharge(db: Session, user: User, data: dict) -> RechargeRecord | str:
    student = db.get(Student, int(data["student_id"]))
    if not student:
        return "学员不存在"
    scope_err = assert_student_in_finance_scope(db, user, student.id)
    if scope_err:
        return scope_err
    amount = float(data.get("amount") or 0)
    if amount <= 0:
        return "充值金额须大于 0"
    acc = get_or_create_account(db, student.id)
    acc.balance = float(acc.balance or 0) + amount
    acc.updated_at = _utcnow()

    order = FinanceOrder(
        order_no=gen_order_no(db),
        student_id=student.id,
        order_type="recharge",
        item_summary=f"账户充值 {amount:.2f} 元",
        courses="[]",
        receivable=amount,
        received=amount,
        arrears=0,
        status="paid",
        source="机构创建",
        performance_owner_id=user.id,
        handler_id=user.id,
        pay_method=(data.get("pay_method") or "微信").strip(),
        handled_at=_utcnow(),
        paid_at=_utcnow(),
        created_by=user.id,
    )
    db.add(order)
    db.flush()
    add_order_log(
        db,
        order_id=order.id,
        action="create",
        user=user,
        detail=f"账户充值订单 {order.order_no}，金额 {_money_safe(amount)}，方式 {order.pay_method}",
    )

    db.add(
        FinanceTransaction(
            handled_at=_utcnow(),
            item="账户充值",
            tx_type="income",
            status="pending",
            amount=amount,
            pay_method=order.pay_method,
            handler_id=user.id,
            order_id=order.id,
            student_id=student.id,
            payer_name=student.name,
            created_by=user.id,
        )
    )

    row = RechargeRecord(
        student_id=student.id,
        amount=amount,
        balance_after=float(acc.balance),
        pay_method=order.pay_method,
        handler_id=user.id,
        order_id=order.id,
        status="success",
        remark=(data.get("remark") or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def _date_range_bounds(start_date: date | None = None, end_date: date | None = None) -> tuple[datetime | None, datetime | None]:
    start_dt = datetime.combine(start_date, time.min) if start_date else None
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min) if end_date else None
    return start_dt, end_dt

def _legacy_income_report(db: Session, *, start_date: date | None = None, end_date: date | None = None) -> dict:
    start_dt, end_dt = _date_range_bounds(start_date, end_date)
    query = db.query(FinanceTransaction).filter(
        FinanceTransaction.tx_type == "income",
        FinanceTransaction.status != "void",
    )
    if start_dt:
        query = query.filter(FinanceTransaction.handled_at >= start_dt)
    if end_dt:
        query = query.filter(FinanceTransaction.handled_at < end_dt)
    rows = query.all()
    pending = sum(float(r.amount or 0) for r in rows if r.status == "pending")
    confirmed = sum(float(r.amount or 0) for r in rows if r.status == "confirmed")
    by_method: dict[str, dict] = {}
    daily: dict[str, dict] = {}
    for r in rows:
        if r.status not in {"pending", "confirmed"}:
            continue
        m = r.pay_method or "其他"
        cur = by_method.setdefault(m, {"method": m, "count": 0, "amount": 0.0})
        cur["count"] += 1
        cur["amount"] += float(r.amount or 0)
    methods = sorted(by_method.values(), key=lambda x: -x["amount"])
    for m in methods:
        m["amount"] = round(m["amount"], 2)
    return {
        "pending_income": round(pending, 2),
        "confirmed_income": round(confirmed, 2),
        "total_income": round(pending + confirmed, 2),
        "by_pay_method": methods,
    }

def income_report(db: Session, *, start_date: date | None = None, end_date: date | None = None) -> dict:
    start_dt, end_dt = _date_range_bounds(start_date, end_date)
    query = db.query(FinanceTransaction).filter(
        FinanceTransaction.tx_type == "income",
        FinanceTransaction.status != "void",
    )
    if start_dt:
        query = query.filter(FinanceTransaction.handled_at >= start_dt)
    if end_dt:
        query = query.filter(FinanceTransaction.handled_at < end_dt)
    rows = query.all()

    pending = sum(float(r.amount or 0) for r in rows if r.status == "pending")
    confirmed = sum(float(r.amount or 0) for r in rows if r.status == "confirmed")
    by_method: dict[str, dict] = {}
    daily: dict[str, dict] = {}
    for r in rows:
        if r.status not in {"pending", "confirmed"}:
            continue
        amount = float(r.amount or 0)
        method = r.pay_method or "其他"
        cur = by_method.setdefault(method, {"method": method, "count": 0, "amount": 0.0})
        cur["count"] += 1
        cur["amount"] += amount

        day = (r.handled_at or r.created_at).date().isoformat()
        day_row = daily.setdefault(day, {"date": day, "pending": 0.0, "confirmed": 0.0, "total": 0.0})
        day_row[r.status] += amount
        day_row["total"] += amount

    methods = sorted(by_method.values(), key=lambda x: -x["amount"])
    for item in methods:
        item["amount"] = round(item["amount"], 2)

    chart = sorted(daily.values(), key=lambda x: x["date"])
    for item in chart:
        item["pending"] = round(item["pending"], 2)
        item["confirmed"] = round(item["confirmed"], 2)
        item["total"] = round(item["total"], 2)

    consume_query = db.query(CourseConsumption).filter(CourseConsumption.status != "void")
    if start_dt:
        consume_query = consume_query.filter(CourseConsumption.consumed_at >= start_dt)
    if end_dt:
        consume_query = consume_query.filter(CourseConsumption.consumed_at < end_dt)
    consume_rows = consume_query.all()
    by_course: dict[str, dict] = {}
    consume_daily: dict[str, dict] = {}
    for r in consume_rows:
        amount = float(r.amount or 0)
        hours = float(r.hours or 0)
        day = (r.consumed_at or r.created_at).date().isoformat()
        day_row = consume_daily.setdefault(day, {"date": day, "hours": 0.0, "amount": 0.0, "count": 0})
        day_row["hours"] += hours
        day_row["amount"] += amount
        day_row["count"] += 1
        course = db.get(Course, r.course_id) if r.course_id else None
        course_name = course.name if course else "未关联课程"
        cur = by_course.setdefault(
            course_name,
            {
                "course_name": course_name,
                "course_type": course.course_type if course else "",
                "course_type_label": _course_type_label(course.course_type if course else ""),
                "count": 0,
                "hours": 0.0,
                "amount": 0.0,
            },
        )
        cur["count"] += 1
        cur["hours"] += hours
        cur["amount"] += amount

    course_rows = sorted(by_course.values(), key=lambda x: -x["amount"])
    for item in course_rows:
        item["hours"] = round(item["hours"], 2)
        item["amount"] = round(item["amount"], 2)
    consume_chart = sorted(consume_daily.values(), key=lambda x: x["date"])
    for item in consume_chart:
        item["hours"] = round(item["hours"], 2)
        item["amount"] = round(item["amount"], 2)

    return {
        "pending_income": round(pending, 2),
        "confirmed_income": round(confirmed, 2),
        "total_income": round(pending + confirmed, 2),
        "by_pay_method": methods,
        "income_chart": chart,
        "course_consumption": {
            "total_hours": round(sum(float(r.hours or 0) for r in consume_rows), 2),
            "total_amount": round(sum(float(r.amount or 0) for r in consume_rows), 2),
            "total_count": len(consume_rows),
            "chart": consume_chart,
            "by_course": course_rows,
        },
    }

def pending_hours_report(db: Session) -> dict:
    """Return the institution's current unconsumed-hours position.

    Refunded packages are excluded. Exhausted packages remain in the denominator so
    the consumption rate represents the full delivery history, not only open packages.
    """
    rows = (
        db.query(StudentCoursePackage, Student, Course)
        .join(Student, Student.id == StudentCoursePackage.student_id)
        .join(Course, Course.id == StudentCoursePackage.course_id)
        .filter(StudentCoursePackage.status != "refunded")
        .order_by(StudentCoursePackage.id.asc())
        .all()
    )

    today = business_today()
    expiring_deadline = today + timedelta(days=30)
    summary = {
        "package_count": 0,
        "purchased_hours": 0.0,
        "gift_hours": 0.0,
        "total_hours": 0.0,
        "consumed_hours": 0.0,
        "pending_hours": 0.0,
        "pending_value": 0.0,
        "expired_hours": 0.0,
        "expiring_soon_hours": 0.0,
    }
    all_students: set[int] = set()
    pending_students: set[int] = set()
    course_groups: dict[int, dict] = {}
    detail_groups: dict[tuple[int, int], dict] = {}

    def add_package(target: dict, package: StudentCoursePackage) -> None:
        purchased = max(float(package.purchased_hours or 0), 0.0)
        gift = max(float(package.gift_hours or 0), 0.0)
        total = max(float(package.total_hours or 0), 0.0)
        remain = max(float(package.remain_hours or 0), 0.0)
        consumed = max(total - remain, 0.0)
        pending_value = remain * max(float(package.unit_price or 0), 0.0)

        target["package_count"] += 1
        target["purchased_hours"] += purchased
        target["gift_hours"] += gift
        target["total_hours"] += total
        target["consumed_hours"] += consumed
        target["pending_hours"] += remain
        target["pending_value"] += pending_value

        if remain <= 0 or package.valid_until is None:
            return
        if package.valid_until < today:
            target["expired_hours"] += remain
        elif package.valid_until <= expiring_deadline:
            target["expiring_soon_hours"] += remain

    def blank_group() -> dict:
        return {
            "package_count": 0,
            "purchased_hours": 0.0,
            "gift_hours": 0.0,
            "total_hours": 0.0,
            "consumed_hours": 0.0,
            "pending_hours": 0.0,
            "pending_value": 0.0,
            "expired_hours": 0.0,
            "expiring_soon_hours": 0.0,
        }

    for package, student, course in rows:
        remain = max(float(package.remain_hours or 0), 0.0)
        all_students.add(student.id)
        if remain > 0:
            pending_students.add(student.id)
        add_package(summary, package)

        course_group = course_groups.setdefault(
            course.id,
            {
                **blank_group(),
                "course_id": course.id,
                "course_name": course.name,
                "course_type": course.course_type,
                "course_type_label": _course_type_label(course.course_type),
                "student_ids": set(),
            },
        )
        course_group["student_ids"].add(student.id)
        add_package(course_group, package)

        detail = detail_groups.setdefault(
            (student.id, course.id),
            {
                **blank_group(),
                "student_id": student.id,
                "student_name": student.name,
                "student_phone": student.phone or "",
                "student_grade": student.grade or "",
                "student_status": student.status,
                "course_id": course.id,
                "course_name": course.name,
                "course_type": course.course_type,
                "course_type_label": _course_type_label(course.course_type),
                "valid_until": None,
            },
        )
        if remain > 0 and package.valid_until is not None:
            valid_until = package.valid_until.isoformat()
            if detail["valid_until"] is None or valid_until < detail["valid_until"]:
                detail["valid_until"] = valid_until
        add_package(detail, package)

    numeric_fields = (
        "purchased_hours",
        "gift_hours",
        "total_hours",
        "consumed_hours",
        "pending_hours",
        "pending_value",
        "expired_hours",
        "expiring_soon_hours",
    )

    def finish(target: dict) -> dict:
        for field in numeric_fields:
            target[field] = round(float(target[field]), 2)
        total = float(target["total_hours"])
        target["consumption_rate"] = round(float(target["consumed_hours"]) / total * 100, 2) if total else 0.0
        expired = float(target["expired_hours"])
        expiring = float(target["expiring_soon_hours"])
        pending = float(target["pending_hours"])
        target["risk_status"] = (
            "expired" if expired > 0 else "expiring" if expiring > 0 else "normal" if pending > 0 else "consumed"
        )
        return target

    course_items = []
    for item in course_groups.values():
        item["student_count"] = len(item.pop("student_ids"))
        course_items.append(finish(item))
    course_items.sort(key=lambda item: (-item["pending_hours"], item["course_name"]))

    detail_items = [finish(item) for item in detail_groups.values()]
    detail_items.sort(key=lambda item: (-item["pending_hours"], item["student_name"], item["course_name"]))

    summary["student_count"] = len(all_students)
    summary["pending_student_count"] = len(pending_students)
    finish(summary)
    return {
        "as_of": today.isoformat(),
        "summary": summary,
        "by_course": course_items,
        "items": detail_items,
    }
