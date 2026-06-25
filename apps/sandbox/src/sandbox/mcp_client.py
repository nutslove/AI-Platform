"""MCP サーバを呼ぶ最小クライアント（JSON-RPC over HTTP）。

エージェントがこれを使い、選択された MCP サーバの ``tools/list`` /
``tools/call`` を実行する。
"""

from __future__ import annotations

import httpx


class McpClient:
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        # 末尾スラッシュを正規化（POST / に送る）
        self.url = url.rstrip("/") + "/"
        self.timeout = timeout

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        resp = httpx.post(self.url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "MCP error"))
        return data.get("result", {})

    def list_tools(self) -> list[dict]:
        return self._rpc("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        parts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        return "\n".join(parts)
