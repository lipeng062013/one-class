"""Proxy OpenAI-compatible image APIs for the embedded GPT Image Playground.

Playground ``normalizeBaseUrl`` truncates at the **first** ``/v1`` in the path.
Therefore the browser-facing proxy base MUST be ``/image-api/v1`` (only one
``v1``, at the end) — NOT under ``/api/v1/.../v1``, which would collapse to
``/api/v1`` and 404.

Auth: playground sends ``Authorization: Bearer <login JWT>``.
This proxy validates admin/operator, then calls upstream with ``IMAGE_API_KEY``.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.deps import require_permissions
from app.core.responses import ok
from app.models.user import User

# Config stays with the rest of the app API (axios baseURL /api/v1).
config_router = APIRouter(prefix="/image-playground", tags=["image-playground"])

# Proxy is mounted at app root as /image-api/v1/* (see main.py).
proxy_router = APIRouter(prefix="/image-api", tags=["image-playground"])

_ops = require_permissions("ai_image.use")

_ALLOWED_PREFIXES = (
    "images/",
    "chat/",
    "responses",
    "models",
)

# Public path for playground baseUrl (same-origin, single trailing /v1).
PLAYGROUND_PROXY_BASE_PATH = "/image-api/v1"


def _upstream_base() -> str:
    settings = get_settings()
    base = (settings.image_api_base_url or "").rstrip("/")
    if not base:
        return ""
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def _path_allowed(path: str) -> bool:
    cleaned = path.lstrip("/")
    return any(cleaned == p.rstrip("/") or cleaned.startswith(p) for p in _ALLOWED_PREFIXES)


@config_router.get("/config")
def playground_config(
    _: User = Depends(_ops),
):
    """Bootstrap GPT Image Playground (no upstream URL/key leaked)."""
    settings = get_settings()
    ready = bool(settings.image_api_base_url and settings.image_api_key)
    return ok(
        {
            "ready": ready,
            "model": (settings.image_model or "gpt-image-2") if ready else "",
            "api_base_path": PLAYGROUND_PROXY_BASE_PATH,
            "notes": {
                "proxy": "浏览器走 /image-api/v1 同源代理；真实 IMAGE_API_* 仅在服务端",
                "auth": "Playground API Key 使用当前登录 JWT",
            },
        }
    )


@proxy_router.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def openai_compatible_proxy(
    path: str,
    request: Request,
    user: User = Depends(_ops),
):
    """Forward OpenAI-compatible calls to the configured image provider."""
    _ = user
    settings = get_settings()
    if not settings.image_api_base_url or not settings.image_api_key:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "message": "IMAGE_API not configured (set IMAGE_API_BASE_URL and IMAGE_API_KEY)",
                    "type": "config_error",
                }
            },
        )

    if not _path_allowed(path):
        return JSONResponse(
            status_code=404,
            content={"error": {"message": f"Proxy path not allowed: {path}", "type": "not_found"}},
        )

    upstream = f"{_upstream_base().rstrip('/')}/{path.lstrip('/')}"
    if request.url.query:
        upstream = f"{upstream}?{request.url.query}"

    forward_headers: dict[str, str] = {
        "Authorization": f"Bearer {settings.image_api_key}",
    }
    content_type = request.headers.get("content-type")
    if content_type:
        forward_headers["Content-Type"] = content_type
    accept = request.headers.get("accept")
    if accept:
        forward_headers["Accept"] = accept

    body = await request.body()
    timeout = httpx.Timeout(connect=30.0, read=300.0, write=120.0, pool=30.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            upstream_resp = await client.request(
                request.method,
                upstream,
                headers=forward_headers,
                content=body if body else None,
            )
    except httpx.ConnectError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Image API connect failed: {exc}",
                    "type": "connect_error",
                }
            },
        )
    except httpx.TimeoutException as exc:
        return JSONResponse(
            status_code=504,
            content={
                "error": {
                    "message": f"Image API timeout: {exc}",
                    "type": "timeout",
                }
            },
        )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Image API request failed: {exc}",
                    "type": "http_error",
                }
            },
        )

    excluded = {
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
    }
    out_headers = {
        k: v
        for k, v in upstream_resp.headers.items()
        if k.lower() not in excluded
    }
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=out_headers,
        media_type=upstream_resp.headers.get("content-type"),
    )


# Back-compat alias used by main.py imports
router = config_router
