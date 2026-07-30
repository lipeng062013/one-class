from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations import llm
from app.integrations.llm import LlmUnavailable
from app.models.content import GeneratedCopy
from app.models.knowledge import KnowledgeEntry
from app.models.material import Material
from app.models.template import CopyTemplate
from app.models.user import User
from app.modules.content.schemas import GenerateCopyRequest, GeneratedCopyUpdate

MODES = {"template", "llm", "template_then_llm"}

_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(body: str, context: dict[str, Any]) -> str:
    """Replace ``{{key}}`` placeholders with values from *context*."""

    def _repl(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key)
        if value is None:
            return ""
        return str(value)

    return _PLACEHOLDER_RE.sub(_repl, body or "")


def find_banned(text: str, words: list[str]) -> list[str]:
    """Return banned words that appear in *text* (order preserved, unique)."""
    hits: list[str] = []
    haystack = text or ""
    for word in words:
        if not word:
            continue
        if word in haystack and word not in hits:
            hits.append(word)
    return hits


def _build_context(db: Session, material: Material | None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "title": "",
        "grade": "",
        "subject": "",
        "pain_point": "",
        "teacher_action": "",
        "next_step": "",
        "tone": "",
        "course": "",
    }
    if material is not None:
        context.update(
            {
                "title": material.title or "",
                "grade": material.grade or "",
                "subject": material.subject or "",
                "pain_point": material.pain_point or "",
                "teacher_action": material.teacher_action or "",
                "next_step": material.next_step or "",
            }
        )

    # 成长中心话术作为品牌表达参考（替代已删除的 tone 分类）
    script_entries = (
        db.query(KnowledgeEntry)
        .filter(KnowledgeEntry.category == "script", KnowledgeEntry.is_active.is_(True))
        .order_by(KnowledgeEntry.id.asc())
        .all()
    )
    course_entries = (
        db.query(KnowledgeEntry)
        .filter(KnowledgeEntry.category == "course", KnowledgeEntry.is_active.is_(True))
        .order_by(KnowledgeEntry.id.asc())
        .all()
    )
    if script_entries:
        context["tone"] = "；".join(
            e.content or e.title for e in script_entries if (e.content or e.title)
        )
    if course_entries:
        context["course"] = "；".join(
            e.title or e.content for e in course_entries if (e.title or e.content)
        )
    return context


def _banned_words(db: Session) -> list[str]:
    entries = (
        db.query(KnowledgeEntry)
        .filter(KnowledgeEntry.category == "banned", KnowledgeEntry.is_active.is_(True))
        .order_by(KnowledgeEntry.id.asc())
        .all()
    )
    words: list[str] = []
    for e in entries:
        # Prefer title as the banned phrase; fall back to content if title empty.
        word = (e.title or "").strip() or (e.content or "").strip()
        if word and word not in words:
            words.append(word)
    return words


def _knowledge_snippets(db: Session) -> str:
    parts: list[str] = []
    for category in ("script", "objection", "banned", "course"):
        entries = (
            db.query(KnowledgeEntry)
            .filter(KnowledgeEntry.category == category, KnowledgeEntry.is_active.is_(True))
            .order_by(KnowledgeEntry.id.asc())
            .limit(10)
            .all()
        )
        if not entries:
            continue
        lines = [f"- {e.title}: {e.content}" for e in entries]
        parts.append(f"【{category}】\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _build_llm_messages(
    *,
    context: dict[str, Any],
    template_body: str | None,
    mode: str,
    extra_instruction: str | None,
    knowledge: str,
) -> list[dict[str, str]]:
    system = (
        "你是嘉壹启航的小红书文案助手。输出可直接发布的中文文案，不要解释。"
        "遵守品牌语气与禁用词约束。"
    )
    if knowledge:
        system += f"\n\n机构知识库摘要：\n{knowledge}"

    user_parts = [
        "素材信息：",
        f"- 标题：{context.get('title', '')}",
        f"- 年级：{context.get('grade', '')}",
        f"- 科目：{context.get('subject', '')}",
        f"- 痛点：{context.get('pain_point', '')}",
        f"- 老师处理：{context.get('teacher_action', '')}",
        f"- 下一步：{context.get('next_step', '')}",
    ]
    if template_body:
        if mode == "template_then_llm":
            user_parts.append("\n请在以下模板草稿基础上润色优化：")
        else:
            user_parts.append("\n参考模板：")
        user_parts.append(template_body)
    if extra_instruction:
        user_parts.append(f"\n额外要求：{extra_instruction}")
    if mode == "llm" and not template_body:
        user_parts.append("\n请根据素材信息撰写一篇小红书种草文案。")

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def _friendly_llm_error(exc: BaseException) -> str:
    text = str(exc)
    if "not configured" in text.lower() or "LLM not configured" in text:
        return (
            "大模型未配置：请在项目根目录或 backend 目录创建 .env，"
            "填写 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL 后重启后端。"
            "详见 README-ops-platform.md「可选 AI」。"
        )
    return f"大模型调用失败，已回退模板结果。原因：{text}"


def _fallback_copy_body(context: dict[str, Any], extra_instruction: str | None) -> str:
    parts = [
        f"【{context.get('title') or '嘉壹启航'}】",
        f"痛点：{context.get('pain_point') or '—'}",
        f"老师怎么做：{context.get('teacher_action') or '—'}",
        f"下一步：{context.get('next_step') or '—'}",
    ]
    if extra_instruction:
        parts.append(f"补充：{extra_instruction}")
    parts.append("（当前未调用大模型，以上为本地草稿，配置 LLM 后可自动润色）")
    return "\n".join(parts)


def serialize_copy(
    copy: GeneratedCopy,
    *,
    banned_hits: list[str] | None = None,
    llm_error: str | None = None,
) -> dict[str, Any]:
    return {
        "id": copy.id,
        "material_id": copy.material_id,
        "template_id": copy.template_id,
        "mode": copy.mode,
        "platform": copy.platform,
        "title": copy.title,
        "body": copy.body,
        "prompt_snapshot": copy.prompt_snapshot,
        "model_name": copy.model_name,
        "created_by": copy.created_by,
        "created_at": copy.created_at.isoformat() if copy.created_at else None,
        "banned_hits": banned_hits if banned_hits is not None else [],
        "llm_error": llm_error,
    }


def generate_copy(db: Session, user: User, body: GenerateCopyRequest) -> dict[str, Any]:
    if user.role == "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if user.role not in {"admin", "operator"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    mode = body.mode or "template"
    if mode not in MODES:
        raise HTTPException(status_code=400, detail="Invalid mode")

    material: Material | None = None
    if body.material_id is not None:
        material = db.get(Material, body.material_id)
        if not material:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    template: CopyTemplate | None = None
    if body.template_id is not None:
        template = db.get(CopyTemplate, body.template_id)
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if mode in {"template", "template_then_llm"} and template is None:
        raise HTTPException(status_code=400, detail="template_id is required for this mode")

    context = _build_context(db, material)
    rendered = render_template(template.body if template else "", context) if template else ""
    title = (material.title if material else "") or ""
    final_body = rendered
    prompt_snapshot: str | None = None
    model_name: str | None = None
    llm_error: str | None = None
    settings = get_settings()

    if mode == "template":
        final_body = rendered
    elif mode == "template_then_llm":
        messages = _build_llm_messages(
            context=context,
            template_body=rendered,
            mode=mode,
            extra_instruction=body.extra_instruction,
            knowledge=_knowledge_snippets(db),
        )
        prompt_snapshot = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        try:
            final_body = llm.chat_completion(messages)
            model_name = settings.llm_model
        except LlmUnavailable as exc:
            final_body = rendered or _fallback_copy_body(context, body.extra_instruction)
            llm_error = _friendly_llm_error(exc)
    elif mode == "llm":
        messages = _build_llm_messages(
            context=context,
            template_body=rendered or None,
            mode=mode,
            extra_instruction=body.extra_instruction,
            knowledge=_knowledge_snippets(db),
        )
        prompt_snapshot = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        try:
            final_body = llm.chat_completion(messages)
            model_name = settings.llm_model
        except LlmUnavailable as exc:
            # Graceful degrade: template / local draft instead of hard 503
            final_body = rendered or _fallback_copy_body(context, body.extra_instruction)
            llm_error = _friendly_llm_error(exc)

    banned = find_banned(f"{title}\n{final_body}", _banned_words(db))

    copy = GeneratedCopy(
        material_id=body.material_id,
        template_id=body.template_id,
        mode=mode,
        platform=body.platform or "xhs",
        title=title,
        body=final_body or "",
        prompt_snapshot=prompt_snapshot,
        model_name=model_name,
        created_by=user.id,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return serialize_copy(copy, banned_hits=banned, llm_error=llm_error)


def list_copies(db: Session) -> list[GeneratedCopy]:
    return db.query(GeneratedCopy).order_by(GeneratedCopy.id.desc()).all()


def update_copy(db: Session, copy_id: int, body: GeneratedCopyUpdate) -> GeneratedCopy:
    copy = db.get(GeneratedCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated copy not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(copy, key, value)

    db.commit()
    db.refresh(copy)
    return copy


def delete_copy(db: Session, copy_id: int) -> None:
    copy = db.get(GeneratedCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated copy not found")
    db.delete(copy)
    db.commit()
