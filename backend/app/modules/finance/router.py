from datetime import date
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.responses import fail, ok
from app.models.user import User
from app.modules.finance import service as svc
from app.modules.finance.receipt import OrderReceiptFontError, build_order_receipt_pdf
from app.modules.finance.schemas import OrderCreate, RechargeCreate, TransactionConfirm

router = APIRouter(prefix="/finance", tags=["finance"])

_finance = require_permissions("finance.read", "finance.write")
_income_report = require_permissions("finance.income_report")


@router.get("/orders")
def list_orders(
    order_no: Optional[str] = None,
    student_q: Optional[str] = None,
    order_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    return ok(
        svc.list_orders(
            db,
            order_no=order_no,
            student_q=student_q,
            order_type=order_type,
            page=page,
            page_size=page_size,
            viewer=user,
        )
    )


@router.post("/orders")
def create_order(
    body: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    result = svc.create_manual_order(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("ORDER_CREATE_FAILED", result, status_code=400)
    return ok(svc.order_to_dict(db, result), status_code=201)


@router.get("/orders/{order_id}")
def get_order(
    order_id: int,
    log_view: bool = Query(False, description="是否记入操作日志「查看订单」"),
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    result = svc.get_order_detail_for_user(db, order_id, user, log_view=log_view)
    if isinstance(result, str):
        return fail("NOT_FOUND", result, status_code=404)
    return ok(result)


@router.get("/orders/{order_id}/receipt")
def download_order_receipt(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    """下载订单收据 PDF。"""
    detail = svc.get_order_detail_for_user(db, order_id, user, log_view=False)
    if isinstance(detail, str):
        return fail("NOT_FOUND", detail, status_code=404)
    try:
        pdf_bytes = build_order_receipt_pdf(detail)
    except OrderReceiptFontError as exc:
        return fail("RECEIPT_FONT_MISSING", str(exc), status_code=503)
    except Exception as exc:
        return fail("RECEIPT_FAILED", f"生成收据失败：{exc}", status_code=500)

    svc.add_order_log(
        db,
        order_id=order_id,
        action="print_receipt",
        user=user,
        detail=f"下载/打印收据 PDF，订单号 {detail.get('order_no') or order_id}",
        commit=True,
    )

    order_no = str(detail.get("order_no") or order_id)
    student = str(detail.get("student") or "学员").replace("/", "-")
    filename = f"收据_{student}_{order_no}.pdf"
    disp = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": disp},
    )


@router.get("/orders/{order_id}/logs")
def list_order_logs(
    order_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    # 先校验订单可见性
    detail = svc.get_order_detail_for_user(db, order_id, user, log_view=False)
    if isinstance(detail, str):
        return fail("NOT_FOUND", detail, status_code=404)
    result = svc.list_order_logs(db, order_id, page=page, page_size=page_size)
    if isinstance(result, str):
        return fail("NOT_FOUND", result, status_code=404)
    return ok(result)


@router.post("/orders/{order_id}/void")
def void_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    result = svc.void_order(db, order_id, user=user)
    if isinstance(result, str):
        return fail("ORDER_VOID_FAILED", result, status_code=400)
    return ok(result)


@router.get("/transactions")
def list_transactions(
    item: Optional[str] = None,
    tx_type: Optional[str] = None,
    status: Optional[str] = None,
    include_void: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    return ok(
        svc.list_transactions(
            db,
            item=item,
            tx_type=tx_type,
            status=status,
            include_void=include_void,
            page=page,
            page_size=page_size,
            viewer=user,
        )
    )


@router.post("/transactions/confirm")
def confirm_transactions(
    body: TransactionConfirm,
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    result = svc.confirm_transactions(db, user, body.ids)
    if isinstance(result, str):
        return fail("TX_CONFIRM_FAILED", result, status_code=400)
    return ok(result)


@router.post("/transactions/{tx_id}/void")
def void_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    result = svc.void_transaction(db, tx_id, user=user)
    if isinstance(result, str):
        return fail("TX_VOID_FAILED", result, status_code=400)
    return ok(svc.tx_to_dict(db, result))


@router.get("/consumptions")
def list_consumptions(
    student_q: Optional[str] = None,
    class_id: Optional[int] = None,
    course_id: Optional[int] = None,
    course_type: Optional[str] = None,
    teacher_id: Optional[int] = None,
    consume_type: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    hide_void: bool = True,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    grade: Optional[str] = None,
    subject: Optional[str] = None,
    term: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    return ok(
        svc.list_consumptions(
            db,
            student_q=student_q,
            class_id=class_id,
            course_id=course_id,
            course_type=course_type,
            teacher_id=teacher_id,
            consume_type=consume_type,
            source=source,
            status=status,
            hide_void=hide_void,
            start_date=start_date,
            end_date=end_date,
            grade=grade,
            subject=subject,
            term=term,
            page=page,
            page_size=page_size,
            viewer=user,
        )
    )


@router.get("/consumptions/{consumption_id}")
def get_consumption_detail(
    consumption_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    result = svc.get_consumption_detail(db, consumption_id, viewer=user)
    if isinstance(result, str):
        return fail("NOT_FOUND", result, status_code=404)
    return ok(result)


@router.get("/recharges")
def list_recharges(
    student_q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    return ok(
        svc.list_recharges(db, student_q=student_q, page=page, page_size=page_size, viewer=user)
    )


@router.post("/recharges")
def create_recharge(
    body: RechargeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_finance),
):
    result = svc.create_recharge(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("RECHARGE_FAILED", result, status_code=400)
    return ok(svc.recharge_to_dict(db, result), status_code=201)


@router.get("/income-report")
def income_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    _: User = Depends(_income_report),
):
    return ok(svc.income_report(db, start_date=start_date, end_date=end_date))


@router.get("/pending-hours-report")
def pending_hours_report(
    db: Session = Depends(get_db),
    _: User = Depends(_income_report),
):
    return ok(svc.pending_hours_report(db))
