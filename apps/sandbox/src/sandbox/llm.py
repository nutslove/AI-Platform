"""GCP Vertex AI（Gemini）でエージェントを動かすためのモジュール。

認証は Application Default Credentials（ADC）。
``GOOGLE_APPLICATION_CREDENTIALS`` に
``~/.config/gcloud/application_default_credentials.json`` を指す（compose で
コンテナにマウントする）。プロジェクトは ``GOOGLE_CLOUD_PROJECT`` か、無ければ
ADC ファイル中の ``quota_project_id`` から解決する。

Gemini の function calling を使い、選択された MCP サーバのツールを呼び出す。
"""

from __future__ import annotations

import json
import os

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree, trace

from sandbox.mcp_client import McpClient

# 既定モデル / リージョン
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_REGION = "global"
MAX_TURNS = 6

# 全エージェント共通の行動指針（自律的にツールを使い、聞き返しすぎない）
BASE_SYSTEM = (
    "あなたは業務アシスタントです。利用可能な MCP ツールは自分で積極的に呼び出して回答してください。"
    "引数が不要な一覧/集計系ツール（list_*, *_summary, *_performance, *_funnel, market_trends など）は、"
    "ユーザに確認せずまず実行してデータを取得します。"
    "必要な情報がツールで得られる場合は聞き返さず、得られたデータに基づいて結論を出してください。"
    "最終回答は結論（示唆・推奨アクション）を先に、根拠となる数値を後に、簡潔にまとめます。"
)


def gcp_config() -> tuple[str | None, str]:
    """(project_id, location) を返す。project が解決できなければ (None, location)。"""
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


def _to_gemini_schema(schema: dict) -> dict:
    """JSON Schema を Gemini の Schema 形式へ変換（type を大文字化）。"""
    if not isinstance(schema, dict):
        return schema
    out: dict = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str):
            out["type"] = value.upper()
        elif key == "properties" and isinstance(value, dict):
            out["properties"] = {k: _to_gemini_schema(v) for k, v in value.items()}
        elif key == "items":
            out["items"] = _to_gemini_schema(value)
        else:
            out[key] = value
    return out


def _collect_tools(mcp_servers: list[dict]):
    """選択された MCP サーバから Gemini の FunctionDeclaration を組み立てる。

    戻り値: (function_declarations, name->(McpClient, server_name), 接続エラーのトレース)
    """
    from google.genai import types

    decls = []
    routing: dict[str, tuple[McpClient, str]] = {}
    errors: list[dict] = []
    for server in mcp_servers:
        client = McpClient(server.get("url", ""))
        try:
            available = client.list_tools()
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {"server": server.get("name"), "tool": None, "result": f"接続失敗: {exc}"}
            )
            continue
        for t in available:
            name = t["name"]
            decls.append(
                types.FunctionDeclaration(
                    name=name,
                    description=t.get("description", ""),
                    parameters=_to_gemini_schema(
                        t.get("inputSchema") or {"type": "object", "properties": {}}
                    ),
                )
            )
            routing[name] = (client, server.get("name", ""))
    return decls, routing, errors


def _serialize_contents(contents) -> list[dict]:
    """LangSmith のトレース表示用に会話履歴を JSON 化する。"""
    out = []
    for content in contents:
        parts = []
        for p in getattr(content, "parts", None) or []:
            if getattr(p, "text", None):
                parts.append({"text": p.text})
            elif getattr(p, "function_call", None):
                fc = p.function_call
                parts.append(
                    {"function_call": fc.name, "args": dict(fc.args) if fc.args else {}}
                )
            elif getattr(p, "function_response", None):
                parts.append({"function_response": p.function_response.name})
        out.append({"role": getattr(content, "role", "?"), "parts": parts})
    return out


@traceable(run_type="chain", name="agent")
def run_llm(
    system: str, text: str, mcp_servers: list[dict], agent_name: str = ""
) -> tuple[str, list[dict]]:
    """Vertex 上の Gemini で function calling ループを回す。

    LangSmith のキー（LANGSMITH_API_KEY 等）が環境にあればトレースを送信する。
    無ければ @traceable / trace は何もしない（ネットワークアクセス無し）。

    戻り値: (最終応答テキスト, ツール呼び出しトレース)
    """
    from google import genai
    from google.genai import types

    # トレースの root 名にエージェント名を反映（トレース無効時は None）
    run_tree = get_current_run_tree()
    if run_tree is not None and agent_name:
        run_tree.name = f"agent.{agent_name}"

    project, location = gcp_config()
    client = genai.Client(vertexai=True, project=project, location=location)
    model = os.getenv("GEMINI_MODEL") or os.getenv("VERTEX_MODEL") or DEFAULT_MODEL

    decls, routing, tool_calls = _collect_tools(mcp_servers)
    tools = [types.Tool(function_declarations=decls)] if decls else None
    system_full = BASE_SYSTEM + ("\n\n" + system if system else "")
    config = types.GenerateContentConfig(
        system_instruction=system_full,
        tools=tools,
        temperature=0,
    )

    contents = [types.Content(role="user", parts=[types.Part(text=text)])]
    final_text = ""

    for _ in range(MAX_TURNS):
        # Gemini 呼び出しを LLM スパンとして記録
        with trace(
            name=f"gemini.generate_content[{model}]",
            run_type="llm",
            inputs={"system": system_full, "messages": _serialize_contents(contents)},
        ) as llm_run:
            resp = client.models.generate_content(
                model=model, contents=contents, config=config
            )
            candidate = resp.candidates[0]
            parts = candidate.content.parts or []
            texts = [p.text for p in parts if getattr(p, "text", None)]
            if texts:
                final_text = "".join(texts)
            function_calls = [
                p.function_call for p in parts if getattr(p, "function_call", None)
            ]
            llm_run.end(
                outputs={
                    "text": "".join(texts),
                    "tool_calls": [fc.name for fc in function_calls],
                    "usage": getattr(resp, "usage_metadata", None)
                    and {
                        "input": resp.usage_metadata.prompt_token_count,
                        "output": resp.usage_metadata.candidates_token_count,
                    },
                }
            )

        if not function_calls:
            break

        # モデルの応答（function_call 含む）を履歴へ
        contents.append(candidate.content)

        response_parts = []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            client_for, server_name = routing.get(fc.name, (None, ""))
            # MCP ツール呼び出しを tool スパンとして記録
            with trace(
                name=f"mcp.{fc.name}",
                run_type="tool",
                inputs={"server": server_name, "args": args},
            ) as tool_run:
                if client_for is None:
                    out = f"unknown tool: {fc.name}"
                else:
                    try:
                        out = client_for.call_tool(fc.name, args)
                    except Exception as exc:  # noqa: BLE001
                        out = f"呼び出し失敗: {exc}"
                tool_run.end(outputs={"result": out})
            tool_calls.append(
                {"server": server_name, "tool": fc.name, "args": args, "result": out}
            )
            response_parts.append(
                types.Part.from_function_response(name=fc.name, response={"result": out})
            )
        contents.append(types.Content(role="user", parts=response_parts))

    return final_text or "(Gemini 応答なし)", tool_calls
