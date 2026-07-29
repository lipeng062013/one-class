from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.responses import fail, ok
from app.core.storage import LocalStorage, get_storage
from app.models.user import User
from app.modules.materials.schemas import MaterialCreate, MaterialUpdate
from app.modules.materials.service import (
    add_file,
    can_patch,
    can_upload_file,
    can_view,
    create_material,
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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = list_materials(db, user)
    return ok([material_to_dict(m) for m in items])


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


@router.post("/{material_id}/files")
async def upload_file(
    material_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: LocalStorage = Depends(get_storage),
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
