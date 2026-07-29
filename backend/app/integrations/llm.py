from __future__ import annotations

import httpx

from app.core.config import get_settings


class LlmUnavailable(Exception):
    """Raised when the LLM is not configured or the upstream call fails."""


def chat_completion(messages: list[dict], **kwargs) -> str:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_base_url:
        raise LlmUnavailable("LLM not configured")

    model = kwargs.get("model") or settings.llm_model
    timeout = kwargs.get("timeout", 60.0)
    base = settings.llm_base_url.rstrip("/")
    url = f"{base}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
    }
    if "temperature" in kwargs:
        payload["temperature"] = kwargs["temperature"]

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise LlmUnavailable(f"LLM request failed: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmUnavailable("LLM response missing content") from exc
    if content is None:
        raise LlmUnavailable("LLM response content is empty")
    return str(content)
