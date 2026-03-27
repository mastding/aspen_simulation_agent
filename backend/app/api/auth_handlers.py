from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.auth import auth_service
from typing import Dict, Any

router = APIRouter(prefix="/api/auth")
admin_router = APIRouter(prefix="/api/admin")

_deps: Dict[str, Any] = {}


def init_auth_handlers(deps: Dict[str, Any]):
    global _deps
    _deps = deps


@router.post("/login")
async def login(request: Request):
    body = await request.json()
    phone = str(body.get("phone", "")).strip()
    password = body.get("password")
    try:
        if password:
            result = auth_service.login_by_password(phone=phone, password=password, deps=_deps)
        else:
            return JSONResponse(status_code=400, content={"detail": "请提供密码"})
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})


@router.post("/register")
async def register(request: Request):
    body = await request.json()
    phone = str(body.get("phone", "")).strip()
    password = str(body.get("password", "")).strip()
    try:
        result = auth_service.register_by_password(phone=phone, password=password, deps=_deps)
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})


@admin_router.get("/users")
async def list_users(request: Request):
    if getattr(request.state, "user_role", None) != "admin":
        return JSONResponse(status_code=403, content={"detail": "无权限"})
    db_connect_fn = _deps["db_connect_fn"]
    with db_connect_fn() as conn:
        rows = conn.execute("SELECT user_id, phone, role, created_at FROM users ORDER BY created_at DESC").fetchall()
        users = [dict(r) for r in rows]
    return {"users": users}


@admin_router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, request: Request):
    if getattr(request.state, "user_role", None) != "admin":
        return JSONResponse(status_code=403, content={"detail": "无权限"})
    body = await request.json()
    new_password = str(body.get("new_password", "")).strip()
    try:
        result = auth_service.reset_user_password(user_id=user_id, new_password=new_password, deps=_deps)
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})


@admin_router.post("/users/{user_id}/delete")
async def delete_user(user_id: str, request: Request):
    if getattr(request.state, "user_role", None) != "admin":
        return JSONResponse(status_code=403, content={"detail": "无权限"})
    try:
        result = auth_service.delete_user(user_id=user_id, deps=_deps)
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
