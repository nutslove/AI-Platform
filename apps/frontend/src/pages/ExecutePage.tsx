import { useEffect, useState } from "react";
import type { Agent, Enablements, ExecuteResponse, McpServer } from "../types";
import { api } from "../api/client";

// 有効化済みの Agent / MCPサーバを複数選んで組み合わせ、実行する画面。
export default function ExecutePage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [servers, setServers] = useState<McpServer[]>([]);
  const [enab, setEnab] = useState<Enablements>({
    enabled_agent_ids: [],
    enabled_mcp_server_ids: [],
  });
  const [selAgents, setSelAgents] = useState<string[]>([]);
  const [selServers, setSelServers] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ExecuteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listAgents(), api.listMcpServers(), api.getEnablements()])
      .then(([a, s, e]) => {
        setAgents(a);
        setServers(s);
        setEnab(e);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const enabledAgents = agents.filter((a) => enab.enabled_agent_ids.includes(a.id));
  const enabledServers = servers.filter((m) => enab.enabled_mcp_server_ids.includes(m.id));

  function toggle(setter: React.Dispatch<React.SetStateAction<string[]>>, id: string) {
    setter((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function run() {
    setError(null);
    setResult(null);
    setRunning(true);
    try {
      const res = await api.execute({
        agent_ids: selAgents,
        mcp_server_ids: selServers,
        input,
      });
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <h2>実行</h2>
      <p className="muted">有効化済みの Agent と MCPサーバを組み合わせて実行します。</p>
      {error && <p className="error">{error}</p>}

      <div className="grid-2">
        <section className="card">
          <h3>Agents を選択</h3>
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
        <section className="card">
          <h3>MCP サーバを選択</h3>
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

      <div className="card">
        <h3>入力</h3>
        <textarea
          rows={4}
          style={{ width: "100%" }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Agent への指示を入力…"
        />
        <div style={{ marginTop: 8 }}>
          <button
            className="primary"
            disabled={running || selAgents.length === 0}
            onClick={run}
          >
            {running ? "実行中…" : "実行"}
          </button>
        </div>
      </div>

      {result && (
        <div className="card">
          <h3>結果（status: {result.status}）</h3>
          <pre className="trace">
            {result.steps.map((s) => `[${s.source}] ${s.detail}`).join("\n")}
          </pre>
          <p>{result.output}</p>
        </div>
      )}
    </div>
  );
}
