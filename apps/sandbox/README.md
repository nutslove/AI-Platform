# sandbox

プロトタイプ用の A2A エージェントと MCP サーバ。1 つのイメージから、環境変数
`SERVICE_KIND` / `SERVICE_NAME` で MCP サーバにもエージェントにもなる。

- MCP サーバ: calculator / text / datetime / weather
- A2A エージェント: math / writer / assistant

A2A・MCP とも、チームで読みやすいよう公式 SDK ではなく **JSON-RPC の最小サブセット**
を手書きしている（プロトタイプ用）。エージェントは LLM を使わない決定的ルールベース。
