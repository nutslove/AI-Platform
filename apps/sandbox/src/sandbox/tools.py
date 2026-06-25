"""業務寄りの MCP サーバが公開するツール群（モックデータ）。

各ツールは ``Tool``（説明・入力スキーマ・ハンドラ）。ハンドラは引数 dict を
受け取り結果文字列を返す（多くは JSON 文字列）。データはプロセス内に保持し、
作成系ツールはその場で更新する（プロセス再起動で初期化）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str]


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


# 引数なし / 任意引数のスキーマ定義ヘルパ
def _obj(props: dict | None = None, required: list[str] | None = None) -> dict:
    schema: dict = {"type": "object", "properties": props or {}}
    if required:
        schema["required"] = required
    return schema


_STR = {"type": "string"}
_NUM = {"type": "number"}


# ======================================================================
# CRM MCP — 顧客・商談パイプライン
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


def _list_customers(_a: dict) -> str:
    return _json(_CUSTOMERS)


def _get_customer(a: dict) -> str:
    cid = a.get("customer_id")
    cust = next((c for c in _CUSTOMERS if c["id"] == cid), None)
    return _json(cust) if cust else f"顧客が見つかりません: {cid}"


def _list_deals(a: dict) -> str:
    stage = a.get("stage")
    deals = [d for d in _DEALS if not stage or d["stage"] == stage]
    return _json(deals)


def _pipeline_summary(_a: dict) -> str:
    summary: dict = {}
    for d in _DEALS:
        s = summary.setdefault(d["stage"], {"count": 0, "amount": 0})
        s["count"] += 1
        s["amount"] += d["amount"]
    open_amount = sum(d["amount"] for d in _DEALS if d["stage"] not in ("won", "lost"))
    return _json({"by_stage": summary, "open_pipeline_amount": open_amount})


def _create_deal(a: dict) -> str:
    new = {
        "id": f"d{len(_DEALS) + 1}",
        "customer_id": a.get("customer_id", ""),
        "name": a.get("name", "新規商談"),
        "stage": "lead",
        "amount": float(a.get("amount", 0) or 0),
        "owner": a.get("owner", "未割当"),
    }
    _DEALS.append(new)
    return _json({"created": new})


def _update_deal_stage(a: dict) -> str:
    deal = next((d for d in _DEALS if d["id"] == a.get("deal_id")), None)
    if not deal:
        return f"商談が見つかりません: {a.get('deal_id')}"
    deal["stage"] = a.get("stage", deal["stage"])
    return _json({"updated": deal})


CRM_TOOLS: dict[str, Tool] = {
    "list_customers": Tool("list_customers", "顧客一覧を返す", _obj(), _list_customers),
    "get_customer": Tool("get_customer", "顧客IDで顧客詳細を返す", _obj({"customer_id": _STR}, ["customer_id"]), _get_customer),
    "list_deals": Tool("list_deals", "商談一覧を返す（stage で絞り込み可）", _obj({"stage": _STR}), _list_deals),
    "pipeline_summary": Tool("pipeline_summary", "商談をステージ別に集計", _obj(), _pipeline_summary),
    "create_deal": Tool("create_deal", "新規商談を作成", _obj({"customer_id": _STR, "name": _STR, "amount": _NUM}, ["customer_id", "name"]), _create_deal),
    "update_deal_stage": Tool("update_deal_stage", "商談ステージを更新", _obj({"deal_id": _STR, "stage": _STR}, ["deal_id", "stage"]), _update_deal_stage),
}


# ======================================================================
# Analytics MCP — Web/マーケ分析
# ======================================================================

_CAMPAIGNS = [
    {"name": "春のキャンペーン", "impressions": 120000, "clicks": 4200, "conversions": 210, "cost": 350000},
    {"name": "ウェビナー集客", "impressions": 50000, "clicks": 3100, "conversions": 420, "cost": 180000},
    {"name": "リターゲティング", "impressions": 80000, "clicks": 2600, "conversions": 160, "cost": 120000},
]


def _enrich_campaign(c: dict) -> dict:
    ctr = round(c["clicks"] / c["impressions"] * 100, 2)
    cvr = round(c["conversions"] / c["clicks"] * 100, 2)
    cpa = round(c["cost"] / c["conversions"]) if c["conversions"] else None
    return {**c, "ctr_pct": ctr, "cvr_pct": cvr, "cpa": cpa}


def _traffic_summary(a: dict) -> str:
    period = a.get("period", "last_30d")
    return _json(
        {
            "period": period,
            "sessions": 48200,
            "users": 31500,
            "bounce_rate_pct": 42.1,
            "top_sources": [
                {"source": "organic", "share_pct": 38},
                {"source": "paid", "share_pct": 27},
                {"source": "referral", "share_pct": 18},
                {"source": "direct", "share_pct": 17},
            ],
        }
    )


def _campaign_performance(a: dict) -> str:
    name = a.get("campaign")
    rows = [c for c in _CAMPAIGNS if not name or c["name"] == name]
    return _json([_enrich_campaign(c) for c in rows])


def _conversion_funnel(_a: dict) -> str:
    return _json(
        {
            "funnel": [
                {"stage": "訪問", "count": 31500},
                {"stage": "リード", "count": 4200},
                {"stage": "商談", "count": 780},
                {"stage": "受注", "count": 190},
            ]
        }
    )


ANALYTICS_TOOLS: dict[str, Tool] = {
    "traffic_summary": Tool("traffic_summary", "Webトラフィック概要", _obj({"period": _STR}), _traffic_summary),
    "campaign_performance": Tool("campaign_performance", "広告キャンペーンの成果（CTR/CVR/CPA）", _obj({"campaign": _STR}), _campaign_performance),
    "conversion_funnel": Tool("conversion_funnel", "コンバージョンファネル", _obj(), _conversion_funnel),
}


# ======================================================================
# Email MCP — アウトリーチ（ドラフト/送信はモック）
# ======================================================================

_TEMPLATES = [
    {"id": "t1", "name": "初回アプローチ"},
    {"id": "t2", "name": "フォローアップ"},
    {"id": "t3", "name": "提案後リマインド"},
]


def _list_templates(_a: dict) -> str:
    return _json(_TEMPLATES)


def _draft_email(a: dict) -> str:
    return _json(
        {
            "draft": {
                "to": a.get("to", ""),
                "subject": a.get("subject", ""),
                "body": a.get("body", ""),
            },
            "note": "下書きを作成しました（未送信）。",
        }
    )


def _send_email(a: dict) -> str:
    return _json({"sent": True, "to": a.get("to", ""), "subject": a.get("subject", ""), "note": "送信しました（モック）"})


EMAIL_TOOLS: dict[str, Tool] = {
    "list_templates": Tool("list_templates", "メールテンプレ一覧", _obj(), _list_templates),
    "draft_email": Tool("draft_email", "メール下書きを作成", _obj({"to": _STR, "subject": _STR, "body": _STR}, ["to", "subject", "body"]), _draft_email),
    "send_email": Tool("send_email", "メールを送信（モック）", _obj({"to": _STR, "subject": _STR, "body": _STR}, ["to", "subject", "body"]), _send_email),
}


# ======================================================================
# Knowledge Base MCP — 製品/社内ドキュメント
# ======================================================================

_DOCS = [
    {"id": "k1", "title": "製品概要", "body": "当社SaaSは営業・マーケ業務を自動化するプラットフォーム。CRM/分析/メール連携を提供。"},
    {"id": "k2", "title": "料金プラン", "body": "Starter 月3万円 / Pro 月10万円 / Enterprise 個別見積。年契約で2ヶ月分割引。"},
    {"id": "k3", "title": "よくある質問", "body": "解約はいつでも可能。SSO対応。データはGCPに保存。SLA 99.9%。"},
    {"id": "k4", "title": "導入事例: Globex", "body": "Globex社はリード対応時間を60%短縮、商談化率を1.4倍に改善。"},
]


def _list_docs(_a: dict) -> str:
    return _json([{"id": d["id"], "title": d["title"]} for d in _DOCS])


def _search_docs(a: dict) -> str:
    q = str(a.get("query", "")).lower()
    hits = [d for d in _DOCS if q in d["title"].lower() or q in d["body"].lower()]
    return _json(hits or {"note": f"該当なし: {q}"})


def _get_doc(a: dict) -> str:
    doc = next((d for d in _DOCS if d["id"] == a.get("doc_id")), None)
    return _json(doc) if doc else f"ドキュメントが見つかりません: {a.get('doc_id')}"


KB_TOOLS: dict[str, Tool] = {
    "list_docs": Tool("list_docs", "ドキュメント一覧", _obj(), _list_docs),
    "search_docs": Tool("search_docs", "ドキュメント全文検索", _obj({"query": _STR}, ["query"]), _search_docs),
    "get_doc": Tool("get_doc", "ドキュメント本文を取得", _obj({"doc_id": _STR}, ["doc_id"]), _get_doc),
}


# ======================================================================
# Calendar MCP — 予定・日程調整
# ======================================================================

_EVENTS = [
    {"id": "e1", "title": "Acme 定例", "date": (date.today() + timedelta(days=1)).isoformat(), "attendees": ["営業A"]},
    {"id": "e2", "title": "Initech デモ", "date": (date.today() + timedelta(days=2)).isoformat(), "attendees": ["営業B"]},
]


def _list_events(a: dict) -> str:
    d = a.get("date")
    events = [e for e in _EVENTS if not d or e["date"] == d]
    return _json(events)


def _create_event(a: dict) -> str:
    new = {
        "id": f"e{len(_EVENTS) + 1}",
        "title": a.get("title", "新規予定"),
        "date": a.get("date", date.today().isoformat()),
        "attendees": a.get("attendees", []),
    }
    _EVENTS.append(new)
    return _json({"created": new})


def _find_free_slot(a: dict) -> str:
    d = a.get("date", (date.today() + timedelta(days=1)).isoformat())
    return _json({"date": d, "free_slots": ["10:00-10:30", "14:00-15:00", "16:30-17:00"]})


CALENDAR_TOOLS: dict[str, Tool] = {
    "list_events": Tool("list_events", "予定一覧（date で絞り込み可）", _obj({"date": _STR}), _list_events),
    "create_event": Tool("create_event", "予定を作成", _obj({"title": _STR, "date": _STR, "attendees": {"type": "array", "items": _STR}}, ["title", "date"]), _create_event),
    "find_free_slot": Tool("find_free_slot", "空き時間を提案", _obj({"date": _STR}), _find_free_slot),
}


# ======================================================================
# Market Research MCP — 競合・市場（モック）
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


def _competitor_overview(a: dict) -> str:
    name = a.get("name")
    rows = [c for c in _COMPETITORS if not name or c["name"] == name]
    return _json(rows)


def _market_trends(a: dict) -> str:
    industry = a.get("industry", "IT")
    return _json({"industry": industry, "trends": _TRENDS.get(industry, _TRENDS["IT"])})


MARKET_TOOLS: dict[str, Tool] = {
    "competitor_overview": Tool("competitor_overview", "競合の概要（強み/弱み/シェア）", _obj({"name": _STR}), _competitor_overview),
    "market_trends": Tool("market_trends", "業界トレンド", _obj({"industry": _STR}), _market_trends),
}
