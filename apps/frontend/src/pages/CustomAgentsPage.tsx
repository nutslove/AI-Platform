import { useEffect, useState } from "react";
import type {
  Agent,
  CustomAgent,
  Enablements,
  ExecuteResponse,
  McpServer,
} from "../types";
import { api } from "../api/client";

// Agent と MCP サーバを組み合わせて独自 Agent を作る画面。
// 組み合わせに使えるのは「有効化済み」のツールのみ。
export default function CustomAgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [servers, setServers] = useState<McpServer[]>([]);
  const [enab, setEnab] = useState<Enablements>({
    enabled_agent_ids: [],
    enabled_mcp_server_ids: [],
  });
  const [customs, setCustoms] = useState<CustomAgent[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 作成フォーム
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selAgents, setSelAgents] = useState<string[]>([]);
  const [selServers, setSelServers] = useState<string[]>([]);

  // 実行
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, ExecuteResponse>>({});
  const [runningId, setRunningId] = useState<string | null>(null);

  async function reload() {
    try {
      const [a, s, e, c] = await Promise.all([
        api.listAgents(),
        api.listMcpServers(),
        api.getEnablements(),
        api.listCustomAgents(),
      ]);
      setAgents(a);
      setServers(s);
      setEnab(e);
      setCustoms(c);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const enabledAgents = agents.filter((a) => enab.enabled_agent_ids.includes(a.id));
  const enabledServers = servers.filter((m) =>
    enab.enabled_mcp_server_ids.includes(m.id),
  );

  function toggle(setter: React.Dispatch<React.SetStateAction<string[]>>, id: string) {
    setter((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function create() {
    setError(null);
    if (!name || selAgents.length === 0) {
      setError("名前と Agent（1つ以上）が必要です");
      return;
    }
    try {
      await api.createCustomAgent({
        name,
        description,
        agent_ids: selAgents,
        mcp_server_ids: selServers,
      });
      setName("");
      setDescription("");
      setSelAgents([]);
      setSelServers([]);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  }

  async function run(custom: CustomAgent) {
    setRunningId(custom.id);
    setError(null);
    try {
      const res = await api.runCustomAgent(custom.id, inputs[custom.id] ?? "");
      setResults((r) => ({ ...r, [custom.id]: res }));
    } catch (e) {
      setError(String(e));
    } finally {
      setRunningId(null);
    }
  }

  const nameById = (id: string) =>
    agents.find((a) => a.id === id)?.name ??
    servers.find((m) => m.id === id)?.name ??
    id;

  return (
    <div>
      <h2>カスタム Agent</h2>
      <p className="muted">
        有効化済みの Agent と MCP サーバを組み合わせて独自の Agent を作成・実行します。
      </p>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h3>新規作成</h3>
        <input
          placeholder="名前"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          placeholder="説明"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          style={{ marginTop: 6, width: "100%" }}
        />
        <div className="grid-2" style={{ marginTop: 8 }}>
          <section>
            <h3>Agents</h3>
            {enabledAgents.map((a) => (
              <label className="check" key={a.id}>
                <input
                  type="checkbox"
                  checked={selAgents.includes(a.id)}
                  onChange={() => toggle(setSelAgents, a.id)}
                />
                {a.name}
              </label>
            ))}
            {enabledAgents.length === 0 && (
              <p className="muted">有効化済みの Agent がありません（マイツールで有効化）</p>
            )}
          </section>
          <section>
            <h3>MCP サーバ</h3>
            {enabledServers.map((m) => (
              <label className="check" key={m.id}>
                <input
                  type="checkbox"
                  checked={selServers.includes(m.id)}
                  onChange={() => toggle(setSelServers, m.id)}
                />
                {m.name}
              </label>
            ))}
            {enabledServers.length === 0 && (
              <p className="muted">有効化済みの MCP サーバがありません</p>
            )}
          </section>
        </div>
        <button className="primary" style={{ marginTop: 8 }} onClick={create}>
          作成
        </button>
      </div>

      <h3>マイ カスタム Agent</h3>
      {customs.length === 0 && <p className="muted">まだありません</p>}
      {customs.map((c) => (
        <div className="card" key={c.id}>
          <h3>{c.name}</h3>
          <div className="muted">{c.description}</div>
          <div style={{ margin: "6px 0" }}>
            {c.agent_ids.map((id) => (
              <span className="badge" key={id}>
                A: {nameById(id)}
              </span>
            ))}
            {c.mcp_server_ids.map((id) => (
              <span className="badge" key={id}>
                MCP: {nameById(id)}
              </span>
            ))}
          </div>
          <textarea
            rows={2}
            style={{ width: "100%" }}
            placeholder="入力…"
            value={inputs[c.id] ?? ""}
            onChange={(e) => setInputs((p) => ({ ...p, [c.id]: e.target.value }))}
          />
          <div style={{ marginTop: 6 }}>
            <button
              className="primary"
              disabled={runningId === c.id}
              onClick={() => run(c)}
            >
              {runningId === c.id ? "実行中…" : "実行"}
            </button>
            <button
              style={{ marginLeft: 8 }}
              onClick={() => api.deleteCustomAgent(c.id).then(reload)}
            >
              削除
            </button>
          </div>
          {results[c.id] && (
            <div style={{ marginTop: 8 }}>
              <div className="muted">status: {results[c.id].status}</div>
              <pre className="trace">
                {results[c.id].steps
                  .map((s) => `[${s.source}] ${s.detail}`)
                  .join("\n")}
              </pre>
              <p>{results[c.id].output}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
