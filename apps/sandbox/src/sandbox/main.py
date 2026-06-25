"""エントリポイント。環境変数で MCP サーバ / エージェントを切り替える。

- ``SERVICE_KIND``: "mcp" または "agent"
- ``SERVICE_NAME``: 下のレジストリのキー
- ``PUBLIC_URL``: エージェントの Agent Card に載せる URL（任意）

uvicorn は ``sandbox.main:app`` を起動するだけでよい。
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from sandbox.agent import AgentDef, create_agent_app
from sandbox.mcp_server import create_mcp_app
from sandbox.tools import (
    ANALYTICS_TOOLS,
    CALENDAR_TOOLS,
    CRM_TOOLS,
    EMAIL_TOOLS,
    KB_TOOLS,
    MARKET_TOOLS,
)

# --- MCP サーバのレジストリ（業務ツール）---
MCP_REGISTRY = {
    "crm": ("CRM MCP", CRM_TOOLS),
    "analytics": ("Analytics MCP", ANALYTICS_TOOLS),
    "email": ("Email MCP", EMAIL_TOOLS),
    "kb": ("Knowledge Base MCP", KB_TOOLS),
    "calendar": ("Calendar MCP", CALENDAR_TOOLS),
    "market": ("Market Research MCP", MARKET_TOOLS),
}

# --- エージェントのレジストリ（業務ロール）---
AGENT_REGISTRY = {
    "sales": AgentDef(
        key="sales",
        name="Sales Agent",
        description="営業担当。CRM・メール・カレンダー・KB を使い、商談管理や顧客フォローを支援する。",
        known_tools={"list_customers", "pipeline_summary", "list_deals", "list_templates", "list_events", "find_free_slot"},
        system=(
            "あなたは経験豊富な営業担当アシスタントです。提供された MCP ツール"
            "（CRM・メール・カレンダー・ナレッジベース）を使い、商談状況の把握、"
            "顧客フォロー、メール下書き、日程調整などを行います。"
            "数値は CRM/分析の実データに基づき、次のアクションを簡潔に提案してください。"
        ),
        skills=[
            {"id": "pipeline", "name": "pipeline-management", "description": "商談パイプライン管理", "tags": ["sales", "crm"]},
            {"id": "outreach", "name": "outreach", "description": "顧客フォロー・メール", "tags": ["email"]},
        ],
    ),
    "marketing": AgentDef(
        key="marketing",
        name="Marketing Agent",
        description="マーケティング担当。分析・市場調査・メールを使い、施策評価とメッセージ作成を支援する。",
        known_tools={"traffic_summary", "campaign_performance", "conversion_funnel", "competitor_overview", "market_trends", "list_templates"},
        system=(
            "あなたはマーケティングのスペシャリストです。提供された MCP ツール"
            "（分析・市場調査・メール・ナレッジベース）を使い、キャンペーン成果の評価、"
            "市場/競合トレンドの把握、訴求メッセージや配信文面の作成を行います。"
            "CTR/CVR/CPA などの指標に基づき、改善案を具体的に示してください。"
        ),
        skills=[
            {"id": "analytics", "name": "campaign-analytics", "description": "施策分析", "tags": ["marketing"]},
            {"id": "research", "name": "market-research", "description": "市場/競合調査", "tags": ["market"]},
        ],
    ),
    "support": AgentDef(
        key="support",
        name="Support Agent",
        description="カスタマーサポート担当。KB・CRM・メールを使い、問い合わせ対応と返信作成を支援する。",
        known_tools={"list_docs", "list_customers", "list_templates"},
        system=(
            "あなたは丁寧なカスタマーサポート担当です。提供された MCP ツール"
            "（ナレッジベース・CRM・メール）を使い、顧客の問い合わせに事実に基づいて回答し、"
            "必要なら顧客情報を確認して返信文面を作成します。"
            "不確かな点は推測せず、ナレッジベースを検索して根拠を示してください。"
        ),
        skills=[
            {"id": "qa", "name": "knowledge-qa", "description": "ナレッジ参照Q&A", "tags": ["support", "kb"]},
        ],
    ),
    "analyst": AgentDef(
        key="analyst",
        name="Revenue Analyst Agent",
        description="レベニュー/データアナリスト。分析・CRM・市場データを横断して示唆を出す。",
        known_tools={"traffic_summary", "campaign_performance", "conversion_funnel", "pipeline_summary", "list_customers", "market_trends"},
        system=(
            "あなたはレベニュー/データアナリストです。提供された MCP ツール"
            "（分析・CRM・市場調査）を横断して、売上パイプラインとマーケ指標を関連づけ、"
            "ボトルネックと改善インパクトを定量的に説明します。"
            "結論（示唆）を先に述べ、根拠となる数値を続けてください。"
        ),
        skills=[
            {"id": "insight", "name": "revenue-insight", "description": "売上分析・示唆出し", "tags": ["analytics"]},
        ],
    ),
}


def build_app() -> FastAPI:
    kind = os.getenv("SERVICE_KIND", "mcp")
    name = os.getenv("SERVICE_NAME", "crm")

    if kind == "mcp":
        if name not in MCP_REGISTRY:
            raise SystemExit(f"未知の MCP サーバ: {name}")
        title, tools = MCP_REGISTRY[name]
        return create_mcp_app(title, tools)

    if kind == "agent":
        if name not in AGENT_REGISTRY:
            raise SystemExit(f"未知のエージェント: {name}")
        public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
        return create_agent_app(AGENT_REGISTRY[name], public_url)

    raise SystemExit(f"未知の SERVICE_KIND: {kind}")


app = build_app()
