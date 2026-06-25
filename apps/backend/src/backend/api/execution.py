"""Agent / MCP サーバを組み合わせて実行するルータ（A2A オーケストレータ）。

プラットフォームが A2A クライアントとして振る舞い、選択された各 Agent に
``message/send`` を送る。その際、選択された MCP サーバ一覧をメッセージの
metadata に載せて渡し、Agent 側がそれらの MCP に接続してツールを実行する。
複数 Agent は順番に実行され、各 Agent の出力が次の Agent の入力に渡る
（オーケストレータ方式の Agent 間連携）。
"""

from __future__ import annotations

import json
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.api.deps import get_current_user
from backend.models.schemas import (
    ExecuteRequest,
    ExecuteResponse,
    ExecutionStep,
    User,
)
from backend.store.memory import store

router = APIRouter(prefix="/execute", tags=["execution"])

# LangChain エージェントは複数回の LLM 呼び出し + MCP 接続で時間がかかるため長め。
A2A_TIMEOUT = float(os.getenv("A2A_TIMEOUT", "180"))

# SSE レスポンス共通ヘッダ（nginx のバッファリング無効化など）
SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


def validate_enablements(
    user: User, agent_ids: list[str], mcp_server_ids: list[str]
) -> list[dict]:
    """実行対象が有効化済みかを検証し、Agent に渡す MCP 接続情報を返す。"""
    enab = store.get_enablements(user)
    if not set(agent_ids) <= set(enab.enabled_agent_ids):
        raise HTTPException(status_code=403, detail="有効化されていない Agent が含まれます")
    if not set(mcp_server_ids) <= set(enab.enabled_mcp_server_ids):
        raise HTTPException(status_code=403, detail="有効化されていない MCP サーバが含まれます")
    if not agent_ids:
        raise HTTPException(status_code=400, detail="Agent を 1 つ以上選択してください")
    servers = {m.id: m for m in store.list_mcp_servers()}
    return [{"name": servers[s].name, "url": servers[s].url} for s in mcp_server_ids]


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _a2a_payload(text: str, mcp_servers: list[dict]) -> dict:
    return {
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


async def stream_composition(
    user: User, agent_ids: list[str], mcp_server_ids: list[str], input_text: str
):
    """SSE で実行を逐次配信する。各 Agent の /stream を中継しトークンを流す。"""
    mcp_servers = validate_enablements(user, agent_ids, mcp_server_ids)
    agents = {a.id: a for a in store.list_agents()}

    yield _sse({"type": "step", "source": "platform", "detail": f"入力: {input_text!r}"})
    for s in mcp_servers:
        yield _sse({"type": "step", "source": "platform", "detail": f"MCP を提供: {s['name']}"})

    prev_output: str | None = None
    final_output = ""
    failed = False
    for aid in agent_ids:
        agent = agents[aid]
        agent_input = (
            input_text if prev_output is None
            else f"{input_text}\n\n[前のエージェントの結果]\n{prev_output}"
        )
        yield _sse({"type": "step", "source": "a2a", "detail": f"{agent.name} にタスク送信"})
        yield _sse({"type": "agent_start", "agent": agent.name})

        agent_text = ""
        try:
            async with httpx.AsyncClient(timeout=A2A_TIMEOUT) as client:
                url = agent.a2a_url.rstrip("/") + "/stream"
                async with client.stream("POST", url, json=_a2a_payload(agent_input, mcp_servers)) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        ev = json.loads(line[5:].strip())
                        t = ev.get("type")
                        if t == "token":
                            agent_text += ev.get("text", "")
                            yield _sse({"type": "token", "agent": agent.name, "text": ev.get("text", "")})
                        elif t == "tool" and ev.get("tool"):
                            yield _sse({
                                "type": "step", "source": "mcp",
                                "detail": f"{ev.get('server', '')} / {ev['tool']} -> {ev.get('result', '')}",
                            })
                        elif t == "final":
                            agent_text = ev.get("text") or agent_text
        except Exception as exc:  # noqa: BLE001 - 到達不能/タイムアウト等
            failed = True
            yield _sse({"type": "step", "source": "a2a",
                        "detail": f"{agent.name} 失敗: {str(exc).splitlines()[0][:120]}"})
            continue

        yield _sse({"type": "step", "source": "a2a", "detail": f"{agent.name} 応答"})
        yield _sse({"type": "agent_done", "agent": agent.name})
        final_output = agent_text
        prev_output = agent_text

    yield _sse({"type": "done", "status": "error" if failed else "completed",
                "output": final_output or "(出力なし)"})


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
    mcp_servers = validate_enablements(user, agent_ids, mcp_server_ids)
    agents = {a.id: a for a in store.list_agents()}

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


@router.post("/stream")
def execute_stream(
    req: ExecuteRequest, user: User = Depends(get_current_user)
) -> StreamingResponse:
    # 検証は事前に行い、エラーは通常の HTTP で返す（ストリーム前）
    validate_enablements(user, req.agent_ids, req.mcp_server_ids)
    return StreamingResponse(
        stream_composition(user, req.agent_ids, req.mcp_server_ids, req.input),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
