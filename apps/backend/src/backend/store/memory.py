"""インメモリのデータストア（スキャフォールド用）。

アクセス制御は **属性ベース（ABAC）**。ユーザは属性（部署など）を持ち、
各 Agent / MCP サーバは「どの属性なら使えるか」のアクセスポリシーを持つ。
ユーザがそのリソースを使えるか（allowed）は属性とポリシーから計算する。

NOTE: プロセス内辞書で状態を保持する。本番では PostgreSQL 等の
永続化層に差し替える前提。
"""

from __future__ import annotations

import uuid

from backend.models.schemas import (
    AccessPolicy,
    Agent,
    AgentCreate,
    CustomAgent,
    CustomAgentCreate,
    Enablements,
    McpServer,
    McpServerCreate,
    User,
)

# デモで使う部署（属性 "department" の取りうる値）
DEPARTMENTS = ["営業部", "マーケティング部", "サポート部", "分析部"]


def _id() -> str:
    return uuid.uuid4().hex[:8]


class Store:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """全状態を初期シードへ戻す（テスト用）。"""
        self.users: dict[str, User] = {}
        self.agents: dict[str, Agent] = {}
        self.mcp_servers: dict[str, McpServer] = {}
        # user_id -> Enablements（ユーザ自身の有効化選択。生の保存値）
        self.enablements: dict[str, Enablements] = {}
        # custom_agent_id -> CustomAgent
        self.custom_agents: dict[str, CustomAgent] = {}
        self._seed()

    # --- seed ---

    def _seed(self) -> None:
        # ユーザに部署属性を付与
        users = [
            User(id="admin", username="admin", role="admin", attributes={"department": "管理部"}),
            User(id="alice", username="alice", role="user", attributes={"department": "営業部"}),
            User(id="bob", username="bob", role="user", attributes={"department": "マーケティング部"}),
            User(id="carol", username="carol", role="user", attributes={"department": "サポート部"}),
            User(id="dave", username="dave", role="user", attributes={"department": "分析部"}),
        ]
        for u in users:
            self.users[u.id] = u

        # Agent（access = 利用を許可する部署。空 = 全員可）
        self.add_agent(AgentCreate(
            name="Sales Agent", description="営業担当。商談管理・顧客フォロー・日程調整を支援。",
            a2a_url="http://sales-agent:8000", skills=["pipeline-management", "outreach"],
            access={"department": ["営業部"]},
        ))
        self.add_agent(AgentCreate(
            name="Marketing Agent", description="マーケ担当。施策評価・市場/競合調査・訴求作成を支援。",
            a2a_url="http://marketing-agent:8000", skills=["campaign-analytics", "market-research"],
            access={"department": ["マーケティング部"]},
        ))
        self.add_agent(AgentCreate(
            name="Support Agent", description="カスタマーサポート。ナレッジ参照Q&A・返信作成を支援。",
            a2a_url="http://support-agent:8000", skills=["knowledge-qa"],
            access={"department": ["サポート部"]},
        ))
        self.add_agent(AgentCreate(
            name="Revenue Analyst Agent", description="レベニュー/データ分析。売上とマーケ指標を横断して示唆を出す。",
            a2a_url="http://analyst-agent:8000", skills=["revenue-insight"],
            access={"department": ["分析部", "マーケティング部"]},
        ))

        # MCP サーバ
        self.add_mcp_server(McpServerCreate(
            name="CRM MCP", description="顧客・商談パイプライン", url="http://crm-mcp:8000",
            access={"department": ["営業部", "サポート部", "分析部"]},
        ))
        self.add_mcp_server(McpServerCreate(
            name="Analytics MCP", description="Web/マーケ分析（CTR/CVR/CPA・ファネル）", url="http://analytics-mcp:8000",
            access={"department": ["マーケティング部", "分析部"]},
        ))
        self.add_mcp_server(McpServerCreate(
            name="Email MCP", description="メール下書き/送信（モック）・テンプレ", url="http://email-mcp:8000",
            access={"department": ["営業部", "マーケティング部", "サポート部"]},
        ))
        self.add_mcp_server(McpServerCreate(
            name="Knowledge Base MCP", description="製品/社内ドキュメント検索", url="http://kb-mcp:8000",
            access={},  # 全社公開
        ))
        self.add_mcp_server(McpServerCreate(
            name="Calendar MCP", description="予定・日程調整", url="http://calendar-mcp:8000",
            access={"department": ["営業部"]},
        ))
        self.add_mcp_server(McpServerCreate(
            name="Market Research MCP", description="競合・市場トレンド（モック）", url="http://market-mcp:8000",
            access={"department": ["マーケティング部", "分析部"]},
        ))

    # --- users ---

    def get_user(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def list_users(self) -> list[User]:
        return list(self.users.values())

    def set_user_attributes(self, user_id: str, attributes: dict[str, str]) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        updated = user.model_copy(update={"attributes": attributes})
        self.users[user_id] = updated
        return updated

    def departments(self) -> list[str]:
        return DEPARTMENTS

    # --- agents ---

    def add_agent(self, data: AgentCreate) -> Agent:
        agent = Agent(id=_id(), **data.model_dump())
        self.agents[agent.id] = agent
        return agent

    def delete_agent(self, agent_id: str) -> bool:
        return self.agents.pop(agent_id, None) is not None

    def list_agents(self) -> list[Agent]:
        return list(self.agents.values())

    def set_agent_access(self, agent_id: str, access: AccessPolicy) -> Agent | None:
        agent = self.agents.get(agent_id)
        if agent is None:
            return None
        updated = agent.model_copy(update={"access": access})
        self.agents[agent_id] = updated
        return updated

    # --- mcp servers ---

    def add_mcp_server(self, data: McpServerCreate) -> McpServer:
        server = McpServer(id=_id(), **data.model_dump())
        self.mcp_servers[server.id] = server
        return server

    def delete_mcp_server(self, server_id: str) -> bool:
        return self.mcp_servers.pop(server_id, None) is not None

    def list_mcp_servers(self) -> list[McpServer]:
        return list(self.mcp_servers.values())

    def set_mcp_access(self, server_id: str, access: AccessPolicy) -> McpServer | None:
        server = self.mcp_servers.get(server_id)
        if server is None:
            return None
        updated = server.model_copy(update={"access": access})
        self.mcp_servers[server_id] = updated
        return updated

    # --- ABAC 判定 ---

    def _user_allowed(self, user: User, access: AccessPolicy) -> bool:
        """ユーザ属性がアクセスポリシーを満たすか。"""
        if user.role == "admin":
            return True
        if not access:
            return True  # 公開
        for key, values in access.items():
            if user.attributes.get(key) not in values:
                return False
        return True

    def allowed_agent_ids(self, user: User) -> set[str]:
        return {a.id for a in self.agents.values() if self._user_allowed(user, a.access)}

    def allowed_mcp_server_ids(self, user: User) -> set[str]:
        return {m.id for m in self.mcp_servers.values() if self._user_allowed(user, m.access)}

    # --- enablements ---

    def get_enablements(self, user: User) -> Enablements:
        """有効化集合。現在 allowed なものだけにフィルタして返す。"""
        raw = self.enablements.get(user.id, Enablements())
        allowed_a = self.allowed_agent_ids(user)
        allowed_m = self.allowed_mcp_server_ids(user)
        return Enablements(
            enabled_agent_ids=[i for i in raw.enabled_agent_ids if i in allowed_a],
            enabled_mcp_server_ids=[i for i in raw.enabled_mcp_server_ids if i in allowed_m],
        )

    def set_enablements(self, user: User, enab: Enablements) -> Enablements:
        self.enablements[user.id] = enab
        return self.get_enablements(user)

    # --- custom agents ---

    def add_custom_agent(self, owner_id: str, data: CustomAgentCreate) -> CustomAgent:
        custom = CustomAgent(id=_id(), owner_id=owner_id, **data.model_dump())
        self.custom_agents[custom.id] = custom
        return custom

    def list_custom_agents(self, owner_id: str) -> list[CustomAgent]:
        return [c for c in self.custom_agents.values() if c.owner_id == owner_id]

    def get_custom_agent(self, custom_id: str) -> CustomAgent | None:
        return self.custom_agents.get(custom_id)

    def delete_custom_agent(self, custom_id: str) -> bool:
        return self.custom_agents.pop(custom_id, None) is not None


# プロセス全体で共有する単一インスタンス
store = Store()
