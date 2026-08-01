from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.image_thumb import DEFAULT_THUMB_EDGE, read_image_variant
from app.core.responses import fail, ok
from app.core.storage import Storage, get_storage
from app.models.material import MaterialFile
from app.models.user import User
from app.modules.materials.schemas import MaterialCreate, MaterialUpdate
from app.modules.materials.service import (
    add_file,
    can_delete,
    can_patch,
    can_upload_file,
    can_view,
    create_material,
    delete_material,
    get_material,
    list_materials,
    material_to_dict,
    update_material,
)

router = APIRouter(prefix="/materials", tags=["materials"])

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}
MAX_FILE_SIZE = 8 * 1024 * 1024  # 8MB


@router.get("")
def get_materials(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，最大 100"),
    status: str | None = Query(None, description="素材状态"),
    grade: str | None = Query(None),
    subject: str | None = Query(None),
    q: str | None = Query(None, description="关键词：标题/痛点/处理等"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = list_materials(
        db,
        user,
        page=page,
        page_size=page_size,
        status=status,
        grade=grade,
        subject=subject,
        q=q,
    )
    return ok(
        {
            "items": [material_to_dict(m) for m in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.post("")
def post_material(
    body: MaterialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = create_material(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("MATERIAL_CREATE_FAILED", result, status_code=400)
    return ok(material_to_dict(result), status_code=201)


@router.get("/files/{file_id}/content")
def download_material_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
    thumb: bool = Query(False, description="返回列表/网格用缩略图"),
    w: int | None = Query(None, ge=64, le=1280, description="缩略图最长边，默认 640"),
):
    mf = db.get(MaterialFile, file_id)
    if not mf:
        return fail("NOT_FOUND", "文件不存在", status_code=404)
    material = get_material(db, mf.material_id)
    if not material or not can_view(user, material):
        return fail("FORBIDDEN", "无权限", status_code=403)
    try:
        data, media_type = read_image_variant(
            storage,
            mf.file_path,
            thumb=thumb,
            max_edge=w or DEFAULT_THUMB_EDGE,
            original_media_type=mf.file_type or None,
        )
    except FileNotFoundError:
        return fail("NOT_FOUND", "文件不存在", status_code=404)

    headers = {"Cache-Control": "private, max-age=86400"} if thumb else {}
    return Response(content=data, media_type=media_type, headers=headers)


@router.get("/{material_id}")
def get_one(
    material_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = get_material(db, material_id)
    if not m:
        return fail("NOT_FOUND", "素材不存在", status_code=404)
    if not can_view(user, m):
        return fail("FORBIDDEN", "无权限", status_code=403)
    return ok(material_to_dict(m))


@router.patch("/{material_id}")
def patch_material(
    material_id: int,
    body: MaterialUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = get_material(db, material_id)
    if not m:
        return fail("NOT_FOUND", "素材不存在", status_code=404)
    if not can_patch(user, m):
        return fail("FORBIDDEN", "无权限", status_code=403)
    result = update_material(db, user, m, body.model_dump(exclude_unset=True))
    if isinstance(result, str):
        code = 403 if "无权限" in result or "不能修改" in result else 400
        return fail("MATERIAL_UPDATE_FAILED", result, status_code=code)
    return ok(material_to_dict(result))


@router.delete("/{material_id}")
def remove_material(
    material_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = get_material(db, material_id)
    if not m:
        return fail("NOT_FOUND", "素材不存在", status_code=404)
    if not can_delete(user, m):
        return fail("FORBIDDEN", "无权限删除", status_code=403)
    delete_material(db, m)
    return ok({"deleted": True, "id": material_id})


@router.post("/{material_id}/files")
async def upload_file(
    material_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
):
    m = get_material(db, material_id)
    if not m:
        return fail("NOT_FOUND", "素材不存在", status_code=404)
    if not can_upload_file(user, m):
        return fail("FORBIDDEN", "无权限", status_code=403)

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_IMAGE_TYPES and not content_type.startswith("image/"):
        return fail("INVALID_FILE", "仅支持图片上传", status_code=400)

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        return fail("FILE_TOO_LARGE", "单文件不能超过 8MB", status_code=400)
    if not data:
        return fail("EMPTY_FILE", "文件为空", status_code=400)

    mf = add_file(
        db,
        storage,
        m,
        filename=file.filename or "upload.bin",
        content=data,
        content_type=content_type,
    )
    return ok(
        {
            "id": mf.id,
            "file_path": mf.file_path,
            "file_type": mf.file_type,
            "sort_order": mf.sort_order,
        },
        status_code=201,
    )
