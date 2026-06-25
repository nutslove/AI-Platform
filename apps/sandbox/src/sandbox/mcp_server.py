"""MCP サーバの最小実装（JSON-RPC over HTTP）。

公式 MCP SDK は使わず、プロトタイプ向けに ``initialize`` / ``tools/list`` /
``tools/call`` だけを実装する。MCP は JSON-RPC 2.0 なので、単一の POST /
エンドポイントでメソッドを振り分ける。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request

from sandbox.tools import Tool

PROTOCOL_VERSION = "2025-06-18"


def _result(req_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def create_mcp_app(name: str, tools: dict[str, Tool]) -> FastAPI:
    app = FastAPI(title=f"{name} (MCP)")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": name}

    @app.post("/")
    async def rpc(request: Request) -> dict:
        body = await request.json()
        req_id = body.get("id")
        method = body.get("method")
        params = body.get("params") or {}

        if method == "initialize":
            return _result(
                req_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": name, "version": "0.1.0"},
                },
            )

        if method == "tools/list":
            return _result(
                req_id,
                {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.input_schema,
                        }
                        for t in tools.values()
                    ]
                },
            )

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            tool = tools.get(tool_name)
            if tool is None:
                return _error(req_id, -32602, f"未知のツール: {tool_name}")
            try:
                text = tool.handler(arguments)
            except Exception as exc:  # noqa: BLE001 - プロトタイプ用に握りつぶす
                return _result(
                    req_id,
                    {"content": [{"type": "text", "text": str(exc)}], "isError": True},
                )
            return _result(
                req_id,
                {"content": [{"type": "text", "text": text}], "isError": False},
            )

        return _error(req_id, -32601, f"未対応のメソッド: {method}")

    return app
