from __future__ import annotations

import base64

import httpx

from app.core.config import get_settings


class ImageApiUnavailable(Exception):
    """Raised when the image API is not configured or the upstream call fails."""


def _extract_image_bytes(data: dict, *, timeout: float) -> bytes:
    """Parse OpenAI-compatible images response (b64_json and/or url)."""
    try:
        item = data["data"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ImageApiUnavailable("Image API response missing image data") from exc
    if not isinstance(item, dict):
        raise ImageApiUnavailable("Image API response missing image data")

    b64 = item.get("b64_json")
    if b64:
        try:
            return base64.b64decode(b64)
        except Exception as exc:
            raise ImageApiUnavailable(f"Failed to decode image data: {exc}") from exc

    url = item.get("url")
    if url:
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                img_resp = client.get(url)
                img_resp.raise_for_status()
                content = img_resp.content
        except httpx.HTTPError as exc:
            raise ImageApiUnavailable(f"Failed to download generated image: {exc}") from exc
        if not content:
            raise ImageApiUnavailable("Downloaded image is empty")
        return content

    raise ImageApiUnavailable("Image API response missing b64_json and url")


def generate_image(**kwargs) -> bytes:
    """Call the configured image API and return raw image bytes.

    Accepts keyword args such as ``prompt``, ``model``, ``timeout``, ``size``.
    Raises ``ImageApiUnavailable`` when API base URL / key are missing or the
    upstream call fails.
    """
    settings = get_settings()
    if not settings.image_api_key or not settings.image_api_base_url:
        raise ImageApiUnavailable(
            "IMAGE_API not configured (set IMAGE_API_BASE_URL and IMAGE_API_KEY in .env, then restart backend)"
        )

    prompt = kwargs.get("prompt") or kwargs.get("title") or ""
    model = kwargs.get("model") or settings.image_model or "dall-e-3"
    # Image generation is often 30–90s on relay providers.
    timeout = float(kwargs.get("timeout", 120.0))
    base = settings.image_api_base_url.rstrip("/")
    url = f"{base}/v1/images/generations"
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "response_format": "b64_json",
    }
    size = kwargs.get("size")
    if size:
        payload["size"] = size

    headers = {
        "Authorization": f"Bearer {settings.image_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError as exc:
        raise ImageApiUnavailable(
            f"Image API connect failed (check IMAGE_API_BASE_URL DNS/SSL/network): {exc}"
        ) from exc
    except httpx.TimeoutException as exc:
        raise ImageApiUnavailable(f"Image API timeout after {timeout:.0f}s: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            body = exc.response.json()
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict):
                detail = str(err.get("message") or err)
            elif isinstance(body, dict) and body.get("message"):
                detail = str(body["message"])
            else:
                detail = (exc.response.text or "")[:300]
        except Exception:
            detail = (exc.response.text or "")[:300]
        msg = f"Image API HTTP {exc.response.status_code}"
        if detail:
            msg = f"{msg}: {detail}"
        raise ImageApiUnavailable(msg) from exc
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise ImageApiUnavailable(f"Image API request failed: {exc}") from exc

    return _extract_image_bytes(data, timeout=timeout)
