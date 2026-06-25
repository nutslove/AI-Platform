# AI Platform

MCPサーバ、AI Agent を一元管理するプラットフォーム。

レジストリに登録された Agent / MCPサーバを一覧表示し、ADMIN がユーザごとの利用可否（RBAC）を設定、一般ユーザは許可された Agent / MCPサーバを有効化して GUI 上で自由に組み合わせ、その場で実行できる。

- **Frontend**: TypeScript + React（Vite）— [apps/frontend/](apps/frontend/)
- **Backend**: Python 3.13 + FastAPI（uv）— [apps/backend/](apps/backend/)

開発・設計方針の詳細は [CLAUDE.md](CLAUDE.md) を参照。

## 必要なもの

- [Docker](https://www.docker.com/) と Docker Compose（`docker compose` または `docker-compose`）
- **GCP Vertex AI（Gemini）の認証**: エージェントは Vertex 上の Gemini を使う。`gcloud auth application-default login` で ADC を作成し、`~/.config/gcloud/application_default_credentials.json` を用意する（compose が自動でマウント）。プロジェクトは ADC の `quota_project_id` を使う（`GOOGLE_CLOUD_PROJECT` で上書き可）。モデルは `GEMINI_MODEL`（既定 `gemini-2.5-flash`）。
  - Vertex が使えない場合でも、エージェントは**ルールベースにフォールバック**してデモは動く。
- ローカルで個別に動かす場合: [uv](https://docs.astral.sh/uv/)（Backend）、Node.js 20+（Frontend）

## 起動方法（Docker Compose・推奨）

リポジトリのルートで実行する。

```bash
docker-compose up --build -d   # ビルドして起動（バックグラウンド）
docker-compose ps              # 状態確認
docker-compose logs -f         # ログ追跡
docker-compose down            # 停止・コンテナ削除
```

> `docker compose`（v2 プラグイン）が使える環境では `docker compose ...` でも同じ。

起動後にアクセスする URL:

| 用途 | URL |
| --- | --- |
| アプリ画面 | http://localhost:5173 |
| API ドキュメント (Swagger) | http://localhost:8000/docs |

### ログイン（共通パスワード）

`.env` に `APP_PASSWORD` を設定すると、アプリを開いたとき最初にパスワード入力を求める（面接デモなどで画面を見せる前のゲート）。未設定ならログイン不要。

```
APP_PASSWORD=demo1234
```

- 設定後は `docker-compose up -d` で反映。ログイン後はトークンがブラウザに保存され、左下「ログアウト」で解除できる。
- これはアプリ全体の入口ゲート（共通パスワード）。下記の「現在のユーザ」切替（alice/bob…）は ABAC デモ用の簡易ユーザ切替で、別物。

左下の「現在のユーザ」でユーザを切り替えられる（`X-User-Id` ヘッダでユーザを識別。本番では OIDC / JWT に置き換える）。`admin` のみ「RBAC 管理」メニューが表示される。

### アクセス制御は属性ベース（ABAC）

各ユーザは **部署属性** を持ち、各 Agent / MCP サーバは **「どの部署が使えるか」** のポリシーを持つ。ユーザが使えるかは属性×ポリシーで決まる（個別割り当てではない）。シードのユーザと部署:

| ユーザ | 部署 | 使える Agent | 使える MCP |
| --- | --- | --- | --- |
| `alice` | 営業部 | Sales | CRM / Email / Calendar / Knowledge Base |
| `bob` | マーケティング部 | Marketing / Revenue Analyst | Analytics / Email / Market Research / Knowledge Base |
| `carol` | サポート部 | Support | CRM / Email / Knowledge Base |
| `dave` | 分析部 | Revenue Analyst | CRM / Analytics / Market Research / Knowledge Base |
| `admin` | （管理） | すべて | すべて |

> Knowledge Base MCP はアクセスポリシーが空 = **全社公開**。**使えない Agent / MCP** は一覧に「利用不可」バッジ付きで表示され非活性化される。

## 試せるパターン例

### パターン1: 部署ごとに見えるツールが変わる（ABAC）
左下のユーザを `alice`(営業) / `bob`(マーケ) / `carol`(サポート) / `dave`(分析) と切り替え、「レジストリ」画面を見る。部署に応じて使える Agent / MCP が変わり、使えないものは「利用不可」表示になる。

### パターン2: 単一 Agent ×複数 MCP（営業）
`alice` で「マイツール」→ Sales Agent と CRM / Email を有効化 →「実行」で Sales Agent ＋ CRM ＋ Email を選択。
入力例: **「今のパイプライン状況を要約して、最も金額の大きい進行中の商談へのフォローアップメール下書きも作って」**
→ Gemini が `pipeline_summary` / `draft_email` 等を自律実行。

### パターン3: 複数 Agent ×複数 MCP の連鎖（マーケ→分析）
`bob` で Marketing Agent ＋ Revenue Analyst Agent を選び、Analytics / Market Research / CRM を有効化して実行。
入力例: **「今期のマーケ施策の成果を評価し、IT業界の市場トレンドも踏まえて来期に注力すべき施策を提案して」**
→ Marketing が `campaign_performance`/`market_trends` を実行 → Analyst が「元タスク＋前段結果」を受けて結論＋根拠数値で提案（A2A 連鎖）。

### パターン4: カスタム Agent（組み合わせを保存）
「カスタムAgent」画面で、有効化済みの Agent と MCP を組み合わせて独自 Agent を作成・保存し、ワンクリック実行。
例: 「営業デイリー」= Sales Agent ＋ CRM ＋ Calendar、入力「今日の予定と動くべき商談は？」

### パターン5: ABAC を管理者が変更（admin）
`admin` で「RBAC 管理」を開く。
- **① ユーザの部署**: 例えば `alice` を「マーケティング部」に変更 → alice で見ると Marketing Agent が使えるようになる。
- **② リソースのアクセスポリシー**: 例えば Calendar MCP に「マーケティング部」を追加 → マーケのユーザも Calendar を使えるようになる。部署を全部外すと「全員可（公開）」。

業務向けの Agent / MCP は [apps/sandbox/](apps/sandbox/) にある（CRM/Analytics/Email/KB/Calendar/Market の MCP と 営業/マーケ/CS/分析 の Agent、モックデータ入り）。実行の仕組みは [CLAUDE.md](CLAUDE.md) を参照。

> データは Backend のインメモリストア（シードデータあり）で保持するため、`docker-compose down` や Backend 再起動で登録内容・RBAC 設定は初期状態に戻る。

## ローカル個別起動（任意）

Docker を使わずに動かす場合。

### Backend（[apps/backend/](apps/backend/)）

```bash
cd apps/backend
uv sync
uv run uvicorn backend.main:app --reload   # http://localhost:8000
uv run pytest                              # テスト
```

### Frontend（[apps/frontend/](apps/frontend/)）

```bash
cd apps/frontend
npm install
npm run dev                                # http://localhost:5173
```

Vite の dev サーバが `/api` を Backend (`http://localhost:8000`) へプロキシする。プロキシ先は `VITE_BACKEND_URL` で変更可能（[.env.example](apps/frontend/.env.example) 参照）。

## ディレクトリ構成

```
apps/
  backend/    # FastAPI（レジストリ / RBAC / 有効化 / 実行 API）
  frontend/   # React + TypeScript（レジストリ / RBAC管理 / マイツール / 実行）
  sandbox/    # プロトタイプの A2A エージェント(3) / MCP サーバ(4)
docker-compose.yml
CLAUDE.md     # 設計・開発方針
```
