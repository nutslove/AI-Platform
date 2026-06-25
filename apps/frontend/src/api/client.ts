import type {
  AccessPolicy,
  Agent,
  CustomAgent,
  CustomAgentCreate,
  Enablements,
  ExecuteRequest,
  ExecuteResponse,
  McpServer,
  User,
} from "../types";

const BASE = "/api/v1";

// 簡易認証: 現在のユーザ ID を X-User-Id ヘッダで送る。
// 本番ではここを OIDC / JWT などに置き換える。
let currentUserId: string | null = localStorage.getItem("userId");

export function setCurrentUserId(id: string | null) {
  currentUserId = id;
  if (id) localStorage.setItem("userId", id);
  else localStorage.removeItem("userId");
}

export function getCurrentUserId(): string | null {
  return currentUserId;
}

// 共通パスワードのアプリトークン（簡易ログイン用）。X-App-Token で送る。
let appToken: string | null = localStorage.getItem("appToken");

export function setAppToken(token: string | null) {
  appToken = token;
  if (token) localStorage.setItem("appToken", token);
  else localStorage.removeItem("appToken");
}

export function getAppToken(): string | null {
  return appToken;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (currentUserId) headers["X-User-Id"] = currentUserId;
  if (appToken) headers["X-App-Token"] = appToken;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // --- 簡易ログイン（共通パスワード）---
  authConfig: () => request<{ login_required: boolean }>("/auth/config"),
  login: (password: string) =>
    request<{ token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  authVerify: () => request<{ ok: boolean }>("/auth/verify"),

  // --- auth / users ---
  me: () => request<User>("/me"),
  /** 簡易ログインのユーザ選択用（無認証）。本番では認証基盤に置き換える */
  listLoginUsers: () => request<User[]>("/auth/users"),
  /** 管理画面用のユーザ一覧（admin 限定） */
  listUsers: () => request<User[]>("/users"),

  // --- registry (role に応じてフィルタされた一覧が返る) ---
  listAgents: () => request<Agent[]>("/agents"),
  createAgent: (a: Omit<Agent, "id" | "allowed" | "access">) =>
    request<Agent>("/agents", { method: "POST", body: JSON.stringify(a) }),
  deleteAgent: (id: string) =>
    request<void>(`/agents/${id}`, { method: "DELETE" }),
  setAgentAccess: (id: string, access: AccessPolicy) =>
    request<Agent>(`/agents/${id}/access`, {
      method: "PUT",
      body: JSON.stringify({ access }),
    }),

  listMcpServers: () => request<McpServer[]>("/mcp-servers"),
  createMcpServer: (m: Omit<McpServer, "id" | "allowed" | "access">) =>
    request<McpServer>("/mcp-servers", { method: "POST", body: JSON.stringify(m) }),
  deleteMcpServer: (id: string) =>
    request<void>(`/mcp-servers/${id}`, { method: "DELETE" }),
  setMcpAccess: (id: string, access: AccessPolicy) =>
    request<McpServer>(`/mcp-servers/${id}/access`, {
      method: "PUT",
      body: JSON.stringify({ access }),
    }),

  // --- ABAC (admin) ---
  listDepartments: () => request<string[]>("/departments"),
  setUserAttributes: (userId: string, attributes: Record<string, string>) =>
    request<User>(`/users/${userId}/attributes`, {
      method: "PUT",
      body: JSON.stringify({ attributes }),
    }),

  // --- enablement (current user) ---
  getEnablements: () => request<Enablements>("/me/enablements"),
  setEnablements: (e: Enablements) =>
    request<Enablements>("/me/enablements", {
      method: "PUT",
      body: JSON.stringify(e),
    }),

  // --- execution ---
  execute: (req: ExecuteRequest) =>
    request<ExecuteResponse>("/execute", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  // --- custom agents（Agent + MCP の組み合わせ）---
  listCustomAgents: () => request<CustomAgent[]>("/me/custom-agents"),
  createCustomAgent: (c: CustomAgentCreate) =>
    request<CustomAgent>("/me/custom-agents", {
      method: "POST",
      body: JSON.stringify(c),
    }),
  deleteCustomAgent: (id: string) =>
    request<void>(`/me/custom-agents/${id}`, { method: "DELETE" }),
  runCustomAgent: (id: string, input: string) =>
    request<ExecuteResponse>(`/me/custom-agents/${id}/run`, {
      method: "POST",
      body: JSON.stringify({ agent_ids: [], mcp_server_ids: [], input }),
    }),
};
