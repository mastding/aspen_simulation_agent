import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, deps):
        super().__init__(app)
        self.deps = deps

    async def dispatch(self, request, call_next):
        # Always allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Public paths
        if path.startswith("/api/auth/") or path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)
        if path.startswith(("/static", "/assets")):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "未登录"})

        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(
                token,
                self.deps["jwt_secret"],
                algorithms=[self.deps["jwt_algorithm"]],
            )
            request.state.user_id = payload.get("user_id")
            request.state.user_phone = payload.get("phone")
            request.state.user_role = payload.get("role")
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "登录已过期"})
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "无效的令牌"})

        return await call_next(request)
