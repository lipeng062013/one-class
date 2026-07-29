from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.responses import fail, ok
from app.models.todo import TodoItem
from app.models.user import User
from app.modules.todos.schemas import TodoCreate, TodoUpdate

router = APIRouter(prefix="/todos", tags=["todos"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ser(t: TodoItem) -> dict:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "title": t.title,
        "content": t.content or "",
        "is_done": bool(t.is_done),
        "created_at": t.created_at,
        "completed_at": t.completed_at,
    }


@router.get("")
def list_todos(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(TodoItem)
        .filter(TodoItem.user_id == user.id)
        .order_by(TodoItem.is_done.asc(), TodoItem.id.desc())
        .all()
    )
    return ok([_ser(t) for t in rows])


@router.post("")
def create_todo(
    body: TodoCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    title = body.title.strip()
    if not title:
        return fail("INVALID", "请填写待办标题", status_code=400)
    item = TodoItem(
        user_id=user.id,
        title=title,
        content=(body.content or "").strip(),
        is_done=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ok(_ser(item), status_code=201)


@router.patch("/{todo_id}")
def patch_todo(
    todo_id: int,
    body: TodoUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(TodoItem, todo_id)
    if not item or item.user_id != user.id:
        return fail("NOT_FOUND", "待办不存在", status_code=404)
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        title = str(data["title"]).strip()
        if not title:
            return fail("INVALID", "标题不能为空", status_code=400)
        item.title = title
    if "content" in data and data["content"] is not None:
        item.content = str(data["content"])
    if "is_done" in data and data["is_done"] is not None:
        item.is_done = bool(data["is_done"])
        item.completed_at = _utcnow() if item.is_done else None
    db.commit()
    db.refresh(item)
    return ok(_ser(item))


@router.delete("/{todo_id}")
def delete_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(TodoItem, todo_id)
    if not item or item.user_id != user.id:
        return fail("NOT_FOUND", "待办不存在", status_code=404)
    db.delete(item)
    db.commit()
    return ok({"deleted": True, "id": todo_id})
