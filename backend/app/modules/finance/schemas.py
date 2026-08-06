from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RechargeCreate(BaseModel):
    student_id: int
    amount: float = Field(gt=0)
    pay_method: str = "微信"
    remark: str = ""


class TransactionConfirm(BaseModel):
    ids: list[int] = Field(min_length=1)


class OrderCreate(BaseModel):
    """手工建单（转课/退课等简化）。"""

    student_id: int
    order_type: str = Field(
        default="other",
        pattern="^(enroll|renew|transfer|drop|recharge|refund|other)$",
    )
    item_summary: str = ""
    receivable: float = Field(default=0, ge=0)
    received: float = Field(default=0, ge=0)
    pay_method: str = ""
    handled_at: Optional[datetime] = None
    performance_owner_id: Optional[int] = None
