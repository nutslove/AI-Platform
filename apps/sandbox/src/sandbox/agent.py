"""A2A エージェントの最小実装（FastAPI）。

各エージェントは:
- ``GET /.well-known/agent-card.json`` で Agent Card を公開（A2A の発見）
- ``POST /`` で JSON-RPC ``message/send`` を受け、タスクを実行（A2A の実行）

実行は LangChain/LangGraph + Vertex(Gemini)（[llm.py](llm.py)）。渡された MCP
サーバ（FastMCP）のツールを langchain-mcp-adapters 経由で使う。Vertex 未設定時は
引数不要ツールを叩くフォールバック。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from sandbox.llm import run_agent, run_agent_stream, run_fallback, vertex_available


def _extract(message: dict) -> tuple[str, list[dict]]:
    text = " ".join(
        p.get("text", "")
        for p in message.get("parts", [])
        if p.get("kind") == "text"
    ).strip()
    mcp_servers = (message.get("metadata") or {}).get("mcpServers") or []
    return text, mcp_servers


@dataclass(frozen=True)
class AgentDef:
    key: str
    name: str
    description: str
    # フォールバック時に叩く引数不要ツール名（空なら全ての引数不要ツール）
    known_tools: set[str] = field(default_factory=set)
    # LLM 実行時のシステムプロンプト（エージェントの役割）
    system: str = ""
    skills: list[dict] = field(default_factory=list)


def create_agent_app(agent: AgentDef, public_url: str) -> FastAPI:
    app = FastAPI(title=f"{agent.name} (A2A)")

    agent_card = {
        "name": agent.name,
        "description": agent.description,
        "url": public_url,
        "version": "0.1.0",
        "protocolVersion": "0.2.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": agent.skills,
    }

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": agent.name}

    @app.get("/.well-known/agent-card.json")
    @app.get("/.well-known/agent.json")
    def get_agent_card() -> dict:
        return agent_card

    @app.post("/stream")
    async def message_stream(request: Request) -> StreamingResponse:
        body = await request.json()
        message = (body.get("params") or {}).get("message") or {}
        text, mcp_servers = _extract(message)

        async def gen():
            async for ev in run_agent_stream(
                agent.system, text, mcp_servers, agent.name, agent.known_tools
            ):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    @app.post("/")
    async def message_send(request: Request) -> dict:
        body = await request.json()
        req_id = body.get("id")
        params = body.get("params") or {}
        message = params.get("message") or {}
        text, mcp_servers = _extract(message)

        if vertex_available():
            try:
                summary, tool_calls = await run_agent(
                    agent.system, text, mcp_servers, agent_name=agent.name
                )
            except Exception as exc:  # noqa: BLE001 - 失敗時はフォールバック
                summary, tool_calls = await run_fallback(agent.known_tools, text, mcp_servers)
                reason = str(exc).splitlines()[0][:140]
                summary = f"[LLM 実行に失敗したためフォールバック: {reason}]\n\n" + summary
        else:
            summary, tool_calls = await run_fallback(agent.known_tools, text, mcp_servers)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "role": "agent",
                "kind": "message",
                "messageId": f"{agent.key}-response",
                "parts": [{"kind": "text", "text": summary}],
                "metadata": {"toolCalls": tool_calls},
            },
        }

    return app
