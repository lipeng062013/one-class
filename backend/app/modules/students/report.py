"""Generate polished student growth archive PDF (学情报告), including images."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image
from sqlalchemy.orm import Session, joinedload

from app.core.storage import Storage, get_storage
from app.models.student import LearningRecord, LearningRecordFile, Student
from app.models.user import User

CLASS_STATUS_CN = {
    "attended": "已上课",
    "absent": "缺勤",
    "late": "迟到",
    "leave": "请假",
    "makeup": "补课",
}

# 状态标签底色 (R,G,B)
CLASS_STATUS_COLOR = {
    "attended": (22, 101, 52),  # green
    "absent": (153, 27, 27),
    "late": (161, 98, 7),
    "leave": (55, 65, 81),
    "makeup": (30, 64, 175),
}

STATUS_CN = {
    "active": "在读",
    "paused": "暂停",
    "graduated": "结业",
    "quit": "退学",
}

# 米金轻奢色板
C_INK = (68, 64, 60)
C_MUTED = (120, 113, 108)
C_PRIMARY = (161, 98, 7)
C_GOLD = (245, 230, 200)
C_PAGE = (250, 248, 243)
C_CARD = (255, 253, 248)
C_BORDER = (232, 224, 208)
C_SIDEBAR = (41, 37, 36)
C_WHITE = (255, 255, 255)


def _find_cjk_font() -> str | None:
    """Locate a system CJK font for PDF Chinese text.

    Docker image installs fonts-wqy-microhei; Windows/macOS use built-in fonts.
    """
    # Bundled fallback (optional): backend/app/assets/fonts/*.ttf|ttc|otf
    assets_fonts = Path(__file__).resolve().parents[2] / "assets" / "fonts"
    bundled: list[Path] = []
    if assets_fonts.is_dir():
        bundled = [
            p
            for p in sorted(assets_fonts.iterdir())
            if p.is_file() and p.suffix.lower() in {".ttf", ".ttc", ".otf"}
        ]

    candidates = [
        *bundled,
        # Linux (Docker / Debian)
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
        Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
        # Windows
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyh.ttf"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        # macOS
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


class GrowthReportFontError(RuntimeError):
    """Raised when no CJK-capable font is available for PDF generation."""


def _prepare_image_for_pdf(raw: bytes, max_side: int = 1200) -> Path | None:
    """Normalize image to RGB JPEG temp file for reliable fpdf embedding."""
    try:
        img = Image.open(BytesIO(raw))
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 253, 248))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        scale = min(1.0, max_side / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        path = Path(tmp.name)
        img.save(path, format="JPEG", quality=88, optimize=True)
        return path
    except Exception:
        return None


class GrowthReportPDF(FPDF):
    """嘉壹启航成长档案 PDF。"""

    def __init__(self, student_name: str, font_family: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.student_name = student_name
        self.font_family = font_family
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(16, 18, 16)
        self._temp_files: list[Path] = []

    def cleanup(self) -> None:
        for p in self._temp_files:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        self._temp_files.clear()

    def header(self) -> None:
        # 顶栏深色条
        self.set_fill_color(*C_SIDEBAR)
        self.rect(0, 0, 210, 12, style="F")
        self.set_fill_color(*C_PRIMARY)
        self.rect(0, 12, 210, 1.2, style="F")

        self.set_xy(16, 3)
        self.set_text_color(*C_GOLD)
        self.set_font(self.font_family, "", 9)
        self.cell(0, 6, "嘉壹启航  ·  成长档案", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(18)
        self.set_text_color(*C_INK)

    def footer(self) -> None:
        self.set_y(-16)
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.3)
        self.line(16, self.get_y(), 194, self.get_y())
        self.set_y(-13)
        self.set_font(self.font_family, "", 8)
        self.set_text_color(*C_MUTED)
        self.cell(90, 8, f"{self.student_name}的成长档案", align="L")
        self.cell(0, 8, f"第 {self.page_no()} 页", align="R")

    def set_ink(self) -> None:
        self.set_text_color(*C_INK)

    def set_muted(self) -> None:
        self.set_text_color(*C_MUTED)

    def set_primary(self) -> None:
        self.set_text_color(*C_PRIMARY)

    def section_title(self, text: str) -> None:
        self.ln(3)
        y = self.get_y()
        self.set_fill_color(*C_PRIMARY)
        self.rect(16, y + 1.5, 2.2, 7, style="F")
        self.set_xy(21, y)
        self.set_font(self.font_family, "B", 13)
        self.set_primary()
        self.cell(0, 10, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_ink()
        self.ln(1)

    def label_value_row(self, pairs: list[tuple[str, str]], left_pad: float = 8) -> None:
        """两列 label:value 信息行；left_pad 让标签与左侧金条保持间距。"""
        col_w = 85
        x0 = self.l_margin + left_pad
        y0 = self.get_y()
        self.set_font(self.font_family, "", 10)
        for i, (label, value) in enumerate(pairs):
            x = x0 + (i % 2) * (col_w + 4)
            y = y0 + (i // 2) * 8
            self.set_xy(x, y)
            self.set_muted()
            self.cell(22, 7, f"{label}")
            self.set_ink()
            self.cell(col_w - 24, 7, value or "—")
        rows = (len(pairs) + 1) // 2
        self.set_y(y0 + rows * 8 + 2)

    def ensure_space(self, h: float) -> None:
        if self.get_y() + h > self.page_break_trigger:
            self.add_page()


def build_growth_report_pdf(
    db: Session,
    student: Student,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    record_ids: list[int] | None = None,
) -> tuple[bytes, str]:
    """Return (pdf_bytes, download_filename).

    Filters (priority):
    1. record_ids — only these LearningRecord ids (must belong to student)
    2. else date_from / date_to on class_date (inclusive)
    3. else all records

    PDF 正文不展示筛选区间文案（仅按筛选导出内容）。
    """
    storage = get_storage()
    manager_name = "—"
    if student.academic_manager_id:
        u = db.get(User, student.academic_manager_id)
        if u:
            manager_name = u.display_name

    query = (
        db.query(LearningRecord)
        .options(joinedload(LearningRecord.files))
        .filter(LearningRecord.student_id == student.id)
    )
    ids = [i for i in (record_ids or []) if isinstance(i, int) and i > 0]
    if ids:
        query = query.filter(LearningRecord.id.in_(ids))
    else:
        if date_from is not None:
            query = query.filter(LearningRecord.class_date >= date_from)
        if date_to is not None:
            end = date_to
            if end.hour == 0 and end.minute == 0 and end.second == 0 and end.microsecond == 0:
                end = end + timedelta(days=1) - timedelta(microseconds=1)
            query = query.filter(LearningRecord.class_date <= end)

    records = query.order_by(LearningRecord.class_date.desc(), LearningRecord.id.desc()).all()

    font_path = _find_cjk_font()
    if not font_path:
        raise GrowthReportFontError(
            "未找到可用的中文字体，无法生成学情报告 PDF。"
            "请在服务器安装 fonts-wqy-microhei，或将 .ttf/.ttc 放到 app/assets/fonts/。"
        )

    font_family = "CJK"
    pdf = GrowthReportPDF(student_name=student.name, font_family=font_family)
    # TTC (e.g. 微软雅黑 / 文泉驿) may emit subset warnings; still usable for CJK.
    pdf.add_font("CJK", "", font_path)
    pdf.add_font("CJK", "B", font_path)

    pdf.add_page()
    # 浅底（整页装饰感）
    pdf.set_fill_color(*C_PAGE)
    # header 已占顶部，内容区从当前 y 开始

    # ── 封面标题区（不展示学情区间）──
    pdf.set_fill_color(*C_GOLD)
    pdf.set_draw_color(*C_BORDER)
    title_y = pdf.get_y()
    header_h = 28
    pdf.rect(16, title_y, 178, header_h, style="FD")

    pdf.set_xy(20, title_y + 5)
    pdf.set_font(font_family, "B", 20)
    pdf.set_primary()
    pdf.cell(0, 10, f"{student.name}的成长档案", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_x(20)
    pdf.set_font(font_family, "", 9)
    pdf.set_muted()
    generated_at = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    pdf.cell(
        0,
        6,
        f"生成时间  {generated_at}    ·    嘉壹启航内部成长档案",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_y(title_y + header_h + 4)
    pdf.set_ink()

    # ── 学员档案卡片 ──
    # 不导出学生信息列表里的备注（student.notes）；学情时间线备注仍保留
    pdf.section_title("学员档案")
    card_top = pdf.get_y()
    info_pairs = [
        ("姓名", student.name),
        ("年级", student.grade or "—"),
        ("学校", student.school or "—"),
        ("学管师", manager_name),
        ("电话", student.phone or "—"),
        ("家长", student.parent_name or "—"),
        ("状态", STATUS_CN.get(student.status, student.status or "—")),
        ("学情条数", str(len(records))),
    ]
    info_lines = (len(info_pairs) + 1) // 2
    card_h = 12 + info_lines * 8 + 6
    pdf.set_fill_color(*C_CARD)
    pdf.set_draw_color(*C_BORDER)
    pdf.set_line_width(0.4)
    pdf.rect(16, card_top, 178, card_h, style="FD")
    # 左侧金条
    pdf.set_fill_color(*C_PRIMARY)
    pdf.rect(16, card_top, 1.8, card_h, style="F")

    pdf.set_y(card_top + 6)
    pdf.label_value_row(info_pairs)
    pdf.set_y(card_top + card_h + 4)

    # ── 学情时间线（标题不带区间）──
    # 若本页剩余高度只够写标题、几乎放不下第一条学情，则整段（标题+内容）换到下一页，
    # 避免第 1 页出现「学情时间线」下方大片空白。
    if not records:
        pdf.section_title("学情时间线")
        pdf.set_font(font_family, "", 11)
        pdf.set_muted()
        pdf.cell(
            0,
            10,
            "暂无学情记录。完成上课反馈后，将自动汇总到本档案。",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_ink()
    else:
        remaining_before_title = pdf.page_break_trigger - pdf.get_y()
        # 标题约 14mm + 卡片开头至少约 40mm
        if remaining_before_title < 55:
            pdf.add_page()
        pdf.section_title("学情时间线")
        for idx, r in enumerate(records, start=1):
            _render_record_card(pdf, db, storage, r, idx, font_family)

    # ── 结尾 ──
    pdf.ln(6)
    pdf.ensure_space(20)
    pdf.set_draw_color(*C_BORDER)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(4)
    pdf.set_font(font_family, "", 9)
    pdf.set_muted()
    pdf.cell(0, 6, "——  嘉壹启航 · 陪伴每一个孩子成长  ——", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, "本报告仅供机构内部教学与家校沟通使用", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    try:
        raw = pdf.output()
        if isinstance(raw, (bytes, bytearray)):
            data = bytes(raw)
        else:
            data = str(raw).encode("latin-1")
    finally:
        pdf.cleanup()

    # 三种导出方式统一文件名：XXX的成长档案.pdf
    safe_name = (student.name or "学员").replace("/", "-").replace("\\", "-").strip() or "学员"
    filename = f"{safe_name}的成长档案.pdf"
    return data, filename


def _pdf_field_block(
    pdf: GrowthReportPDF,
    *,
    card_x: float,
    content_w: float,
    font_family: str,
    title: str,
    body: str,
    pad_x: float = 8,
) -> None:
    """字段块：加粗标题 + 正文，块间留白，避免挤成一堆。"""
    pdf.ln(3)
    # 标题左侧小色条
    y = pdf.get_y()
    pdf.set_fill_color(*C_PRIMARY)
    pdf.rect(card_x + pad_x, y + 1.2, 1.6, 4.2, style="F")
    pdf.set_xy(card_x + pad_x + 4, y)
    pdf.set_font(font_family, "B", 10)
    pdf.set_primary()
    pdf.cell(content_w - 6, 6.5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_x(card_x + pad_x + 4)
    pdf.set_font(font_family, "", 10)
    pdf.set_ink()
    pdf.multi_cell(content_w - 6, 5.8, body or "—")


def _render_record_card(
    pdf: GrowthReportPDF,
    db: Session,
    storage: Storage,
    record: LearningRecord,
    index: int,
    font_family: str,
) -> None:
    teacher = db.get(User, record.teacher_id)
    teacher_name = teacher.display_name if teacher else "—"
    when = record.class_date.strftime("%Y-%m-%d %H:%M") if record.class_date else "—"
    status_key = record.class_status or "attended"
    status_label = CLASS_STATUS_CN.get(status_key, status_key)
    status_color = CLASS_STATUS_COLOR.get(status_key, C_PRIMARY)

    files = list(record.files or [])
    text_body = (record.learning_summary or "—").strip() or "—"
    # 只在「连卡片开头都放不下」时换页；允许长卡片跨页（跨页不画完整边框，避免幽灵空框）。
    # 切勿按整卡预估高度强行换页，否则会在上一页留下大片空白（仅剩「学情时间线」标题）。
    remaining = pdf.page_break_trigger - pdf.get_y()
    min_card_start = 42  # 序号行 + 元信息 + 少许正文
    if remaining < min_card_start:
        pdf.add_page()

    card_x = 16
    card_w = 178
    pad_x = 8
    content_w = card_w - pad_x * 2
    start_page = pdf.page_no()
    top = pdf.get_y()

    # 内容区：顶部金条 + 内边距
    content_top = top + 6
    pdf.set_xy(card_x + pad_x, content_top)

    # ── 头部：序号 · 日期 · 状态 ──
    pdf.set_font(font_family, "B", 12)
    pdf.set_ink()
    pdf.cell(14, 8, f"#{index}")
    pdf.set_font(font_family, "", 10)
    pdf.set_muted()
    pdf.cell(52, 8, when)

    badge_w = max(pdf.get_string_width(status_label) + 8, 16)
    bx = pdf.get_x() + 4
    by = pdf.get_y() + 1.2
    pdf.set_fill_color(*status_color)
    pdf.rect(bx, by, badge_w, 6, style="F")
    pdf.set_xy(bx, by)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font(font_family, "B", 8)
    pdf.cell(badge_w, 6, status_label, align="C")
    pdf.set_ink()

    # ── 元信息行：填写人 / 科目（轻量标签感）──
    pdf.set_xy(card_x + pad_x, content_top + 10)
    pdf.set_font(font_family, "", 9)
    pdf.set_muted()
    meta_parts = [f"填写人  {teacher_name}"]
    if record.subject:
        meta_parts.append(f"科目  {record.subject}")
    pdf.cell(0, 6, "    ·    ".join(meta_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # 分隔线
    sep_y = pdf.get_y() + 2
    pdf.set_draw_color(*C_BORDER)
    pdf.set_line_width(0.3)
    pdf.line(card_x + pad_x, sep_y, card_x + card_w - pad_x, sep_y)
    pdf.set_y(sep_y + 2)

    # ── 字段块：统一版式，块间留白 ──
    _pdf_field_block(
        pdf,
        card_x=card_x,
        content_w=content_w,
        font_family=font_family,
        title="学习情况",
        body=text_body,
        pad_x=pad_x,
    )

    if record.homework_note and record.homework_note.strip():
        _pdf_field_block(
            pdf,
            card_x=card_x,
            content_w=content_w,
            font_family=font_family,
            title="作业 / 下次",
            body=record.homework_note.strip(),
            pad_x=pad_x,
        )

    if record.notes and record.notes.strip():
        _pdf_field_block(
            pdf,
            card_x=card_x,
            content_w=content_w,
            font_family=font_family,
            title="内部备注",
            body=record.notes.strip(),
            pad_x=pad_x,
        )

    # ── 附件图片 ──
    if files:
        pdf.ln(4)
        y = pdf.get_y()
        # 标题行若贴近页底，先换页，避免「附件」标题与图片分离成空框
        if y + 56 > pdf.page_break_trigger:
            pdf.add_page()
            y = pdf.get_y()
        pdf.set_fill_color(*C_PRIMARY)
        pdf.rect(card_x + pad_x, y + 1.2, 1.6, 4.2, style="F")
        pdf.set_xy(card_x + pad_x + 4, y)
        pdf.set_font(font_family, "B", 10)
        pdf.set_primary()
        pdf.cell(0, 6.5, f"附件（{len(files)} 张）", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)
        _embed_images(pdf, storage, files, card_x + pad_x, content_w, font_family)

    # 底部内边距
    bottom = pdf.get_y() + 8
    end_page = pdf.page_no()

    # 仅在「同一页内完整画完」时绘制卡片边框。
    # 跨页时若仍用起始 top 与结束 bottom 算高度，会在新页画出空白矩形幽灵框。
    if end_page == start_page and bottom > top:
        height = max(bottom - top, 28)
        pdf.set_fill_color(*C_GOLD)
        pdf.rect(card_x, top, card_w, 2.0, style="F")
        pdf.set_fill_color(*C_PRIMARY)
        pdf.rect(card_x, top, 1.8, height, style="F")
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.4)
        pdf.rect(card_x, top, card_w, height, style="D")
        pdf.set_y(top + height + 8)
    else:
        # 跨页：在当前页内容末尾补一条轻分隔，不再画跨页大框
        y_end = pdf.get_y() + 2
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.35)
        pdf.line(card_x + 4, y_end, card_x + card_w - 4, y_end)
        pdf.set_y(y_end + 8)


def _embed_images(
    pdf: GrowthReportPDF,
    storage: Storage,
    files: list[LearningRecordFile],
    x0: float,
    max_w: float,
    font_family: str,
) -> None:
    """Embed learning images in a 2-column grid with breathing room."""
    gap = 5
    col_w = (max_w - gap) / 2
    img_h = 46
    col = 0
    row_y = pdf.get_y()
    placed = 0

    for f in files:
        try:
            raw = storage.read(f.file_path)
        except FileNotFoundError:
            continue
        path = _prepare_image_for_pdf(raw)
        if not path:
            continue
        pdf._temp_files.append(path)

        if col == 0:
            pdf.ensure_space(img_h + 10)
            row_y = pdf.get_y()

        x = x0 + col * (col_w + gap)
        try:
            with Image.open(path) as im:
                iw, ih = im.size
            ratio = iw / max(ih, 1)
            draw_w = col_w - 4
            draw_h = draw_w / ratio
            if draw_h > img_h - 4:
                draw_h = img_h - 4
                draw_w = draw_h * ratio
            ox = x + (col_w - draw_w) / 2
            oy = row_y + (img_h - draw_h) / 2
            pdf.set_fill_color(248, 245, 238)
            pdf.set_draw_color(*C_BORDER)
            pdf.set_line_width(0.3)
            pdf.rect(x, row_y, col_w, img_h, style="FD")
            pdf.image(str(path), x=ox, y=oy, w=draw_w, h=draw_h)
        except Exception:
            pdf.set_xy(x, row_y + img_h / 2 - 3)
            pdf.set_font(font_family, "", 8)
            pdf.set_muted()
            pdf.cell(col_w, 6, "图片无法加载", align="C")

        placed += 1
        col += 1
        if col >= 2:
            col = 0
            pdf.set_y(row_y + img_h + gap)

    if col != 0:
        pdf.set_y(row_y + img_h + gap)
    elif placed == 0:
        pdf.set_x(x0)
        pdf.set_font(font_family, "", 9)
        pdf.set_muted()
        pdf.cell(0, 6, "（暂无可用附件图片）", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
