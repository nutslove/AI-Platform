"""MCP サーバ レジストリのルータ。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_current_user, require_admin
from backend.models.schemas import (
    McpServer,
    McpServerCreate,
    McpServerView,
    ResourceAccess,
    User,
)
from backend.store.memory import store

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


@router.get("", response_model=list[McpServerView])
def list_mcp_servers(user: User = Depends(get_current_user)) -> list[McpServerView]:
    """全 MCP サーバを返す。属性ベースで利用可能か（allowed）を付ける。"""
    allowed = store.allowed_mcp_server_ids(user)
    return [
        McpServerView(**m.model_dump(), allowed=m.id in allowed)
        for m in store.list_mcp_servers()
    ]


@router.post("", response_model=McpServer, status_code=status.HTTP_201_CREATED)
def create_mcp_server(
    data: McpServerCreate, _: User = Depends(require_admin)
) -> McpServer:
    return store.add_mcp_server(data)


@router.put("/{server_id}/access", response_model=McpServer)
def set_mcp_access(
    server_id: str, body: ResourceAccess, _: User = Depends(require_admin)
) -> McpServer:
    """MCP サーバのアクセスポリシー（利用可能な属性）を設定する。"""
    server = store.set_mcp_access(server_id, body.access)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP サーバが見つかりません")
    return server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp_server(server_id: str, _: User = Depends(require_admin)) -> None:
    if not store.delete_mcp_server(server_id):
        raise HTTPException(status_code=404, detail="MCP サーバが見つかりません")
