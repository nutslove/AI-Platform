"""業務 MCP サーバ群（FastMCP 実装）。

各サーバは ``FastMCP`` インスタンスで、型付き関数を ``@mcp.tool`` で公開する。
``http_app(stateless_http=True)`` で Streamable HTTP の ASGI アプリを返し、
uvicorn で配信する（既定パス /mcp/）。データはプロセス内のモック。
"""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta

from fastmcp import FastMCP


def http_app(name: str):
    """SERVICE_NAME から MCP サーバの ASGI アプリを作る。"""
    builder = _BUILDERS.get(name)
    if builder is None:
        raise SystemExit(f"未知の MCP サーバ: {name}")
    return builder().http_app(stateless_http=True)


# ======================================================================
# CRM — 顧客・商談パイプライン
# ======================================================================

_CUSTOMERS = [
    {"id": "c1", "name": "Acme Corp", "industry": "製造", "contact": "佐藤太郎", "mrr": 120000, "status": "active"},
    {"id": "c2", "name": "Globex", "industry": "小売", "contact": "鈴木花子", "mrr": 80000, "status": "active"},
    {"id": "c3", "name": "Initech", "industry": "IT", "contact": "田中一郎", "mrr": 0, "status": "prospect"},
    {"id": "c4", "name": "Umbrella KK", "industry": "製薬", "contact": "高橋実", "mrr": 250000, "status": "active"},
    {"id": "c5", "name": "Hooli", "industry": "IT", "contact": "渡辺健", "mrr": 0, "status": "prospect"},
]
_DEALS = [
    {"id": "d1", "customer_id": "c1", "name": "Acme 追加ライセンス", "stage": "proposal", "amount": 600000, "owner": "営業A"},
    {"id": "d2", "customer_id": "c3", "name": "Initech 新規導入", "stage": "qualified", "amount": 1200000, "owner": "営業B"},
    {"id": "d3", "customer_id": "c2", "name": "Globex 年次更新", "stage": "won", "amount": 960000, "owner": "営業A"},
    {"id": "d4", "customer_id": "c4", "name": "Umbrella 拡張", "stage": "lead", "amount": 300000, "owner": "営業B"},
    {"id": "d5", "customer_id": "c5", "name": "Hooli PoC", "stage": "qualified", "amount": 800000, "owner": "営業A"},
]


def build_crm() -> FastMCP:
    mcp = FastMCP("CRM MCP")

    @mcp.tool
    def list_customers() -> list[dict]:
        """顧客一覧を返す。"""
        return _CUSTOMERS

    @mcp.tool
    def get_customer(customer_id: str) -> dict | str:
        """顧客IDで顧客詳細を返す。"""
        c = next((c for c in _CUSTOMERS if c["id"] == customer_id), None)
        return c or f"顧客が見つかりません: {customer_id}"

    @mcp.tool
    def list_deals(stage: str = "") -> list[dict]:
        """商談一覧を返す（stage 指定で絞り込み）。"""
        return [d for d in _DEALS if not stage or d["stage"] == stage]

    @mcp.tool
    def pipeline_summary() -> dict:
        """商談をステージ別に集計し、進行中(open)の合計金額も返す。"""
        by_stage: dict = {}
        for d in _DEALS:
            s = by_stage.setdefault(d["stage"], {"count": 0, "amount": 0})
            s["count"] += 1
            s["amount"] += d["amount"]
        open_amount = sum(d["amount"] for d in _DEALS if d["stage"] not in ("won", "lost"))
        return {"by_stage": by_stage, "open_pipeline_amount": open_amount}

    @mcp.tool
    def create_deal(customer_id: str, name: str, amount: float = 0) -> dict:
        """新規商談を作成する。"""
        new = {"id": f"d{len(_DEALS) + 1}", "customer_id": customer_id, "name": name,
               "stage": "lead", "amount": amount, "owner": "未割当"}
        _DEALS.append(new)
        return {"created": new}

    @mcp.tool
    def update_deal_stage(deal_id: str, stage: str) -> dict | str:
        """商談ステージを更新する。"""
        d = next((d for d in _DEALS if d["id"] == deal_id), None)
        if not d:
            return f"商談が見つかりません: {deal_id}"
        d["stage"] = stage
        return {"updated": d}

    return mcp


# ======================================================================
# Analytics — Web/マーケ分析
# ======================================================================

_CAMPAIGNS = [
    {"name": "春のキャンペーン", "impressions": 120000, "clicks": 4200, "conversions": 210, "cost": 350000},
    {"name": "ウェビナー集客", "impressions": 50000, "clicks": 3100, "conversions": 420, "cost": 180000},
    {"name": "リターゲティング", "impressions": 80000, "clicks": 2600, "conversions": 160, "cost": 120000},
]


def build_analytics() -> FastMCP:
    mcp = FastMCP("Analytics MCP")

    @mcp.tool
    def traffic_summary(period: str = "last_30d") -> dict:
        """Webトラフィック概要を返す。"""
        return {"period": period, "sessions": 48200, "users": 31500, "bounce_rate_pct": 42.1,
                "top_sources": [{"source": "organic", "share_pct": 38}, {"source": "paid", "share_pct": 27},
                                {"source": "referral", "share_pct": 18}, {"source": "direct", "share_pct": 17}]}

    @mcp.tool
    def campaign_performance(campaign: str = "") -> list[dict]:
        """広告キャンペーンの成果（CTR/CVR/CPA を計算して付与）。"""
        rows = [c for c in _CAMPAIGNS if not campaign or c["name"] == campaign]
        out = []
        for c in rows:
            out.append({**c,
                        "ctr_pct": round(c["clicks"] / c["impressions"] * 100, 2),
                        "cvr_pct": round(c["conversions"] / c["clicks"] * 100, 2),
                        "cpa": round(c["cost"] / c["conversions"]) if c["conversions"] else None})
        return out

    @mcp.tool
    def conversion_funnel() -> dict:
        """コンバージョンファネルを返す。"""
        return {"funnel": [{"stage": "訪問", "count": 31500}, {"stage": "リード", "count": 4200},
                           {"stage": "商談", "count": 780}, {"stage": "受注", "count": 190}]}

    return mcp


# ======================================================================
# Email — アウトリーチ（モック）
# ======================================================================


def build_email() -> FastMCP:
    mcp = FastMCP("Email MCP")

    @mcp.tool
    def list_templates() -> list[dict]:
        """メールテンプレ一覧を返す。"""
        return [{"id": "t1", "name": "初回アプローチ"}, {"id": "t2", "name": "フォローアップ"},
                {"id": "t3", "name": "提案後リマインド"}]

    @mcp.tool
    def draft_email(to: str, subject: str, body: str) -> dict:
        """メールの下書きを作成する（送信はしない）。"""
        return {"draft": {"to": to, "subject": subject, "body": body}, "note": "下書きを作成しました（未送信）"}

    @mcp.tool
    def send_email(to: str, subject: str, body: str) -> dict:
        """メールを送信する（モック）。"""
        return {"sent": True, "to": to, "subject": subject, "note": "送信しました（モック）"}

    return mcp


# ======================================================================
# Knowledge Base — 製品/社内ドキュメント
# ======================================================================

_DOCS = [
    {"id": "k1", "title": "製品概要", "body": "当社SaaSは営業・マーケ業務を自動化するプラットフォーム。CRM/分析/メール連携を提供。"},
    {"id": "k2", "title": "料金プラン", "body": "Starter 月3万円 / Pro 月10万円 / Enterprise 個別見積。年契約で2ヶ月分割引。"},
    {"id": "k3", "title": "よくある質問", "body": "解約はいつでも可能。SSO対応。データはGCPに保存。SLA 99.9%。"},
    {"id": "k4", "title": "導入事例: Globex", "body": "Globex社はリード対応時間を60%短縮、商談化率を1.4倍に改善。"},
]


def build_kb() -> FastMCP:
    mcp = FastMCP("Knowledge Base MCP")

    @mcp.tool
    def list_docs() -> list[dict]:
        """ドキュメント一覧（id, title）を返す。"""
        return [{"id": d["id"], "title": d["title"]} for d in _DOCS]

    @mcp.tool
    def search_docs(query: str) -> list[dict] | dict:
        """ドキュメントを全文検索する。"""
        q = query.lower()
        hits = [d for d in _DOCS if q in d["title"].lower() or q in d["body"].lower()]
        return hits or {"note": f"該当なし: {query}"}

    @mcp.tool
    def get_doc(doc_id: str) -> dict | str:
        """ドキュメント本文を取得する。"""
        d = next((d for d in _DOCS if d["id"] == doc_id), None)
        return d or f"ドキュメントが見つかりません: {doc_id}"

    return mcp


# ======================================================================
# Calendar — 予定・日程調整
# ======================================================================

_EVENTS = [
    {"id": "e1", "title": "Acme 定例", "date": (_date.today() + timedelta(days=1)).isoformat(), "attendees": ["営業A"]},
    {"id": "e2", "title": "Initech デモ", "date": (_date.today() + timedelta(days=2)).isoformat(), "attendees": ["営業B"]},
]


def build_calendar() -> FastMCP:
    mcp = FastMCP("Calendar MCP")

    @mcp.tool
    def list_events(date: str = "") -> list[dict]:
        """予定一覧を返す（date 指定で絞り込み、YYYY-MM-DD）。"""
        return [e for e in _EVENTS if not date or e["date"] == date]

    @mcp.tool
    def create_event(title: str, date: str, attendees: list[str] | None = None) -> dict:
        """予定を作成する。"""
        new = {"id": f"e{len(_EVENTS) + 1}", "title": title, "date": date, "attendees": attendees or []}
        _EVENTS.append(new)
        return {"created": new}

    @mcp.tool
    def find_free_slot(date: str = "") -> dict:
        """指定日（未指定なら翌日）の空き時間を提案する。"""
        d = date or (_date.today() + timedelta(days=1)).isoformat()
        return {"date": d, "free_slots": ["10:00-10:30", "14:00-15:00", "16:30-17:00"]}

    return mcp


# ======================================================================
# Market Research — 競合・市場（モック）
# ======================================================================

_COMPETITORS = [
    {"name": "CompetitorX", "strength": "低価格", "weakness": "サポート品質", "share_pct": 25},
    {"name": "CompetitorY", "strength": "ブランド力", "weakness": "高価格", "share_pct": 18},
    {"name": "CompetitorZ", "strength": "機能の広さ", "weakness": "UI複雑", "share_pct": 12},
]
_TRENDS = {
    "IT": ["生成AIの業務導入が加速", "セキュリティ投資の増加", "SaaS統合ニーズ"],
    "製造": ["スマートファクトリー", "脱炭素・GX", "予知保全"],
    "小売": ["OMO推進", "在庫最適化AI", "パーソナライズ"],
}


def build_market() -> FastMCP:
    mcp = FastMCP("Market Research MCP")

    @mcp.tool
    def competitor_overview(name: str = "") -> list[dict]:
        """競合の概要（強み/弱み/シェア）を返す。"""
        return [c for c in _COMPETITORS if not name or c["name"] == name]

    @mcp.tool
    def market_trends(industry: str = "IT") -> dict:
        """業界トレンドを返す。"""
        return {"industry": industry, "trends": _TRENDS.get(industry, _TRENDS["IT"])}

    return mcp


_BUILDERS = {
    "crm": build_crm,
    "analytics": build_analytics,
    "email": build_email,
    "kb": build_kb,
    "calendar": build_calendar,
    "market": build_market,
}
