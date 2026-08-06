from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.deps import require_permissions
from app.core.responses import ok
from app.models.user import User

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/integrations")
def integrations_status(
    _: User = Depends(require_permissions("system.read")),
):
    """Return whether optional AI providers are configured (never expose keys)."""
    settings = get_settings()
    llm_ready = bool(settings.llm_base_url and settings.llm_api_key)
    image_ready = bool(settings.image_api_base_url and settings.image_api_key)
    return ok(
        {
            "app_env": settings.app_env,
            "seed_demo_data": settings.should_seed_demo_data,
            "storage_backend": settings.storage_backend,
            "llm": {
                "configured": llm_ready,
                "model": settings.llm_model if llm_ready else None,
                "base_url_set": bool(settings.llm_base_url),
            },
            "image": {
                "configured": image_ready,
                "model": settings.image_model if image_ready else None,
                "base_url_set": bool(settings.image_api_base_url),
            },
            "notes": {
                "copy_template_then_llm": "未配置或上游失败时回退模板结果",
                "copy_llm_only": "未配置时接口返回 503",
                "poster_ai_image": "未配置时需改用版式导出",
                "data_split": "development 用 data/dev（演示数据）；production 用 data/prod（正式业务）",
            },
        }
    )
