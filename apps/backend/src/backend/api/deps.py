"""共通の依存（認証・認可）。

簡易認証: ``X-User-Id`` ヘッダで現在のユーザを識別する。
本番では OIDC / JWT 検証に差し替える。
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from backend.models.schemas import User
from backend.store.memory import store


def get_current_user(x_user_id: str | None = Header(default=None)) -> User:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id ヘッダがありません",
        )
    user = store.get_user(x_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="不明なユーザです",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理者権限が必要です",
        )
    return user
