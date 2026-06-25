"""Agent レジストリのルータ。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_current_user, require_admin
from backend.models.schemas import Agent, AgentCreate, AgentView, ResourceAccess, User
from backend.store.memory import store

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentView])
def list_agents(user: User = Depends(get_current_user)) -> list[AgentView]:
    """全 Agent を返す。属性ベースで利用可能か（allowed）を付ける。

    使えない Agent も一覧には出す（フロントで非活性表示する）。
    """
    allowed = store.allowed_agent_ids(user)
    return [
        AgentView(**a.model_dump(), allowed=a.id in allowed)
        for a in store.list_agents()
    ]


@router.post("", response_model=Agent, status_code=status.HTTP_201_CREATED)
def create_agent(data: AgentCreate, _: User = Depends(require_admin)) -> Agent:
    return store.add_agent(data)


@router.put("/{agent_id}/access", response_model=Agent)
def set_agent_access(
    agent_id: str, body: ResourceAccess, _: User = Depends(require_admin)
) -> Agent:
    """Agent のアクセスポリシー（利用可能な属性）を設定する。"""
    agent = store.set_agent_access(agent_id, body.access)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent が見つかりません")
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, _: User = Depends(require_admin)) -> None:
    if not store.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent が見つかりません")
