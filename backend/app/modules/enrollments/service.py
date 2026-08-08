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
    """生成业务订单号：EN/RN/TF + yyyymmdd + 6 位随机，冲突则重试。"""
    prefix = {"enroll": "EN", "renew": "RN", "transfer": "TF"}.get(kind, "EN")
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

def _apply_transfer_out(
    db: Session,
    *,
    student: Student,
    transfer_out_course_id: int | None,
    transfer_out_items: list[dict],
) -> tuple[list[dict], float, float, str | None]:
    """扣减转出课包，返回转出明细、转出金额合计、手续费合计、错误信息。"""
    from app.models.academic import StudentCoursePackage

    if not transfer_out_course_id:
        return [], 0.0, 0.0, "请选择转出课程"
    if not transfer_out_items:
        return [], 0.0, 0.0, "请至少选择一条转出课包"

    out_course = db.get(Course, int(transfer_out_course_id))
    if not out_course:
        return [], 0.0, 0.0, "转出课程不存在"

    out_rows: list[dict] = []
    out_amount_total = 0.0
    fee_total = 0.0
    seen_pkgs: set[int] = set()

    for raw in transfer_out_items:
        try:
            package_id = int(raw.get("package_id"))
        except (TypeError, ValueError):
            return [], 0.0, 0.0, "转出课包 ID 无效"
        if package_id in seen_pkgs:
            return [], 0.0, 0.0, "转出课包重复"
        seen_pkgs.add(package_id)

        pkg = db.get(StudentCoursePackage, package_id)
        if not pkg or pkg.student_id != student.id:
            return [], 0.0, 0.0, f"课包 #{package_id} 不存在或不属于该学员"
        if int(pkg.course_id) != int(transfer_out_course_id):
            return [], 0.0, 0.0, f"课包 #{package_id} 不属于所选转出课程"
        if pkg.status != "active":
            return [], 0.0, 0.0, f"课包 #{package_id} 非在读状态，无法转出"

        remain = float(pkg.remain_hours or 0)
        if remain <= 0:
            return [], 0.0, 0.0, f"课包 #{package_id} 剩余课时为 0"

        exit_order = bool(raw.get("exit_order"))
        transfer_hours = float(raw.get("transfer_hours") or 0)
        transfer_gift = float(raw.get("transfer_gift_hours") or 0)
        fee = float(raw.get("fee") or 0)
        if fee < 0:
            return [], 0.0, 0.0, "手续费不能为负"

        if exit_order:
            # 退出订单：全部剩余转出
            transfer_hours = remain
            transfer_gift = 0.0
        take = transfer_hours + transfer_gift
        if take <= 0:
            return [], 0.0, 0.0, f"课包 #{package_id} 请填写转出课时"
        if take > remain + 1e-9:
            return [], 0.0, 0.0, f"课包 #{package_id} 转出课时不能大于剩余 {remain:g}"

        unit = float(pkg.unit_price or 0)
        if raw.get("transfer_amount") is not None:
            line_amount = float(raw.get("transfer_amount") or 0)
        else:
            line_amount = round(unit * transfer_hours, 2)

        # 扣减课包
        pkg.remain_hours = max(0.0, round(remain - take, 4))
        if exit_order or pkg.remain_hours <= 1e-9:
            pkg.remain_hours = 0.0
            pkg.status = "exhausted"
        pkg.updated_at = _utcnow()

        out_rows.append(
            {
                "package_id": pkg.id,
                "order_no": f"PKG-{pkg.id}",
                "course_id": out_course.id,
                "course_name": out_course.name,
                "unit_price": unit,
                "remain_before": remain,
                "transfer_hours": round(transfer_hours, 4),
                "transfer_gift_hours": round(transfer_gift, 4),
                "transfer_amount": line_amount,
                "fee": round(fee, 2),
                "exit_order": exit_order,
                "remain_after": float(pkg.remain_hours or 0),
            }
        )
        out_amount_total += line_amount
        fee_total += fee

    return out_rows, round(out_amount_total, 2), round(fee_total, 2), None


def _notify_admins_after_first_enroll(
    db: Session,
    student: Student,
    *,
    order_no: str,
    actor: User,
) -> None:
    """首次 kind=enroll 成功后通知负责人分配学管（仅线索转入学员且尚无学管）。"""
    if not student.source_lead_id:
        return
    if student.academic_manager_id:
        return

    from app.core.timeutil import now as _utcnow
    from app.models.todo import TodoItem
    from app.modules.auth.service import list_active_admins

    admins = list_active_admins(db)
    if not admins:
        return

    marker = f"[[student-alloc:{student.id}]]"
    title = f"【报名成功待调配】{student.name}"
    actor_name = (actor.display_name or actor.username or "").strip() or f"用户#{actor.id}"
    content = (
        f"{marker}\n"
        f"path:/students/{student.id}\n"
        f"学员 {student.name}（#{student.id}）已完成报名，订单 {order_no or '—'}。\n"
        f"来源线索#{student.source_lead_id}；办理人：{actor_name}。\n"
        f"请打开学员详情分配学管师。"
    )
    for admin in admins:
        existing = (
            db.query(TodoItem)
            .filter(
                TodoItem.user_id == admin.id,
                TodoItem.is_done.is_(False),
                TodoItem.content.contains(marker),
            )
            .first()
        )
        if existing:
            existing.title = title
            existing.content = content
            existing.created_at = _utcnow()
            db.add(existing)
            continue
        db.add(
            TodoItem(
                user_id=admin.id,
                title=title,
                content=content,
                is_done=False,
            )
        )


def create_record(db: Session, user: User, data: dict) -> EnrollmentRecord | str:
    from app.core.roles import managed_student_ids
    from app.modules.students import service as student_svc

    student = db.get(Student, data["student_id"])
    if not student:
        return "学员不存在"
    scope = managed_student_ids(db, user)
    if scope is not None and student.id not in scope:
        return "仅可为自己绑定的学员办理报名/续费/转课"

    kind = data.get("kind") or "enroll"
    if kind not in {"enroll", "renew", "transfer"}:
        return "类型须为报名、续费或转课"

    first_enroll = kind == "enroll" and not student_svc.student_has_enroll_record(
        db, student.id
    )

    transfer_mode = "course"
    transfer_to: Student | None = None
    if kind == "transfer":
        transfer_mode = data.get("transfer_mode") or "course"
        if transfer_mode not in {"course", "student"}:
            return "转课方式无效"
        if transfer_mode == "student":
            to_id = data.get("transfer_to_student_id")
            if not to_id:
                return "请选择转入学员"
            try:
                to_id = int(to_id)
            except (TypeError, ValueError):
                return "转入学员无效"
            if to_id == student.id:
                return "转入学员不能与转出学员相同"
            transfer_to = db.get(Student, to_id)
            if not transfer_to:
                return "转入学员不存在"
            if scope is not None and transfer_to.id not in scope:
                return "仅可为自己绑定的学员办理转课（转入学员不在管辖范围）"

    courses_in = data.get("courses") or []
    if not courses_in:
        return "请至少选择一门关联课程" if kind != "transfer" else "请至少选择一门转入课程"
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
            "discount": round(max(0.0, discount), 2),
        }
        # 客户端可传手动小计（学管/负责人改价）；与直减/折扣相互独立
        client_subtotal = item.get("subtotal")
        if client_subtotal is not None and str(client_subtotal).strip() != "":
            try:
                st = max(0.0, round(float(client_subtotal), 2))
            except (TypeError, ValueError):
                return f"课程「{name}」小计格式不正确"
            course_row["subtotal"] = st
            # 涨价时反推课包单价；优惠字段保持客户端传入，不因小计改写
            if st + 1e-9 > total and hours > 0:
                course_row["unit_price"] = round(st / hours, 4)
        else:
            if course_row["discount"] > total + 1e-9:
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

    # 转出课包（仅 transfer）
    transfer_out_rows: list[dict] = []
    transfer_out_amount = 0.0
    transfer_fee_total = 0.0
    if kind == "transfer":
        transfer_out_rows, transfer_out_amount, transfer_fee_total, tout_err = _apply_transfer_out(
            db,
            student=student,
            transfer_out_course_id=data.get("transfer_out_course_id"),
            transfer_out_items=list(data.get("transfer_out_items") or []),
        )
        if tout_err:
            return tout_err
        # 转入课程不能与转出课程完全相同且无差额时仍允许（换价/补差）
        out_cid = int(data.get("transfer_out_course_id") or 0)
        only_same = all(int(c.get("id") or 0) == out_cid for c in courses if c.get("id"))
        if only_same and len(courses) == 1:
            # 允许同课补差/调整课时，不拦截
            pass

    in_subtotal = round(sum(float(c.get("subtotal") or 0) for c in courses), 2)

    # 应收：转课 = max(0, 转入小计 - 转出金额 + 手续费)；报名/续费用客户端 amount 或业绩合计
    if kind == "transfer":
        amount = round(max(0.0, in_subtotal - transfer_out_amount + transfer_fee_total), 2)
    else:
        amount = float(data.get("amount") or 0)
        if amount <= 0 and attributions:
            amount = sum(float(a["amount"]) for a in attributions)

    # 支付方式
    raw_methods = data.get("pay_methods") or []
    if not isinstance(raw_methods, list):
        raw_methods = []
    if kind != "transfer" and not raw_methods:
        return "请至少选择一种支付方式"
    if kind == "transfer" and amount > 0 and not raw_methods:
        return "转课有应收差额时请选择支付方式"

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

    if attributions and abs(sum(float(a["amount"]) for a in attributions) - amount) >= 0.01:
        return "销售业绩合计必须等于应收金额"
    received = sum(float(p["amount"]) for p in payments)
    # 兼容旧客户端：未传支付明细时，勾选的首个方式承担全额实收。
    if not payments_in and amount > 0 and pay_methods:
        received = amount
        payments = [{"method": pay_methods[0], "amount": amount}]
    if received > amount:
        return "实收金额不能大于应收金额"
    # 报名/续费：有应收时必须有实收，禁止零支付直接成功
    if kind in {"enroll", "renew"} and amount > 0 and received <= 0:
        return "报名/续费须填写实收金额，不能零支付提交"
    arrears = max(0.0, amount - received)

    order_no = generate_order_no(db, kind=kind)
    pay_label = "、".join(pay_methods) if pay_methods else "—"
    if pay_other:
        pay_label = f"{pay_label}（{pay_other}）"

    # 课程快照：转课写入转入课程，并附加 transfer 元数据
    courses_snapshot = list(courses)
    if kind == "transfer":
        out_course_name = ""
        if transfer_out_rows:
            out_course_name = str(transfer_out_rows[0].get("course_name") or "")
        transfer_meta = {
            "transfer_mode": transfer_mode,
            "from_student_id": student.id,
            "from_student_name": student.name,
        }
        if transfer_to is not None:
            transfer_meta["to_student_id"] = transfer_to.id
            transfer_meta["to_student_name"] = transfer_to.name
        courses_snapshot = [
            {
                **c,
                "role": "transfer_in",
                **transfer_meta,
            }
            for c in courses
        ]
        # 在记录中保留转出摘要（前端订单展示用）
        for tr in transfer_out_rows:
            courses_snapshot.append(
                {
                    "id": tr.get("course_id"),
                    "name": f"转出 · {tr.get('course_name') or out_course_name}",
                    "type": "转出",
                    "price_label": f"单价({float(tr.get('unit_price') or 0):g}元/课时)",
                    "hours": float(tr.get("transfer_hours") or 0),
                    "gift_hours": float(tr.get("transfer_gift_hours") or 0),
                    "unit_price": float(tr.get("unit_price") or 0),
                    "subtotal": -float(tr.get("transfer_amount") or 0),
                    "role": "transfer_out",
                    "package_id": tr.get("package_id"),
                    "transfer_amount": tr.get("transfer_amount"),
                    "fee": tr.get("fee"),
                    "exit_order": tr.get("exit_order"),
                    **transfer_meta,
                }
            )

    row = EnrollmentRecord(
        student_id=student.id,
        kind=kind,
        handled_at=handled_at,
        amount=amount,
        order_no=order_no,
        pay_methods=json.dumps(pay_methods, ensure_ascii=False),
        pay_other=pay_other[:128],
        courses=json.dumps(courses_snapshot, ensure_ascii=False),
        attributions=json.dumps(attributions, ensure_ascii=False),
        internal_notes=(data.get("internal_notes") or "").strip(),
        external_notes=(data.get("external_notes") or "").strip(),
        internal_images=json.dumps(images, ensure_ascii=False),
        created_by=user.id,
    )
    db.add(row)
    db.flush()  # 拿到 enrollment id 再写财务订单

    # 同步财务订单 + 待确认收支
    kind_label = {"enroll": "报名", "renew": "续费", "transfer": "转课"}.get(kind, kind)
    if kind == "transfer":
        in_names = "、".join(c["name"] for c in courses) or "转入课程"
        out_name = ""
        if transfer_out_rows:
            out_name = str(transfer_out_rows[0].get("course_name") or "")
        if transfer_mode == "student" and transfer_to is not None:
            course_names = (
                f"【{student.name}】转出【{out_name or '课程'}】→ "
                f"【{transfer_to.name}】转入【{in_names}】"
            )
        else:
            course_names = (
                f"转出【{out_name}】→ 转入【{in_names}】" if out_name else f"转课 · {in_names}"
            )
    else:
        course_names = "、".join(c["name"] for c in courses) or kind_label
    perf_owner = attributions[0]["user_id"] if attributions else None
    handled_dt = handled_at if isinstance(handled_at, datetime) else _utcnow()
    order_status = (
        "paid"
        if amount <= 0 or arrears <= 0
        else "partial"
        if received > 0
        else "unpaid"
    )
    if amount <= 0:
        order_status = "paid"
    order = FinanceOrder(
        order_no=order_no,
        student_id=student.id,
        order_type=kind,
        item_summary=course_names[:500],
        courses=json.dumps(courses_snapshot, ensure_ascii=False),
        receivable=amount,
        received=received,
        arrears=arrears if amount > 0 else 0.0,
        status=order_status,
        source="机构创建",
        performance_owner_id=perf_owner,
        handler_id=user.id,
        enrollment_id=row.id,
        pay_method=pay_label[:64],
        handled_at=handled_dt,
        paid_at=_utcnow() if (received > 0 or amount <= 0) else None,
        created_by=user.id,
    )
    db.add(order)
    db.flush()
    try:
        from app.modules.finance.service import add_order_log

        detail_extra = ""
        if kind == "transfer":
            detail_extra = (
                f"，转出 {transfer_out_amount:.2f}，转入 {in_subtotal:.2f}，"
                f"手续费 {transfer_fee_total:.2f}"
            )
            if transfer_mode == "student" and transfer_to is not None:
                detail_extra += f"，转入学员 {transfer_to.name}(#{transfer_to.id})"
        add_order_log(
            db,
            order_id=order.id,
            action="create",
            user=user,
            detail=(
                f"{kind_label}生成订单 {order_no}，金额 {amount:.2f}，支付 {pay_label}"
                f"{detail_extra}"
            ),
        )
    except Exception:
        pass

    tx_item = "报名/续费" if kind in {"enroll", "renew"} else "转课"
    for payment in payments:
        db.add(
            FinanceTransaction(
                handled_at=handled_dt,
                item=tx_item,
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

    # 写入转入课包；一对一自动建班
    # 转给其他课程 → 课包归原学员；转课给其他学员 → 课包归目标学员
    package_owner = transfer_to if (kind == "transfer" and transfer_mode == "student" and transfer_to) else student
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
            student_id=package_owner.id,
            course_id=course_obj.id,
            hours=hours,
            purchased_hours=purchased_hours,
            gift_hours=gift_hours,
            unit_price=unit_price,
            enrollment_id=row.id,
        )
        academic_svc.ensure_one_to_one_class(
            db, student=package_owner, course=course_obj, user=user
        )

    def _merge_linked_courses(target: Student, links: list[dict]) -> None:
        existing = _parse_json_list(getattr(target, "linked_courses", None))
        merged: dict[str, dict] = {}
        for link in [*existing, *links]:
            key = f"id:{link.get('id')}" if link.get("id") else f"name:{link.get('name', '')}"
            if key not in merged:
                merged[key] = dict(link)
            else:
                merged[key].update(link)
        target.linked_courses = json.dumps(list(merged.values()), ensure_ascii=False)

    # 报名/续费/转课后默认置为在读；同步关联课程到学员档案
    if student.status in {"paused", "quit", "graduated"} or kind in {"enroll", "transfer"}:
        student.status = "active"
        student.updated_at = _utcnow()

    if kind == "transfer" and transfer_mode == "student" and transfer_to is not None:
        # 原学员仅扣课，不把转入课程写回自己的关联；目标学员写入转入课程
        if transfer_to.status in {"paused", "quit", "graduated"}:
            transfer_to.status = "active"
            transfer_to.updated_at = _utcnow()
        _merge_linked_courses(transfer_to, courses)
        # 目标学员侧写一条转入登记（金额 0，便于动态/报读追溯；财务单仍挂在转出学员）
        target_courses = [
            {
                **c,
                "role": "transfer_in",
                "transfer_mode": "student",
                "from_student_id": student.id,
                "from_student_name": student.name,
                "to_student_id": transfer_to.id,
                "to_student_name": transfer_to.name,
            }
            for c in courses
        ]
        target_notes = (data.get("internal_notes") or "").strip()
        if target_notes:
            target_notes = f"由【{student.name}】转入。{target_notes}"
        else:
            target_notes = f"由【{student.name}】转入（订单 {order_no}）"
        target_row = EnrollmentRecord(
            student_id=transfer_to.id,
            kind="transfer",
            handled_at=handled_at,
            amount=0,
            order_no=order_no,
            pay_methods=json.dumps([], ensure_ascii=False),
            pay_other="",
            courses=json.dumps(target_courses, ensure_ascii=False),
            attributions=json.dumps([], ensure_ascii=False),
            internal_notes=target_notes[:2000],
            external_notes=(data.get("external_notes") or "").strip(),
            internal_images=json.dumps([], ensure_ascii=False),
            created_by=user.id,
        )
        db.add(target_row)
    else:
        _merge_linked_courses(student, courses)
    # 对内备注仅保存在报名记录，不写入学员档案 notes

    if first_enroll:
        _notify_admins_after_first_enroll(
            db, student, order_no=order_no, actor=user
        )

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
