"""订单收据 PDF 生成（米金轻奢样式）。"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.core.timeutil import now as business_now
from app.modules.students.report import _find_cjk_font

# 米金轻奢色板（与成长档案一致）
C_INK = (68, 64, 60)
C_MUTED = (120, 113, 108)
C_PRIMARY = (161, 98, 7)
C_GOLD = (245, 230, 200)
C_GOLD_SOFT = (250, 246, 238)
C_BORDER = (232, 224, 208)
C_PAGE = (250, 248, 243)
C_WHITE = (255, 255, 255)
C_SIDEBAR = (41, 37, 36)
C_SUCCESS = (22, 163, 74)


class OrderReceiptFontError(RuntimeError):
    pass


def _money(n: float | int | None) -> str:
    try:
        return f"{float(n or 0):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _fmt_dt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    try:
        return str(v).replace("T", " ")[:16]
    except Exception:
        return str(v)


def _fmt_date(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    s = str(v)
    return s[:10] if len(s) >= 10 else s


def _clip(s, n: int = 40) -> str:
    t = str(s if s is not None and s != "" else "—")
    return t if len(t) <= n else t[: n - 1] + "…"


class OrderReceiptPDF(FPDF):
    def __init__(self, font_family: str = "CJK", order_no: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.font_family = font_family
        self.order_no = order_no
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(16, 18, 16)

    def header(self) -> None:
        # 顶栏深色 + 金线
        self.set_fill_color(*C_SIDEBAR)
        self.rect(0, 0, 210, 11, style="F")
        self.set_fill_color(*C_PRIMARY)
        self.rect(0, 11, 210, 1.4, style="F")

        self.set_xy(16, 2.5)
        self.set_text_color(*C_GOLD)
        self.set_font(self.font_family, "", 9)
        self.cell(100, 6, "嘉壹启航  ·  收费收据", align="L")
        self.set_font(self.font_family, "", 8)
        if self.order_no:
            self.cell(0, 6, f"No.{self.order_no}", align="R")
        self.set_y(16)
        self.set_text_color(*C_INK)

    def footer(self) -> None:
        self.set_y(-16)
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.3)
        self.line(16, self.get_y(), 194, self.get_y())
        self.set_y(-13)
        self.set_font(self.font_family, "", 8)
        self.set_text_color(*C_MUTED)
        self.cell(90, 8, "嘉壹启航运营系统 · 内部收据", align="L")
        self.cell(0, 8, f"第 {self.page_no()} 页", align="R")

    def section_title(self, text: str) -> None:
        self.ln(2)
        y = self.get_y()
        self.set_fill_color(*C_PRIMARY)
        self.rect(16, y + 1.8, 2.2, 6.5, style="F")
        self.set_xy(21, y)
        self.set_font(self.font_family, "B", 12)
        self.set_text_color(*C_PRIMARY)
        self.cell(0, 10, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*C_INK)

    def ensure_space(self, h: float) -> None:
        if self.get_y() + h > self.page_break_trigger:
            self.add_page()


def build_order_receipt_pdf(detail: dict) -> bytes:
    """根据 get_order_detail 结果生成收据 PDF。"""
    font_path = _find_cjk_font()
    if not font_path:
        raise OrderReceiptFontError(
            "未找到可用的中文字体，无法生成收据 PDF。"
            "请在服务器安装 fonts-wqy-microhei，或将 .ttf/.ttc 放到 app/assets/fonts/。"
        )

    font_family = "CJK"
    order_no = str(detail.get("order_no") or "—")
    pdf = OrderReceiptPDF(font_family=font_family, order_no=order_no)
    pdf.add_font("CJK", "", font_path)
    pdf.add_font("CJK", "B", font_path)
    pdf.add_page()

    # ── 标题卡 ──
    y0 = pdf.get_y()
    pdf.set_fill_color(*C_GOLD)
    pdf.set_draw_color(*C_BORDER)
    pdf.set_line_width(0.4)
    pdf.rect(16, y0, 178, 22, style="FD")

    # 左侧金条强调
    pdf.set_fill_color(*C_PRIMARY)
    pdf.rect(16, y0, 3, 22, style="F")

    pdf.set_xy(24, y0 + 3)
    pdf.set_font(font_family, "B", 16)
    pdf.set_text_color(*C_PRIMARY)
    pdf.cell(120, 9, "收费收据", new_x=XPos.RIGHT, new_y=YPos.TOP)

    status = detail.get("status_label") or detail.get("status") or ""
    # 右侧状态徽章
    pdf.set_xy(150, y0 + 5)
    pdf.set_font(font_family, "B", 10)
    if detail.get("status") == "paid":
        pdf.set_text_color(*C_SUCCESS)
    elif detail.get("status") == "void":
        pdf.set_text_color(*C_MUTED)
    else:
        pdf.set_text_color(*C_PRIMARY)
    pdf.cell(40, 8, f"【{status}】", align="R")

    pdf.set_xy(24, y0 + 13)
    pdf.set_font(font_family, "", 8)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(
        0,
        5,
        f"打印时间  {business_now().strftime('%Y年%m月%d日 %H:%M')}    ·    请妥善保管本收据",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_y(y0 + 26)

    # ── 订单基本信息 ──
    pdf.section_title("订单信息")
    pdf.set_font(font_family, "", 9)
    pdf.set_fill_color(*C_GOLD_SOFT)
    pdf.set_draw_color(*C_BORDER)

    meta_rows = [
        ("订单号", order_no, "创建时间", _fmt_dt(detail.get("created_at"))),
        (
            "订单类型",
            str(detail.get("order_type_label") or "—"),
            "订单来源",
            str(detail.get("source") or "机构创建"),
        ),
    ]
    for lab1, val1, lab2, val2 in meta_rows:
        pdf.set_font(font_family, "", 9)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(22, 8, lab1, border="LBT", fill=True)
        pdf.set_text_color(*C_INK)
        pdf.set_font(font_family, "B", 9)
        pdf.cell(67, 8, _clip(val1, 22), border="BT", fill=True)
        pdf.set_font(font_family, "", 9)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(22, 8, lab2, border="BT", fill=True)
        pdf.set_text_color(*C_INK)
        pdf.set_font(font_family, "B", 9)
        pdf.cell(67, 8, _clip(val2, 22), border="RBT", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── 学员与金额 ──
    pdf.section_title("学员与金额")
    pdf.set_fill_color(*C_WHITE)
    info_pairs = [
        ("学员姓名", _clip(detail.get("student"), 18)),
        ("年级", _clip(detail.get("student_grade"), 12)),
        ("手机号", _clip(detail.get("phone"), 16)),
        ("经办日期", _fmt_date(detail.get("handled_at"))),
        ("应收(元)", _money(detail.get("receivable"))),
        ("实收(元)", _money(detail.get("received"))),
        ("欠费(元)", _money(detail.get("arrears"))),
        ("支付方式", _clip(detail.get("pay_method") or "—", 16)),
    ]
    # 两列网格
    for i in range(0, len(info_pairs), 2):
        lab1, val1 = info_pairs[i]
        lab2, val2 = info_pairs[i + 1] if i + 1 < len(info_pairs) else ("", "")
        pdf.set_font(font_family, "", 9)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(22, 8, lab1, border="LBT")
        pdf.set_text_color(*C_INK)
        pdf.set_font(font_family, "B", 9)
        pdf.cell(67, 8, val1, border="BT")
        if lab2:
            pdf.set_font(font_family, "", 9)
            pdf.set_text_color(*C_MUTED)
            pdf.cell(22, 8, lab2, border="BT")
            pdf.set_text_color(*C_INK)
            pdf.set_font(font_family, "B", 9)
            # 金额高亮
            if "元" in lab2 or lab2 in ("应收(元)", "实收(元)", "欠费(元)"):
                pdf.set_text_color(*C_PRIMARY)
            pdf.cell(67, 8, val2, border="RBT", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.cell(89, 8, "", border="RBT", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── 购买内容 ──
    pdf.section_title("购买内容")
    lines = detail.get("line_items") or []
    pdf.set_fill_color(*C_GOLD)
    pdf.set_draw_color(*C_BORDER)
    pdf.set_font(font_family, "B", 8)
    pdf.set_text_color(*C_INK)
    headers = [
        ("购买项目", 48),
        ("定价标准", 36),
        ("数量", 24),
        ("总价(元)", 24),
        ("应收(元)", 24),
        ("班级", 22),
    ]
    for title, w in headers:
        pdf.cell(w, 8, title, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font(font_family, "", 8)
    if not lines:
        pdf.set_text_color(*C_MUTED)
        pdf.cell(178, 8, "（无购买明细）", border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        for idx, item in enumerate(lines):
            pdf.ensure_space(10)
            # 斑马纹
            if idx % 2 == 1:
                pdf.set_fill_color(*C_GOLD_SOFT)
                fill = True
            else:
                pdf.set_fill_color(*C_WHITE)
                fill = True
            name = str(item.get("name") or "—")
            tag = item.get("tag") or ""
            if tag:
                name = f"{name} · {tag}"
            name = _clip(name, 14)
            price = _clip(str(item.get("price_label") or "—"), 12)
            qty = _clip(str(item.get("quantity_label") or "—"), 8)
            cls = _clip(str(item.get("class_name") or "—"), 6)
            pdf.set_text_color(*C_INK)
            row = [
                (name, 48, "L"),
                (price, 36, "L"),
                (qty, 24, "C"),
                (_money(item.get("total")), 24, "R"),
                (_money(item.get("receivable")), 24, "R"),
                (cls, 22, "C"),
            ]
            for text, w, align in row:
                pdf.cell(w, 8, text, border=1, align=align, fill=fill)
            pdf.ln()

    # 合计条
    pdf.ln(1)
    sum_recv = detail.get("line_receivable_sum")
    if sum_recv is None:
        sum_recv = detail.get("receivable")
    sum_paid = detail.get("received")
    y_sum = pdf.get_y()
    pdf.set_fill_color(*C_GOLD)
    pdf.set_draw_color(*C_BORDER)
    pdf.rect(16, y_sum, 178, 10, style="FD")
    pdf.set_xy(20, y_sum + 1.5)
    pdf.set_font(font_family, "B", 10)
    pdf.set_text_color(*C_PRIMARY)
    pdf.cell(
        170,
        7,
        f"应收合计  ¥ {_money(sum_recv)}          实收合计  ¥ {_money(sum_paid)}",
        align="R",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_y(y_sum + 12)

    # ── 支付记录 ──
    pdf.section_title("支付记录")
    pays = detail.get("payments") or []
    pdf.set_fill_color(*C_GOLD)
    pdf.set_font(font_family, "B", 8)
    pdf.set_text_color(*C_INK)
    pay_headers = [
        ("支付时间", 40),
        ("经办人", 32),
        ("项目", 32),
        ("支付方式", 30),
        ("金额(元)", 28),
        ("状态", 16),
    ]
    for title, w in pay_headers:
        pdf.cell(w, 8, title, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font(font_family, "", 8)
    if not pays:
        pdf.set_text_color(*C_MUTED)
        pdf.cell(178, 8, "（暂无支付记录）", border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        for idx, p in enumerate(pays):
            pdf.ensure_space(10)
            fill = idx % 2 == 1
            if fill:
                pdf.set_fill_color(*C_GOLD_SOFT)
            else:
                pdf.set_fill_color(*C_WHITE)
            pdf.set_text_color(*C_INK)
            cells = [
                (_clip(_fmt_dt(p.get("created_at") or p.get("handled_at")), 16), 40, "C"),
                (_clip(p.get("handler"), 8), 32, "C"),
                (_clip(p.get("item"), 8), 32, "C"),
                (_clip(p.get("pay_method"), 8), 30, "C"),
                (_money(p.get("amount")), 28, "R"),
                (_clip(p.get("status"), 4), 16, "C"),
            ]
            for text, w, align in cells:
                pdf.cell(w, 8, text, border=1, align=align, fill=True)
            pdf.ln()

    # ── 对外备注（仅对外，不对内） ──
    notes_ex = (detail.get("external_notes") or "").strip()
    if notes_ex:
        pdf.section_title("备注")
        pdf.set_fill_color(*C_GOLD_SOFT)
        pdf.set_draw_color(*C_BORDER)
        pdf.set_font(font_family, "", 9)
        pdf.set_text_color(*C_INK)
        # 用 cell 避免 multi_cell 宽度问题；长备注分行
        text = _clip(notes_ex, 90)
        pdf.cell(178, 8, text, border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── 经办人（写明姓名，无客户确认） ──
    pdf.ln(8)
    handler = str(detail.get("handler") or "—").strip() or "—"
    y_h = pdf.get_y()
    pdf.set_draw_color(*C_BORDER)
    pdf.set_fill_color(*C_GOLD_SOFT)
    pdf.rect(16, y_h, 178, 14, style="FD")
    pdf.set_xy(22, y_h + 3)
    pdf.set_font(font_family, "", 10)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(28, 8, "经办人")
    pdf.set_font(font_family, "B", 11)
    pdf.set_text_color(*C_INK)
    pdf.cell(0, 8, handler, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(4)
    pdf.set_font(font_family, "", 8)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(
        0,
        5,
        "本收据由嘉壹启航运营系统自动生成，仅供核对与留存。",
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    out = BytesIO()
    pdf.output(out)
    return out.getvalue()
