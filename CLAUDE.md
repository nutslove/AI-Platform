# AI Platform

MCPサーバとAI Agentを一元管理する統合プラットフォーム。レジストリに登録された Agent / MCPサーバを一覧表示し、ADMIN がユーザごとの利用可否（RBAC）を設定、一般ユーザは許可された Agent / MCPサーバを有効化して GUI 上で自由に組み合わせ、その場で実行できる。

## プロダクト要件

このプロジェクトが満たすべき機能要件。実装の判断に迷ったらここに立ち返る。

- **レジストリ**: Agent と MCPサーバを登録・管理し、一覧として表示する。
- **Agent**: [A2A（Agent2Agent）プロトコル](https://a2a-protocol.org/) に対応する。各 Agent は Agent Card を公開し、他 Agent / プラットフォームから発見・呼び出し可能。
- **MCPサーバ**: [MCP（Model Context Protocol）](https://modelcontextprotocol.io/) に準拠したツール／リソース提供サーバ。
- **RBAC**:
  - **ADMIN** はユーザ（またはロール）ごとに、利用可能な Agent と MCPサーバを割り当てる。
  - **一般ユーザ** は自分に割り当てられた Agent / MCPサーバの中から、使うものを有効化（選択）する。
  - ユーザに割り当てられていない Agent / MCPサーバは一覧にも実行対象にも現れない。
- **GUI でのオーケストレーション**: ユーザは GUI 上で複数の Agent と MCPサーバを選択し、自由に組み合わせて構成を作る。
- **GUI からの実行**: 組み合わせた構成を GUI 上から実行し、結果（A2A のタスク進捗・ストリーミング出力含む）を表示する。

## 技術スタック

- **Frontend**: TypeScript + React（[apps/frontend/](apps/frontend/)）
- **Backend**: Python 3.13 + FastAPI（[apps/backend/](apps/backend/)、パッケージ管理は `uv`）
- **コンテナ**: Frontend / Backend それぞれの Dockerfile と、ルートの `docker-compose.yml` でローカル一括起動。

## リポジトリ構成

モノレポ。アプリは `apps/` 配下に置く。

```
apps/
  backend/                  # FastAPI（src レイアウト）
    src/backend/
      main.py               # FastAPI エントリポイント（app 定義、ルータ登録）
      api/routes.py         # APIRouter。prefix="/api/v1"
    tests/                  # pytest（conftest.py）
    pyproject.toml          # 依存は uv で管理
    Dockerfile
  frontend/                 # React + TypeScript
    Dockerfile
  sandbox/                  # プロトタイプの A2A エージェント / MCP サーバ
    src/sandbox/
      tools.py              # MCP ツール実装（calculator/text/datetime/weather）
      mcp_server.py         # MCP サーバ最小実装（JSON-RPC）
      mcp_client.py         # エージェントが使う MCP クライアント
      agent.py              # A2A エージェント最小実装
      main.py               # SERVICE_KIND/SERVICE_NAME で役割を切替
    Dockerfile
docker-compose.yml          # frontend + backend + 7 個の sandbox サービス
```

> 現状: レジストリ / RBAC / 有効化 / 実行の API と、4 画面の Frontend、プロトタイプの A2A エージェント・MCP サーバ（[apps/sandbox/](apps/sandbox/)）、Docker 一式まで実装済み。`/execute` は実際に A2A で各エージェントを呼び、エージェントは選択された MCP に接続してツールを実行する（[実行フロー](#実行フローa2a--mcp)参照）。データは backend のインメモリストア（[store/memory.py](apps/backend/src/backend/store/memory.py)、シードデータあり）で保持しており、永続 DB への差し替えが次の課題。

## プロトタイプの Agent / MCP（apps/sandbox）

チームでの意識合わせ用に、**実際に動く** A2A エージェントと MCP サーバを用意している。A2A・MCP は読みやすさ優先で **JSON-RPC の最小サブセットを手書き**。1 つのイメージから環境変数で役割を切り替える（[main.py](apps/sandbox/src/sandbox/main.py)）。

業務寄りのモック構成。

- MCP サーバ(6): CRM（顧客・商談）/ Analytics（CTR/CVR/CPA・ファネル）/ Email（下書き・送信モック）/ Knowledge Base（製品/社内ドキュメント）/ Calendar（日程）/ Market Research（競合・市場トレンド）
- A2A エージェント(4): Sales（営業）/ Marketing（マーケ）/ Support（CS）/ Revenue Analyst（分析）。各エージェントは役割別の system プロンプトを持ち、選択された MCP のツールを Gemini が自律選択して実行する（[main.py](apps/sandbox/src/sandbox/main.py)、[tools.py](apps/sandbox/src/sandbox/tools.py)）。

複数エージェント×複数 MCP を「実行」画面やカスタム Agent で組み合わせられる。複数エージェント時はオーケストレータが順に実行し、2 番目以降には「元タスク + 前段エージェントの結果」を渡す。

### エージェントの実行エンジン（GCP Vertex AI / Gemini）

エージェントは **GCP Vertex AI 上の Gemini**（`google-genai` SDK、[llm.py](apps/sandbox/src/sandbox/llm.py)）で動く。認証は **ADC**（`~/.config/gcloud/application_default_credentials.json` をコンテナにマウント、`GOOGLE_APPLICATION_CREDENTIALS` で指定）。プロジェクトは `GOOGLE_CLOUD_PROJECT`、無ければ ADC の `quota_project_id` から解決。モデルは `GEMINI_MODEL`（既定 `gemini-2.5-flash`）、ロケーションは `CLOUD_ML_REGION`（既定 `global`）。

実行時、エージェントは選択された MCP サーバの `tools/list` を Gemini の `FunctionDeclaration` に変換し、**function calling ループ**で `tools/call` を実行する。**Vertex 呼び出しが失敗した場合（クォータ/権限等）は LLM 不要の決定的ルールベースにフォールバック**するので、GCP 未設定でもデモは動く（[agent.py](apps/sandbox/src/sandbox/agent.py)）。

### トレース（LangSmith）

`langsmith` SDK の `@traceable` / `trace` で計装済み（[llm.py](apps/sandbox/src/sandbox/llm.py)）。`.env` に `LANGSMITH_TRACING=true` と `LANGSMITH_API_KEY` を設定すると、エージェントの実行が LangSmith に送信される（root=エージェント、子に Gemini 呼び出し[llm スパン]・各 MCP ツール[tool スパン]）。compose が agent サービスへ環境変数を渡す。**未設定なら完全な no-op**（ネットワークアクセス無し）。LangChain には依存しない。設定例は [.env.example](.env.example)。

### 実行フロー（A2A + MCP）

`/execute`（[execution.py](apps/backend/src/backend/api/execution.py)）はオーケストレータとして動く:

1. 選択された MCP サーバの接続情報を、A2A メッセージの `metadata.mcpServers` に載せる
2. 選択された各エージェントへ順に `message/send`（A2A）を送る
3. エージェントは受け取った MCP に接続し、ツールを実行して結果を返す
4. 複数エージェント時は前段の出力を次段の入力へ渡す（素朴な出力連鎖。テキスト変換系では要約文ごと再加工される点は既知の挙動で、構造化ハンドオフは今後の課題）

## API 概要（`/api/v1`）

認証は簡易実装で、現在のユーザを `X-User-Id` ヘッダで識別する（[api/deps.py](apps/backend/src/backend/api/deps.py)）。本番では OIDC / JWT に差し替える。Frontend は簡易ログインとしてユーザを切り替えてこのヘッダを送る。

| メソッド | パス | 権限 | 用途 |
| --- | --- | --- | --- |
| GET | `/me` | 認証 | 現在のユーザ |
| GET | `/users` | admin | ユーザ一覧 |
| PUT | `/users/{id}/attributes` | admin | ユーザ属性（部署など）の設定 |
| GET | `/departments` | 認証 | 属性 department の選択肢 |
| GET | `/agents`, `/mcp-servers` | 認証 | 全件返し、各要素に `allowed`（属性ベース判定）を付与 |
| PUT | `/agents/{id}/access`, `/mcp-servers/{id}/access` | admin | アクセスポリシー（許可属性）の設定 |
| POST/DELETE | `/agents`, `/mcp-servers` | admin | レジストリ登録・削除 |
| GET/PUT | `/me/enablements` | 認証 | 有効化集合の取得・更新（allowed の部分集合のみ可） |
| GET/POST/DELETE | `/me/custom-agents` | 認証 | カスタム Agent（Agent + MCP の組み合わせ）の一覧・作成・削除 |
| POST | `/me/custom-agents/{id}/run` | 認証 | 保存したカスタム Agent を実行 |
| POST | `/execute` | 認証 | 有効化済みの Agent/MCP を組み合わせて実行 |

`/agents`・`/mcp-servers` は**全件**を返し、各要素に現在ユーザの `allowed`（利用可否）を付ける。フロントは使えないものも表示しつつ非活性化する。実行系（`/execute`・カスタム Agent 実行）は [execution.py](apps/backend/src/backend/api/execution.py) の `run_composition` を共通で使う。

アクセス制御は **属性ベース（ABAC）**。ユーザは属性（`attributes`、例 `{"department": "営業部"}`）を持ち、各 Agent / MCP サーバは `access`（許可ポリシー、例 `{"department": ["営業部","分析部"]}`、空 = 全員可）を持つ。ユーザがリソースを使えるか（allowed）は属性とポリシーから計算する（[store/memory.py](apps/backend/src/backend/store/memory.py) の `_user_allowed` / `allowed_agent_ids`）。

権限の階層は **allowed（属性ベース判定）⊇ enabled（ユーザが有効化）⊇ 実行時に選択** で、各段の検証は必ず backend 側で行う。属性やポリシーが変わって allowed から外れたものは、`get_enablements` が自動でフィルタする。

## 開発コマンド

### Backend（[apps/backend/](apps/backend/) で実行）

```bash
uv sync                                   # 依存インストール
uv run uvicorn backend.main:app --reload  # 開発サーバ（http://localhost:8000）
uv run ruff check .                       # Lint
uv run ruff format .                      # フォーマット
uv run pytest                             # テスト
```

### Frontend（[apps/frontend/](apps/frontend/) で実行）

```bash
npm install
npm run dev      # 開発サーバ
npm run build    # 本番ビルド
npm run lint
```

### Docker

```bash
docker compose up --build   # 全サービス起動
```

## アーキテクチャ指針

- **API バージョニング**: backend のルートは `/api/v1` プレフィックス配下。新しいルータは `api/` に追加し `main.py` で `include_router` する。
- **ドメイン分離**: レジストリ / RBAC / 実行（オーケストレーション）は責務を分ける。`api/`（ルーティング）と、ビジネスロジック・永続化層を混在させない。
- **RBAC の評価**: 「ユーザに割り当てられた集合」と「ユーザが有効化した集合」は別概念。実行時の権限チェックは必ずサーバ側（backend）で行い、frontend の選択状態を信頼しない。
- **A2A / MCP は外部プロトコル**: 仕様に準拠する。独自拡張する場合はその旨をコメントで明示する。Agent の発見は Agent Card、ツール呼び出しは MCP のスキーマに従う。
- **設定は環境変数**: シークレット（API キー、DB 接続情報）はコードに埋め込まず環境変数 / `.env` から読む。`.env` はコミットしない。

## コーディング規約

- **Backend**: ruff の設定に従う。型ヒントを付ける（`py.typed` 配布）。FastAPI のエンドポイントは Pydantic モデルで入出力を定義する。
- **Frontend**: TypeScript の strict モードを前提に、`any` を避ける。
- 既存ファイルのスタイル（命名・コメント量・構成）に合わせる。

## LLM 利用時の方針

Agent 実装などで Claude を呼び出す場合は最新かつ最も高性能なモデルを既定にする。モデルID:

- Opus 4.8: `claude-opus-4-8`
- Sonnet 4.6: `claude-sonnet-4-6`
- Haiku 4.5: `claude-haiku-4-5-20251001`
- Fable 5: `claude-fable-5`

実装前に最新の料金・パラメータを確認すること（記憶で答えない）。
