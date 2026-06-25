"""ユーザ自身の有効化（enablement）設定のルータ。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user
from backend.models.schemas import Enablements, User
from backend.store.memory import store

router = APIRouter(prefix="/me/enablements", tags=["enablements"])


@router.get("", response_model=Enablements)
def get_enablements(user: User = Depends(get_current_user)) -> Enablements:
    return store.get_enablements(user)


@router.put("", response_model=Enablements)
def set_enablements(
    enab: Enablements, user: User = Depends(get_current_user)
) -> Enablements:
    """有効化は属性ベースで利用可能な集合（allowed）の部分集合でなければならない。"""
    if not set(enab.enabled_agent_ids) <= store.allowed_agent_ids(user):
        raise HTTPException(
            status_code=403, detail="許可されていない Agent を有効化しようとしました"
        )
    if not set(enab.enabled_mcp_server_ids) <= store.allowed_mcp_server_ids(user):
        raise HTTPException(
            status_code=403, detail="許可されていない MCP サーバを有効化しようとしました"
        )
    return store.set_enablements(user, enab)
