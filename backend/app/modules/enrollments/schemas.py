from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AttributionIn(BaseModel):
    user_id: int
    amount: float = Field(default=0, ge=0)


class CourseLinkIn(BaseModel):
    """报名/续费关联的课程（可多选）。"""

    id: Optional[int] = None
    name: str = Field(min_length=1, max_length=128)
    type: str = ""
    price_label: str = ""
    # 购买课时数；未传则默认 10
    hours: float = Field(default=10, gt=0, le=9999)
    unit_price: Optional[float] = Field(default=None, ge=0)
    gift_hours: float = Field(default=0, ge=0, le=9999)
    price_standard: str = Field(default="", max_length=128)
    discount_type: str = Field(default="reduce", pattern="^(reduce|rate)$")
    discount_value: float = Field(default=0, ge=0)
    # 兼容旧客户端仅传优惠金额
    discount: float = Field(default=0, ge=0)
    # 可选：学管/负责人手动改价后的行小计；不传则按 总价-优惠 计算
    subtotal: Optional[float] = Field(default=None, ge=0)


class PaymentIn(BaseModel):
    method: str = Field(min_length=1, max_length=32)
    amount: float = Field(default=0, ge=0)


class TransferOutItem(BaseModel):
    """转出课包行：从原课包扣减课时并折算金额。"""

    package_id: int
    # 转出购买课时
    transfer_hours: float = Field(default=0, ge=0, le=9999)
    # 转出赠送课时
    transfer_gift_hours: float = Field(default=0, ge=0, le=9999)
    # 手续费/亏损费
    fee: float = Field(default=0, ge=0)
    # 是否退出该订单（剩余课时一并清零）
    exit_order: bool = False
    # 可选覆盖转出金额；不传则按 unit_price × transfer_hours 计算
    transfer_amount: Optional[float] = Field(default=None, ge=0)


# 支付方式固定选项；「其他」须配合 pay_other 文案
PAY_METHOD_OPTIONS = ("微信", "支付宝", "POS机刷卡", "现金", "其他")


class EnrollmentCreate(BaseModel):
    student_id: int
    kind: str = Field(default="enroll", pattern="^(enroll|renew|transfer)$")
    handled_at: Optional[datetime] = None
    amount: float = Field(default=0, ge=0)
    # 转入/报名课程（转课时至少一门转入课程）
    courses: list[CourseLinkIn] = Field(min_length=1, max_length=20)
    attributions: list[AttributionIn] = Field(default_factory=list, max_length=10)
    # 支付方式多选；转课应收为 0 时可空
    pay_methods: list[str] = Field(default_factory=list, max_length=5)
    pay_other: str = Field(default="", max_length=128)
    # 各支付方式的本次实收；旧客户端不传时仍按 amount 全额收款处理
    payments: list[PaymentIn] = Field(default_factory=list, max_length=5)
    internal_notes: str = ""
    external_notes: str = ""
    # 已上传的对内备注图相对路径（最多 3 张）
    internal_images: list[str] = Field(default_factory=list, max_length=3)
    # ── 转课专用 ──
    # course：转给其他课程；student：转课给其他学员
    transfer_mode: str = Field(default="course", pattern="^(course|student)$")
    transfer_out_course_id: Optional[int] = None
    transfer_out_items: list[TransferOutItem] = Field(default_factory=list, max_length=50)
    # 转课给其他学员时的目标学员
    transfer_to_student_id: Optional[int] = None


class EnrollmentOut(BaseModel):
    id: int
    order_id: Optional[int] = None
    student_id: int
    student_name: Optional[str] = None
    student_grade: Optional[str] = None
    student_phone: Optional[str] = None
    kind: str
    handled_at: Optional[datetime] = None
    amount: float = 0
    order_no: str = ""
    pay_methods: list[str] = Field(default_factory=list)
    pay_other: str = ""
    courses: list[dict] = Field(default_factory=list)
    attributions: list[dict] = Field(default_factory=list)
    internal_notes: str = ""
    external_notes: str = ""
    internal_images: list[str] = Field(default_factory=list)
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
