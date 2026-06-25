"""カスタム Agent（既存 Agent + MCP サーバの組み合わせ）のルータ。

ユーザは自分が有効化済みの Agent / MCP サーバを組み合わせて独自の Agent を
保存し、ワンクリックで実行できる。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from fastapi.responses import StreamingResponse

from backend.api.deps import get_current_user
from backend.api.execution import (
    SSE_HEADERS,
    run_composition,
    stream_composition,
    validate_enablements,
)
from backend.models.schemas import (
    CustomAgent,
    CustomAgentCreate,
    ExecuteRequest,
    ExecuteResponse,
    User,
)
from backend.store.memory import store

router = APIRouter(prefix="/me/custom-agents", tags=["custom-agents"])


@router.get("", response_model=list[CustomAgent])
def list_custom_agents(user: User = Depends(get_current_user)) -> list[CustomAgent]:
    return store.list_custom_agents(user.id)


@router.post("", response_model=CustomAgent, status_code=201)
def create_custom_agent(
    data: CustomAgentCreate, user: User = Depends(get_current_user)
) -> CustomAgent:
    # 組み合わせに使えるのは「有効化済み」の Agent / MCP サーバのみ
    enab = store.get_enablements(user)
    if not set(data.agent_ids) <= set(enab.enabled_agent_ids):
        raise HTTPException(status_code=400, detail="有効化されていない Agent が含まれます")
    if not set(data.mcp_server_ids) <= set(enab.enabled_mcp_server_ids):
        raise HTTPException(status_code=400, detail="有効化されていない MCP サーバが含まれます")
    if not data.agent_ids:
        raise HTTPException(status_code=400, detail="Agent を 1 つ以上選択してください")
    return store.add_custom_agent(user.id, data)


@router.delete("/{custom_id}", status_code=204)
def delete_custom_agent(custom_id: str, user: User = Depends(get_current_user)) -> None:
    custom = store.get_custom_agent(custom_id)
    if custom is None or custom.owner_id != user.id:
        raise HTTPException(status_code=404, detail="カスタム Agent が見つかりません")
    store.delete_custom_agent(custom_id)


@router.post("/{custom_id}/run", response_model=ExecuteResponse)
def run_custom_agent(
    custom_id: str, req: ExecuteRequest, user: User = Depends(get_current_user)
) -> ExecuteResponse:
    custom = store.get_custom_agent(custom_id)
    if custom is None or custom.owner_id != user.id:
        raise HTTPException(status_code=404, detail="カスタム Agent が見つかりません")
    # 構成は保存済みのものを使い、入力だけリクエストから受け取る
    return run_composition(user, custom.agent_ids, custom.mcp_server_ids, req.input)


@router.post("/{custom_id}/run/stream")
def run_custom_agent_stream(
    custom_id: str, req: ExecuteRequest, user: User = Depends(get_current_user)
) -> StreamingResponse:
    custom = store.get_custom_agent(custom_id)
    if custom is None or custom.owner_id != user.id:
        raise HTTPException(status_code=404, detail="カスタム Agent が見つかりません")
    validate_enablements(user, custom.agent_ids, custom.mcp_server_ids)
    return StreamingResponse(
        stream_composition(user, custom.agent_ids, custom.mcp_server_ids, req.input),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
