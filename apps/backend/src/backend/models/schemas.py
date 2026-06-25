"""API の入出力スキーマ（Pydantic）。Frontend の src/types.ts と対応する。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["admin", "user"]
McpTransport = Literal["http", "stdio"]


class User(BaseModel):
    id: str
    username: str
    role: Role
    # 属性ベースのアクセス制御（ABAC）に使う属性。例: {"department": "営業部"}
    attributes: dict[str, str] = Field(default_factory=dict)


# アクセスポリシー: 属性キー -> 許可する値リスト（AND 結合、値内は OR）。
# 例: {"department": ["営業部", "分析部"]} = 営業部 か 分析部 のユーザが利用可。
# 空 {} は「全員可（公開）」。
AccessPolicy = dict[str, list[str]]


# --- Agent ---


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    a2a_url: str = Field("", description="A2A の Agent Card / エンドポイント URL")
    skills: list[str] = Field(default_factory=list)
    access: AccessPolicy = Field(default_factory=dict)


class Agent(AgentCreate):
    id: str


class AgentView(Agent):
    """一覧表示用。現在のユーザが利用を許可されているか（allowed）を付与する。"""

    allowed: bool = True


# --- MCP サーバ ---


class McpServerCreate(BaseModel):
    name: str
    description: str = ""
    transport: McpTransport = "http"
    url: str = ""
    access: AccessPolicy = Field(default_factory=dict)


class McpServer(McpServerCreate):
    id: str


class McpServerView(McpServer):
    allowed: bool = True


# --- ABAC 管理（ADMIN 用）---


class UserAttributes(BaseModel):
    """ユーザに属性（部署など）を割り当てる。"""

    attributes: dict[str, str] = Field(default_factory=dict)


class ResourceAccess(BaseModel):
    """Agent / MCP サーバのアクセスポリシーを設定する。"""

    access: AccessPolicy = Field(default_factory=dict)


# --- Enablement（ユーザが有効化した集合。allowed の部分集合）---


class Enablements(BaseModel):
    enabled_agent_ids: list[str] = Field(default_factory=list)
    enabled_mcp_server_ids: list[str] = Field(default_factory=list)


# --- カスタム Agent（Agent + MCP サーバの組み合わせ）---


class CustomAgentCreate(BaseModel):
    name: str
    description: str = ""
    agent_ids: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)


class CustomAgent(CustomAgentCreate):
    id: str
    owner_id: str


# --- 実行 ---


class ExecuteRequest(BaseModel):
    agent_ids: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    input: str = ""


class ExecutionStep(BaseModel):
    source: str
    detail: str


class ExecuteResponse(BaseModel):
    status: str
    steps: list[ExecutionStep]
    output: str
