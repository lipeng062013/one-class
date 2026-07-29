from __future__ import annotations

import base64

import httpx

from app.core.config import get_settings


class ImageApiUnavailable(Exception):
    """Raised when the image API is not configured or the upstream call fails."""


def generate_image(**kwargs) -> bytes:
    """Call the configured image API and return raw image bytes.

    Accepts keyword args such as ``prompt``, ``model``, ``timeout``.
    Raises ``ImageApiUnavailable`` when API base URL / key are missing.
    """
    settings = get_settings()
    if not settings.image_api_key or not settings.image_api_base_url:
        raise ImageApiUnavailable("IMAGE_API not configured")

    prompt = kwargs.get("prompt") or kwargs.get("title") or ""
    model = kwargs.get("model") or settings.image_model or "dall-e-3"
    timeout = kwargs.get("timeout", 60.0)
    base = settings.image_api_base_url.rstrip("/")
    url = f"{base}/v1/images/generations"
    payload = {
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
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise ImageApiUnavailable(f"Image API request failed: {exc}") from exc

    try:
        b64 = data["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ImageApiUnavailable("Image API response missing image data") from exc
    try:
        return base64.b64decode(b64)
    except Exception as exc:
        raise ImageApiUnavailable(f"Failed to decode image data: {exc}") from exc
