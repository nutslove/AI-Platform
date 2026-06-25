"""ユーザ一覧・現在ユーザ・属性（ABAC）管理 + 簡易ログインのルータ。"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_current_user, require_admin
from backend.models.schemas import User, UserAttributes
from backend.store.memory import store

router = APIRouter(tags=["users"])


# --- 簡易ログイン（.env の共通パスワード）---


class LoginRequest(BaseModel):
    password: str


@router.get("/auth/config")
def auth_config() -> dict[str, bool]:
    """ログインが必要かをフロントに伝える（APP_PASSWORD が設定されていれば true）。"""
    return {"login_required": bool(os.getenv("APP_PASSWORD", ""))}


@router.post("/auth/login")
def login(body: LoginRequest) -> dict[str, str]:
    """共通パスワードでログイン。成功するとアプリトークン（=パスワード）を返す。"""
    password = os.getenv("APP_PASSWORD", "")
    if password and body.password != password:
        raise HTTPException(status_code=401, detail="パスワードが違います")
    return {"token": body.password}


@router.get("/auth/verify")
def auth_verify() -> dict[str, bool]:
    """保存済みトークンの有効性確認（ゲートを通過できれば 200）。"""
    return {"ok": True}


@router.get("/auth/users", response_model=list[User])
def login_users() -> list[User]:
    """簡易ログインのユーザ選択用（デモ専用・無認証）。"""
    return store.list_users()


@router.get("/me", response_model=User)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/users", response_model=list[User])
def list_users(_: User = Depends(require_admin)) -> list[User]:
    return store.list_users()


@router.put("/users/{user_id}/attributes", response_model=User)
def set_user_attributes(
    user_id: str, body: UserAttributes, _: User = Depends(require_admin)
) -> User:
    """ユーザの属性（部署など）を設定する。"""
    user = store.set_user_attributes(user_id, body.attributes)
    if user is None:
        raise HTTPException(status_code=404, detail="ユーザが見つかりません")
    return user


@router.get("/departments", response_model=list[str])
def list_departments(_: User = Depends(get_current_user)) -> list[str]:
    """属性 department の選択肢（ABAC 管理 UI 用）。"""
    return store.departments()
