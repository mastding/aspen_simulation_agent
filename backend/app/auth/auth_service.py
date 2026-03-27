import os
import time
import uuid
import bcrypt
import jwt
import re
from typing import Dict, Any

MOCK_CODE = "123456"

def _gen_user_id() -> str:
    return "usr_" + uuid.uuid4().hex[:5]

def _now() -> float:
    return time.time()

def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("密码长度不能少于8位，且必须包含字母和数字")
    if not re.search(r'[a-zA-Z]', password):
        raise ValueError("密码长度不能少于8位，且必须包含字母和数字")
    if not re.search(r'[0-9]', password):
        raise ValueError("密码长度不能少于8位，且必须包含字母和数字")

def create_jwt_token(*, user_id: str, phone: str, role: str, deps: Dict[str, Any]) -> str:
    secret = deps["jwt_secret"]
    algo = deps["jwt_algorithm"]
    payload = {
        "user_id": user_id,
        "phone": phone,
        "role": role,
        "exp": time.time() + (3600 * 24 * 7),
    }
    return jwt.encode(payload, secret, algorithm=algo)

def register_by_password(*, phone: str, password: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    if not phone or len(phone) < 2:
        raise ValueError("用户名格式不正确")
    if phone.lower() == "admin":
        raise ValueError("不能使用 admin 作为用户名")
    _validate_password(password)
    db_connect_fn = deps["db_connect_fn"]
    with db_connect_fn() as conn:
        existing = conn.execute("SELECT id FROM users WHERE phone = ?", (phone,)).fetchone()
        if existing:
            raise ValueError("该用户名已注册")
        user_id = _gen_user_id()
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        now = _now()
        conn.execute(
            "INSERT INTO users (user_id, phone, password, role, nickname, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, phone, hashed, "user", "", now, now),
        )
        conn.commit()
    token = create_jwt_token(user_id=user_id, phone=phone, role="user", deps=deps)
    return {"token": token, "user": {"user_id": user_id, "phone": phone, "role": "user", "nickname": ""}}


def login_by_password(*, phone: str, password: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    db_connect_fn = deps["db_connect_fn"]
    with db_connect_fn() as conn:
        row = conn.execute("SELECT user_id, phone, password, role, nickname FROM users WHERE phone = ?", (phone,)).fetchone()
        if not row:
            raise ValueError("用户不存在")
        if not row["password"]:
            raise ValueError("该用户未设置密码")
        if not bcrypt.checkpw(password.encode(), row["password"].encode()):
            raise ValueError("密码错误")
        user_id = row["user_id"]
        role = row["role"]
        nickname = row["nickname"]
    token = create_jwt_token(user_id=user_id, phone=phone, role=role, deps=deps)
    return {"token": token, "user": {"user_id": user_id, "phone": phone, "role": role, "nickname": nickname}}


def create_default_admin(deps: Dict[str, Any]):
    db_connect_fn = deps["db_connect_fn"]
    admin_phone = "admin"
    admin_pwd = os.getenv("ADMIN_PASSWORD", "admin123")
    with db_connect_fn() as conn:
        row = conn.execute("SELECT id FROM users WHERE phone = ?", (admin_phone,)).fetchone()
        if not row:
            user_id = "admin-root"
            hashed = bcrypt.hashpw(admin_pwd.encode(), bcrypt.gensalt()).decode()
            now = _now()
            conn.execute(
                "INSERT INTO users (user_id, phone, password, role, nickname, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, admin_phone, hashed, "admin", "Administrator", now, now),
            )
            conn.commit()


def reset_user_password(*, user_id: str, new_password: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    _validate_password(new_password)
    db_connect_fn = deps["db_connect_fn"]
    with db_connect_fn() as conn:
        row = conn.execute("SELECT id, phone FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            raise ValueError("用户不存在")
        hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        now = _now()
        conn.execute("UPDATE users SET password = ?, updated_at = ? WHERE user_id = ?", (hashed, now, user_id))
        conn.commit()
    return {"ok": True, "message": f"用户 {row['phone']} 的密码已重置"}


def delete_user(*, user_id: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    db_connect_fn = deps["db_connect_fn"]
    with db_connect_fn() as conn:
        row = conn.execute("SELECT phone, role FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            raise ValueError("用户不存在")
        if row["role"] == "admin":
            raise ValueError("不能删除管理员账号")
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM chat_sessions WHERE user_id = ?", (user_id,))
        conn.commit()
    return {"ok": True, "message": f"用户 {row['phone']} 已删除"}
