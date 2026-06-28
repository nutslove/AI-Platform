# アーキテクチャ図

このプラットフォームの構成図。 **現状（実装済み）** と、 **将来構想（AI Gateway / MCP Gateway 追加）** の 2 つを示す。
図は [Mermaid](https://mermaid.js.org/)。GitHub・VS Code（Markdown Preview Mermaid 拡張）でそのまま描画される。面接で見せるなら GitHub に push してプレビュー、もしくは [mermaid.live](https://mermaid.live) に貼ると確実。

---

## 1. 現状アーキテクチャ（実装済み）

ユーザのリクエストはフロント → backend（オーケストレータ）→ A2A で各 Agent →（Agent が）MCP に接続、という流れ。
権限は backend で 3 段階に評価し、LLM は Vertex 上の Gemini、トレースは LangSmith。

```mermaid
flowchart TB
  subgraph Client["ブラウザ"]
    FE["Frontend<br/>React + TypeScript + Vite<br/>(nginx 配信)"]
  end

  subgraph Backend["Backend — FastAPI (uv)"]
    AUTH["簡易認証<br/>X-User-Id / X-App-Token"]
    REG["レジストリ<br/>Agent / MCP 登録・一覧"]
    RBAC["ABAC エンジン<br/>属性×ポリシーで allowed 判定"]
    ENA["有効化ストア<br/>enabled ⊆ allowed"]
    ORCH["オーケストレータ<br/>/execute・/execute/stream<br/>A2A 呼び出し＋連鎖＋SSE中継"]
    STORE[("インメモリストア<br/>users / resources /<br/>enablements / custom agents")]
  end

  subgraph Agents["A2A エージェント (apps/sandbox, 4)"]
    AG["Sales / Marketing /<br/>Support / Revenue Analyst<br/>──────────<br/>A2A 受け口: FastAPI<br/>実行: LangChain / LangGraph<br/>ReAct エージェント"]
  end

  subgraph MCPs["MCP サーバ (apps/sandbox, 6)"]
    MCP["CRM / Analytics / Email /<br/>Knowledge Base / Calendar /<br/>Market Research<br/>──────────<br/>FastMCP (Streamable HTTP)"]
  end

  subgraph GCP["Google Cloud"]
    GEM["Vertex AI<br/>Gemini 2.5 Flash<br/>(ADC 認証)"]
  end

  LS["LangSmith<br/>(トレース / 任意)"]

  FE -->|"REST + SSE<br/>/api/v1"| AUTH
  AUTH --> REG & RBAC & ENA & ORCH
  REG & RBAC & ENA & ORCH <--> STORE
  ORCH -->|"A2A message/send<br/>(metadata.mcpServers)"| AG
  AG -->|"MCP ツール呼び出し<br/>(langchain-mcp-adapters)"| MCP
  AG -->|"function calling"| GEM
  AG -.->|"@traceable / trace"| LS

  classDef done fill:#e3f2e3,stroke:#4caf50,color:#1b5e20;
  classDef ext fill:#e3f0fb,stroke:#1976d2,color:#0d47a1;
  class FE,AUTH,REG,RBAC,ENA,ORCH,STORE,AG,MCP done;
  class GEM,LS ext;
```

### リクエストの流れ（実行時）

```mermaid
sequenceDiagram
  participant U as ブラウザ
  participant B as Backend<br/>(オーケストレータ)
  participant A as A2A Agent<br/>(LangGraph)
  participant M as MCP サーバ<br/>(FastMCP)
  participant G as Vertex Gemini

  U->>B: POST /execute/stream<br/>(agent_ids, mcp_server_ids, input)
  Note over B: ABAC 検証<br/>allowed ⊇ enabled ⊇ 選択
  B->>A: A2A message/send (SSE /stream)<br/>metadata.mcpServers
  A->>M: ツール一覧取得 (MCP)
  loop ReAct ループ
    A->>G: 推論（次のツールは？）
    G-->>A: tool_call
    A->>M: ツール実行
    M-->>A: 結果
  end
  A->>G: 最終回答生成
  G-->>A: トークン（ストリーム）
  A-->>B: SSE: token / tool / final
  B-->>U: SSE 中継: step / token / done
  Note over U: 処理ログ＋回答を<br/>ストリーミング表示
```

---

## 2. 将来構想 — AI Gateway / MCP Gateway 追加版

**全 LLM 呼び出しを AI Gateway に、全 MCP ツール呼び出しを MCP Gateway に集約**する。
横断的な関心事（認証・レート制限・コスト管理・監査ログ・PII マスキング・キャッシュ・モデル/ツールの差し替え）を各 Agent から剥がし、**ガバナンスを 1 か所**に効かせる構成。

```mermaid
flowchart TB
  subgraph Client["ブラウザ"]
    FE["Frontend (React)"]
  end

  subgraph Backend["Backend — FastAPI"]
    IAM["認証 (OIDC / JWT)<br/>※簡易実装から差し替え"]
    CORE["レジストリ / ABAC /<br/>有効化 / オーケストレータ"]
    DB[("永続 DB<br/>PostgreSQL<br/>※インメモリから差し替え")]
  end

  subgraph AIGW["★ AI Gateway （新規）"]
    direction TB
    AGW["・APIキー/認可の集約<br/>・レート制限 / クォータ<br/>・コスト計測・予算<br/>・プロンプト/応答ログ・監査<br/>・PII マスキング・ガードレール<br/>・モデルルーティング / フォールバック<br/>・セマンティックキャッシュ"]
  end

  subgraph MCPGW["★ MCP Gateway （新規）"]
    direction TB
    MGW["・MCP サーバの発見・登録<br/>・ツール単位の認可<br/>・呼び出し監査・レート制限<br/>・スキーマ検証 / サニタイズ<br/>・シークレット注入<br/>・テナント分離"]
  end

  subgraph Agents["A2A エージェント (N)"]
    AG["Sales / Marketing /<br/>Support / Analyst / …"]
  end

  subgraph MCPs["MCP サーバ (N)"]
    MCP["CRM / Analytics / Email /<br/>KB / Calendar / Market / …"]
  end

  subgraph LLMs["LLM プロバイダ（差し替え可能）"]
    L1["Vertex Gemini"]
    L2["Anthropic Claude"]
    L3["OpenAI 等"]
  end

  OBS["可観測性<br/>LangSmith / OpenTelemetry /<br/>メトリクス・ダッシュボード"]

  FE -->|REST + SSE| IAM --> CORE <--> DB
  CORE -->|A2A| AG
  AG -->|"LLM 呼び出しは全部ここ経由"| AGW
  AGW --> L1 & L2 & L3
  AG -->|"ツール呼び出しは全部ここ経由"| MGW
  MGW --> MCP
  AGW -.-> OBS
  MGW -.-> OBS
  AG -.-> OBS

  classDef done fill:#e3f2e3,stroke:#4caf50,color:#1b5e20;
  classDef new fill:#fff3e0,stroke:#fb8c00,color:#e65100,stroke-width:2px;
  classDef ext fill:#e3f0fb,stroke:#1976d2,color:#0d47a1;
  class FE,CORE,AG,MCP done;
  class AGW,MGW,IAM,DB new;
  class L1,L2,L3,OBS ext;
```

### なぜ Gateway を挟むのか（面接での説明用）

| 関心事 | Gateway なし（現状） | Gateway あり（構想） |
| --- | --- | --- |
| **コスト管理** | 各 Agent がバラバラに LLM を叩く。総コストが見えない | AI Gateway で全呼び出しを計測。部署別・ユーザ別に予算/上限 |
| **レート制限** | プロバイダ側の上限に各自で当たる | Gateway で集中管理、公平にスロットリング |
| **監査・コンプラ** | ログが分散 | プロンプト/応答/ツール呼び出しを一元監査。PII マスキング |
| **モデル差し替え** | 各 Agent のコード変更が必要 | Gateway のルーティング設定だけで切替・A/B・フォールバック |
| **ツールのガバナンス** | Agent が MCP に直結 | MCP Gateway がツール単位で認可・検証・シークレット注入 |
| **セキュリティ** | シークレットが各 Agent に分散 | Gateway がシークレットを集中保管・注入 |

> **言い方の例**: 「AI Gateway / MCP Gateway は、ネットワークでいう **API Gateway / サービスメッシュ**の AI 版です。横断的関心事を Agent から剥がして 1 か所に集約することで、組織が Agent やツールを増やしてもガバナンスが破綻しない。これが本番運用に向けた次の一手です。」

---

## 3. ロードマップ（現状 → 本番）

```mermaid
flowchart LR
  P1["現状<br/>プロトタイプ"] --> P2["永続化<br/>PostgreSQL<br/>OIDC/JWT 認証"]
  P2 --> P3["Gateway 導入<br/>AI / MCP Gateway<br/>監査・コスト・レート"]
  P3 --> P4["本番運用<br/>マルチテナント<br/>可観測性・SLO"]

  classDef now fill:#e3f2e3,stroke:#4caf50,color:#1b5e20;
  classDef next fill:#fff3e0,stroke:#fb8c00,color:#e65100;
  class P1 now;
  class P2,P3,P4 next;
```

| フェーズ | 主な作業 | 解決する課題 |
| --- | --- | --- |
| 現状 | レジストリ / ABAC / GUI 実行 / A2A・MCP / ストリーミング | コア機能の実証 |
| 永続化 | インメモリ → PostgreSQL、認証を OIDC/JWT 化 | 再起動で消えない・本物の認証 |
| Gateway | AI Gateway / MCP Gateway 導入 | コスト・レート・監査・PII・モデル差し替え |
| 本番運用 | マルチテナント、OpenTelemetry、SLO/アラート | 組織スケールでの安定運用 |
