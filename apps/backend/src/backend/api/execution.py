"""Agent / MCP サーバを組み合わせて実行するルータ（A2A オーケストレータ）。

プラットフォームが A2A クライアントとして振る舞い、選択された各 Agent に
``message/send`` を送る。その際、選択された MCP サーバ一覧をメッセージの
metadata に載せて渡し、Agent 側がそれらの MCP に接続してツールを実行する。
複数 Agent は順番に実行され、各 Agent の出力が次の Agent の入力に渡る
（オーケストレータ方式の Agent 間連携）。
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user
from backend.models.schemas import (
    ExecuteRequest,
    ExecuteResponse,
    ExecutionStep,
    User,
)
from backend.store.memory import store

router = APIRouter(prefix="/execute", tags=["execution"])

A2A_TIMEOUT = 15.0


def _send_to_agent(a2a_url: str, text: str, mcp_servers: list[dict]) -> dict:
    """A2A の message/send を 1 つの Agent に送り、result を返す。"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "platform-request",
                "parts": [{"kind": "text", "text": text}],
                "metadata": {"mcpServers": mcp_servers},
            }
        },
    }
    resp = httpx.post(a2a_url.rstrip("/") + "/", json=payload, timeout=A2A_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "A2A error"))
    return data.get("result", {})


def _result_text(result: dict) -> str:
    return " ".join(
        p.get("text", "")
        for p in result.get("parts", [])
        if p.get("kind") == "text"
    ).strip()


def run_composition(
    user: User,
    agent_ids: list[str],
    mcp_server_ids: list[str],
    input_text: str,
) -> ExecuteResponse:
    """選択された Agent / MCP サーバを A2A オーケストレータで実行する共通処理。

    `/execute`（アドホック実行）と カスタム Agent の実行 の両方から使う。
    """
    enab = store.get_enablements(user)

    # 実行対象は「有効化済み」でなければならない（サーバ側で必ず検証）
    if not set(agent_ids) <= set(enab.enabled_agent_ids):
        raise HTTPException(status_code=403, detail="有効化されていない Agent が含まれます")
    if not set(mcp_server_ids) <= set(enab.enabled_mcp_server_ids):
        raise HTTPException(status_code=403, detail="有効化されていない MCP サーバが含まれます")
    if not agent_ids:
        raise HTTPException(status_code=400, detail="Agent を 1 つ以上選択してください")

    agents = {a.id: a for a in store.list_agents()}
    servers = {m.id: m for m in store.list_mcp_servers()}

    # Agent に渡す「選択された MCP サーバ」一覧（接続情報）
    mcp_servers = [
        {"name": servers[sid].name, "url": servers[sid].url} for sid in mcp_server_ids
    ]

    steps: list[ExecutionStep] = [
        ExecutionStep(source="platform", detail=f"入力: {input_text!r}"),
    ]
    for s in mcp_servers:
        steps.append(ExecutionStep(source="platform", detail=f"MCP を提供: {s['name']}"))

    # 複数 Agent をオーケストレータ方式で順に実行。
    # 2 番目以降は「元タスク + 前段エージェントの結果」を入力に渡す。
    prev_output: str | None = None
    final_output = ""
    failed = False
    for aid in agent_ids:
        agent = agents[aid]
        if prev_output is None:
            agent_input = input_text
        else:
            agent_input = (
                f"{input_text}\n\n[前のエージェントの結果]\n{prev_output}"
            )
        steps.append(ExecutionStep(source="a2a", detail=f"{agent.name} にタスク送信"))
        try:
            result = _send_to_agent(agent.a2a_url, agent_input, mcp_servers)
        except Exception as exc:  # noqa: BLE001 - 到達不能などはステップに記録
            failed = True
            steps.append(ExecutionStep(source="a2a", detail=f"{agent.name} 失敗: {exc}"))
            continue

        # Agent が実行した MCP ツール呼び出しをトレースとして展開
        for tc in (result.get("metadata") or {}).get("toolCalls", []):
            if tc.get("tool"):
                steps.append(
                    ExecutionStep(
                        source="mcp",
                        detail=f"{tc['server']} / {tc['tool']} -> {tc['result']}",
                    )
                )

        text = _result_text(result)
        steps.append(ExecutionStep(source="a2a", detail=f"{agent.name} 応答: {text}"))
        final_output = text
        prev_output = text  # 次の Agent へ引き継ぐ

    return ExecuteResponse(
        status="error" if failed else "completed",
        steps=steps,
        output=final_output or "(出力なし)",
    )


@router.post("", response_model=ExecuteResponse)
def execute(req: ExecuteRequest, user: User = Depends(get_current_user)) -> ExecuteResponse:
    return run_composition(user, req.agent_ids, req.mcp_server_ids, req.input)
