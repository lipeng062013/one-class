"""业务时间工具。

教务/点名/课消/报名等按「门店本地墙钟」记录与展示，统一使用中国标准时间（UTC+8）。
返回 naive datetime（无 tzinfo），与排课 start_at/end_at、前端按本地解析的约定一致。

注意：JWT 过期等安全相关时间仍应使用真正的 UTC（见 security.py），不要用本模块。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

# 中国标准时间（无夏令时），不依赖系统 tzdata，Windows/Linux 行为一致
APP_TZ = timezone(timedelta(hours=8))


def now() -> datetime:
    """当前业务时间（UTC+8 墙钟，naive）。用于 roll_at / created_at / handled_at 等。"""
    return datetime.now(APP_TZ).replace(tzinfo=None)


def now_aware() -> datetime:
    """当前业务时间（带 +08:00）。用于 DateTime(timezone=True) 字段。"""
    return datetime.now(APP_TZ)


def today() -> date:
    """当前业务日期（UTC+8）。"""
    return datetime.now(APP_TZ).date()


def day_start(d: date | None = None) -> datetime:
    """某日 00:00:00（业务墙钟，naive）。"""
    return datetime.combine(d or today(), time.min)


def day_end(d: date | None = None) -> datetime:
    """某日 23:59:59.999999（业务墙钟，naive）。"""
    return datetime.combine(d or today(), time.max)


# 兼容旧名：历史代码大量使用 _utcnow，语义已改为业务本地「现在」
utcnow = now
