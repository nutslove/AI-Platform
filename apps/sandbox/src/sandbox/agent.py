"""A2A エージェントの最小実装。

各エージェントは:
- ``GET /.well-known/agent-card.json`` で Agent Card を公開（A2A の発見）
- ``POST /`` で JSON-RPC ``message/send`` を受け、タスクを実行（A2A の実行）

エージェントは Vertex(Gemini) の function calling で、**選択された MCP サーバ**
（メッセージの metadata で渡される）のツールを呼ぶ。Vertex 未設定/失敗時は
引数不要の一覧/集計系ツールを叩くルールベースにフォールバックする。これが
「Agent ↔ MCP 連携」と「複数 Agent を組み合わせた実行（A2A）」のデモになる。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import FastAPI, Request

from sandbox.llm import run_llm, vertex_available
from sandbox.mcp_client import McpClient


@dataclass(frozen=True)
class AgentDef:
    key: str
    name: str
    description: str
    # ルールベース・フォールバック時に自動で叩く「引数不要の一覧/集計系」ツール名
    known_tools: set[str]
    # Vertex(Gemini)実行時のシステムプロンプト（エージェントの役割）
    system: str = ""
    skills: list[dict] = field(default_factory=list)


def _rule_based(
    agent: AgentDef, text: str, mcp_servers: list[dict]
) -> tuple[str, list[dict]]:
    """LLM を使わない決定的フォールバック（Vertex 未設定/失敗時）。

    業務ツールは引数が必要なものが多いため、フォールバックでは
    **引数不要（required が無い）の一覧/集計系ツール**だけを呼ぶ。
    """
    tool_calls: list[dict] = []
    for server in mcp_servers:
        client = McpClient(server.get("url", ""))
        try:
            tools = client.list_tools()
        except Exception as exc:  # noqa: BLE001
            tool_calls.append(
                {"server": server.get("name"), "tool": None, "result": f"接続失敗: {exc}"}
            )
            continue
        for t in tools:
            name = t["name"]
            if agent.known_tools and name not in agent.known_tools:
                continue
            if (t.get("inputSchema") or {}).get("required"):
                continue  # 引数必須ツールはフォールバックでは呼ばない
            try:
                result = client.call_tool(name, {})
            except Exception as exc:  # noqa: BLE001
                result = f"呼び出し失敗: {exc}"
            tool_calls.append(
                {"server": server.get("name"), "tool": name, "args": {}, "result": result}
            )

    if tool_calls and any(tc.get("tool") for tc in tool_calls):
        lines = [
            f"- {tc['server']} / {tc['tool']}: {tc['result']}"
            for tc in tool_calls
            if tc.get("tool")
        ]
        summary = f"{agent.name}（ルールベース）がツールを実行しました:\n" + "\n".join(lines)
    else:
        summary = (
            f"{agent.name}: 利用できるツールがありませんでした"
            "（MCP 未選択、または扱えるツールなし）。"
        )
    return summary, tool_calls


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

    # A2A の発見用。/.well-known/agent.json も別名で受ける。
    @app.get("/.well-known/agent-card.json")
    @app.get("/.well-known/agent.json")
    def get_agent_card() -> dict:
        return agent_card

    @app.post("/")
    async def message_send(request: Request) -> dict:
        body = await request.json()
        req_id = body.get("id")
        params = body.get("params") or {}
        message = params.get("message") or {}

        # 入力テキストを取り出す
        text = " ".join(
            p.get("text", "")
            for p in message.get("parts", [])
            if p.get("kind") == "text"
        ).strip()

        # プラットフォームが渡してきた「選択された MCP サーバ」一覧
        metadata = message.get("metadata") or {}
        mcp_servers = metadata.get("mcpServers") or []

        # GCP Vertex(Gemini) が使えれば LLM 駆動。失敗時はルールベースにフォールバック。
        if vertex_available():
            try:
                summary, tool_calls = run_llm(
                    agent.system, text, mcp_servers, agent_name=agent.name
                )
            except Exception as exc:  # noqa: BLE001 - クォータ超過等はフォールバック
                summary, tool_calls = _rule_based(agent, text, mcp_servers)
                summary = (
                    f"[Vertex 実行に失敗したためルールベースで応答: {exc}]\n" + summary
                )
        else:
            summary, tool_calls = _rule_based(agent, text, mcp_servers)

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
