// Backend (/api/v1) のスキーマと 1:1 で対応する型定義。

export type Role = "admin" | "user";

export interface User {
  id: string;
  username: string;
  role: Role;
  /** ABAC 用の属性。例: { department: "営業部" } */
  attributes: Record<string, string>;
}

/** アクセスポリシー: 属性キー -> 許可値リスト。空 {} は全員可 */
export type AccessPolicy = Record<string, string[]>;

export interface Agent {
  id: string;
  name: string;
  description: string;
  /** A2A の Agent Card / エンドポイント URL */
  a2a_url: string;
  skills: string[];
  /** アクセスポリシー（どの属性なら使えるか） */
  access: AccessPolicy;
  /** 現在のユーザが利用を許可されているか（一覧では false でも表示する） */
  allowed: boolean;
}

export type McpTransport = "http" | "stdio";

export interface McpServer {
  id: string;
  name: string;
  description: string;
  transport: McpTransport;
  url: string;
  access: AccessPolicy;
  allowed: boolean;
}

/** ユーザ自身が有効化した集合（allowed の部分集合） */
export interface Enablements {
  enabled_agent_ids: string[];
  enabled_mcp_server_ids: string[];
}

/** Agent + MCP サーバを組み合わせた独自 Agent */
export interface CustomAgent {
  id: string;
  owner_id: string;
  name: string;
  description: string;
  agent_ids: string[];
  mcp_server_ids: string[];
}

export interface CustomAgentCreate {
  name: string;
  description: string;
  agent_ids: string[];
  mcp_server_ids: string[];
}

export interface ExecuteRequest {
  agent_ids: string[];
  mcp_server_ids: string[];
  input: string;
}

export interface ExecutionStep {
  source: string;
  detail: string;
}

export interface ExecuteResponse {
  status: string;
  steps: ExecutionStep[];
  output: string;
}
