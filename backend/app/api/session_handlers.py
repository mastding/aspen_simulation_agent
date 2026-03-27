from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import time
import json

router = APIRouter(prefix="/api/sessions")
_deps = {}


def init_session_handlers(deps):
    global _deps
    _deps = deps


@router.get("")
async def list_sessions(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return {"sessions": []}
    db_connect_fn = _deps["db_connect_fn"]
    with db_connect_fn() as conn:
        rows = conn.execute(
            "SELECT session_id, title, updated_at FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return {"sessions": [dict(r) for r in rows]}


@router.post("/{session_id}")
async def upsert_session(session_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "未登录"})
    body = await request.json()
    title = body.get("title", "新对话")
    messages = body.get("messages")
    base_updated_at = body.get("base_updated_at")
    force = bool(body.get("force"))
    db_connect_fn = _deps["db_connect_fn"]
    with db_connect_fn() as conn:
        now = time.time()
        existing = conn.execute(
            "SELECT id, title, messages_json, updated_at FROM chat_sessions WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if existing:
            current_updated_at = float(existing["updated_at"] or 0)
            if base_updated_at is not None and not force:
                try:
                    expected_updated_at = float(base_updated_at)
                except Exception:
                    expected_updated_at = None
                if expected_updated_at is not None and abs(current_updated_at - expected_updated_at) > 1e-6:
                    try:
                        current_messages = json.loads(existing["messages_json"] or "[]")
                    except Exception:
                        current_messages = []
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": "session_conflict",
                            "session": {
                                "session_id": session_id,
                                "title": existing["title"] or "新对话",
                                "messages": current_messages,
                                "updated_at": current_updated_at,
                            },
                        },
                    )
            if messages is not None:
                conn.execute(
                    "UPDATE chat_sessions SET messages_json = ?, title = ?, updated_at = ? WHERE session_id = ? AND user_id = ?",
                    (json.dumps(messages, ensure_ascii=False), title, now, session_id, user_id),
                )
            elif title:
                conn.execute(
                    "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ? AND user_id = ?",
                    (title, now, session_id, user_id),
                )
        else:
            conn.execute(
                "INSERT INTO chat_sessions (session_id, user_id, title, messages_json, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (session_id, user_id, title, json.dumps(messages or [], ensure_ascii=False), now, now),
            )
        conn.commit()
    return {
        "ok": True,
        "session": {
            "session_id": session_id,
            "title": title or "新对话",
            "updated_at": now,
        },
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "未登录"})
    db_connect_fn = _deps["db_connect_fn"]
    with db_connect_fn() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE session_id = ? AND user_id = ?", (session_id, user_id))
        conn.commit()
    return {"ok": True}


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "未登录"})
    db_connect_fn = _deps["db_connect_fn"]
    with db_connect_fn() as conn:
        row = conn.execute(
            "SELECT title, messages_json, updated_at FROM chat_sessions WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not row:
            return {"messages": [], "title": "新对话", "updated_at": None}
        try:
            messages = json.loads(row["messages_json"] or "[]")
        except Exception:
            messages = []
        return {
            "messages": messages,
            "title": row["title"] or "新对话",
            "updated_at": row["updated_at"],
        }
