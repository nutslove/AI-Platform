"""エージェントの実行エンジン（LangChain / LangGraph + Vertex Gemini）。

- LLM: ``ChatVertexAI``（GCP Vertex 上の Gemini、ADC 認証）
- ツール: ``langchain-mcp-adapters`` で MCP サーバ（FastMCP）から取得
- エージェントループ: ``langgraph`` の ReAct エージェント

LangSmith のキーが環境にあれば LangChain が自動でトレースを送る。
"""

from __future__ import annotations

import json
import os

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_REGION = "global"

# 全エージェント共通の行動指針
BASE_SYSTEM = (
    "あなたは業務アシスタントです。利用可能なツールは自分で積極的に呼び出して回答します。"
    "引数が不要な一覧/集計系ツールは、ユーザに確認せずまず実行してデータを取得してください。"
    "一覧を取得するときはまず絞り込み無し（引数なし）で全件を取得します。"
    "固有名詞・数値・ID は必ずツールの結果から取得し、推測やでっち上げは絶対にしないでください。"
    "ツール結果に無い情報は『データなし』と述べます。"
    "必要な情報がツールで得られる場合は聞き返さず、データに基づいて結論を出します。"
    "最終回答は結論（示唆・推奨アクション）を先に、根拠となる数値を後に、簡潔にまとめてください。"
)


def gcp_config() -> tuple[str | None, str]:
    """(project_id, location) を返す。"""
    region = os.getenv("CLOUD_ML_REGION") or os.getenv("VERTEX_REGION") or DEFAULT_REGION
    project = (
        os.getenv("GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("VERTEX_PROJECT_ID")
    )
    if not project:
        adc = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if adc and os.path.exists(adc):
            try:
                with open(adc, encoding="utf-8") as f:
                    project = json.load(f).get("quota_project_id")
            except (OSError, ValueError):
                project = None
    return project, region


def vertex_available() -> bool:
    project, _ = gcp_config()
    return bool(project)


def _mcp_connections(mcp_servers: list[dict]) -> dict:
    """選択された MCP サーバ -> langchain-mcp-adapters の接続設定。"""
    conns = {}
    for srv in mcp_servers:
        url = srv.get("url", "").rstrip("/") + "/mcp/"
        conns[srv.get("name", url)] = {"url": url, "transport": "streamable_http"}
    return conns


async def _load_tools(mcp_servers: list[dict]):
    """各 MCP サーバからツールを取得し、ツール名->サーバ名 のマップも返す。"""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    tools = []
    server_of: dict[str, str] = {}
    errors: list[dict] = []
    for srv in mcp_servers:
        name = srv.get("name", "")
        conn = _mcp_connections([srv])
        try:
            client = MultiServerMCPClient(conn)
            stools = await client.get_tools()
        except Exception as exc:  # noqa: BLE001
            errors.append({"server": name, "tool": None, "result": f"接続失敗: {exc}"})
            continue
        for t in stools:
            server_of[t.name] = name
        tools.extend(stools)
    return tools, server_of, errors


def _trace_from_messages(messages, server_of: dict[str, str]) -> tuple[str, list[dict]]:
    """LangGraph の messages から (最終テキスト, ツール呼び出しトレース) を作る。"""
    from langchain_core.messages import AIMessage, ToolMessage

    calls_by_id: dict[str, dict] = {}
    tool_calls: list[dict] = []
    for m in messages:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls or []:
                calls_by_id[tc.get("id")] = tc
        elif isinstance(m, ToolMessage):
            tc = calls_by_id.get(m.tool_call_id, {})
            name = tc.get("name") or getattr(m, "name", "")
            tool_calls.append(
                {
                    "server": server_of.get(name, ""),
                    "tool": name,
                    "args": tc.get("args", {}),
                    "result": str(m.content)[:600],
                }
            )

    final_text = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            content = m.content
            if isinstance(content, list):  # 一部モデルは content をブロック配列で返す
                content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
            if isinstance(content, str) and content.strip():
                final_text = content
                break
    return final_text, tool_calls


async def run_agent(
    system: str, text: str, mcp_servers: list[dict], agent_name: str = ""
) -> tuple[str, list[dict]]:
    """LangGraph の ReAct エージェントで実行する。"""
    from langchain_google_vertexai import ChatVertexAI
    from langgraph.prebuilt import create_react_agent

    project, location = gcp_config()
    model = os.getenv("GEMINI_MODEL") or os.getenv("VERTEX_MODEL") or DEFAULT_MODEL

    tools, server_of, errors = await _load_tools(mcp_servers)

    # thinking_budget=0: Gemini 2.5 の thinking を無効化。
    # 有効だと tool 併用時にまれに空応答（思考だけでターン終了）になるため。
    llm = ChatVertexAI(
        model=model,
        project=project,
        location=location,
        temperature=0,
        max_retries=2,
        thinking_budget=0,
    )
    prompt = BASE_SYSTEM + ("\n\n" + system if system else "")
    agent = create_react_agent(llm, tools, prompt=prompt)

    # Vertex/Gemini はまれに空応答を返すため、最大 3 回まで再試行する。
    final_text, tool_calls = "", []
    for _ in range(3):
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": text}]},
            config={"recursion_limit": 25, "run_name": f"agent.{agent_name}"},
        )
        final_text, tool_calls = _trace_from_messages(result["messages"], server_of)
        if final_text or tool_calls:
            break

    if not final_text and tool_calls:
        # ツールは動いたが要約が空 → ツール結果を要約代わりに返す
        lines = [f"- {c['server']} / {c['tool']}: {c['result']}" for c in tool_calls if c.get("tool")]
        final_text = "ツール実行結果:\n" + "\n".join(lines)

    return final_text or "(応答なし)", errors + tool_calls


async def run_fallback(
    agent_known_tools: set[str], text: str, mcp_servers: list[dict]
) -> tuple[str, list[dict]]:
    """Vertex 未設定時のフォールバック。引数不要のツールだけ実行する。"""
    tools, server_of, errors = await _load_tools(mcp_servers)
    tool_calls: list[dict] = list(errors)
    for t in tools:
        if agent_known_tools and t.name not in agent_known_tools:
            continue
        schema = t.args_schema
        required = []
        if schema is not None:
            try:
                required = schema.model_json_schema().get("required", [])
            except Exception:  # noqa: BLE001
                required = list(getattr(t, "args", {}) or {})
        if required:
            continue  # 引数必須ツールはフォールバックでは呼ばない
        try:
            out = await t.ainvoke({})
        except Exception as exc:  # noqa: BLE001
            out = f"呼び出し失敗: {exc}"
        tool_calls.append(
            {"server": server_of.get(t.name, ""), "tool": t.name, "args": {}, "result": str(out)[:600]}
        )

    if any(tc.get("tool") for tc in tool_calls):
        lines = [f"- {tc['server']} / {tc['tool']}: {tc['result']}" for tc in tool_calls if tc.get("tool")]
        summary = "（ルールベース）ツールを実行しました:\n" + "\n".join(lines)
    else:
        summary = "利用できるツールがありませんでした（MCP 未選択、または扱えるツールなし）。"
    return summary, tool_calls
