import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router

app = FastAPI(title="AI Platform API")

# Frontend（Vite dev サーバ等）からのアクセスを許可。
# 値はカンマ区切りで CORS_ORIGINS から上書きできる。
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 共通パスワードによる簡易ログインゲート。
# APP_PASSWORD が設定されているときだけ有効。設定が無ければ素通り（開発/テスト）。
# ゲート対象外: ヘルスチェックとログイン関連（フロントが最初に叩くため）。
_OPEN_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/config",
}


@app.middleware("http")
async def app_password_gate(request: Request, call_next):
    password = os.getenv("APP_PASSWORD", "")
    path = request.url.path
    if (
        password
        and request.method != "OPTIONS"
        and path.startswith("/api/v1")
        and path not in _OPEN_PATHS
    ):
        if request.headers.get("X-App-Token") != password:
            return JSONResponse({"detail": "ログインが必要です"}, status_code=401)
    return await call_next(request)


app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
