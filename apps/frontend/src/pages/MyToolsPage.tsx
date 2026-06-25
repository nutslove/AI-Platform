import { useEffect, useState } from "react";
import type { Agent, Enablements, McpServer } from "../types";
import { api } from "../api/client";

// 一般ユーザが「自分に許可された」Agent/MCPサーバの中から
// 実際に使うものを有効化する画面。
export default function MyToolsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [servers, setServers] = useState<McpServer[]>([]);
  const [enab, setEnab] = useState<Enablements>({
    enabled_agent_ids: [],
    enabled_mcp_server_ids: [],
  });
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // listAgents/listMcpServers は role に応じて「許可された集合」を返す
    Promise.all([api.listAgents(), api.listMcpServers(), api.getEnablements()])
      .then(([a, s, e]) => {
        setAgents(a);
        setServers(s);
        setEnab(e);
      })
      .catch((e) => setError(String(e)));
  }, []);

  function toggle(list: keyof Enablements, id: string) {
    setEnab((p) => {
      const set = new Set(p[list]);
      if (set.has(id)) set.delete(id);
      else set.add(id);
      return { ...p, [list]: [...set] };
    });
  }

  async function save() {
    setSavedMsg(null);
    try {
      const result = await api.setEnablements(enab);
      setEnab(result);
      setSavedMsg("有効化設定を保存しました");
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div>
      <h2>マイツール</h2>
      <p className="muted">許可されたツールの中から、実行で使うものを有効化します。</p>
      {error && <p className="error">{error}</p>}

      <div className="grid-2">
        <section className="card">
          <h3>Agents</h3>
          {agents.map((a) => (
            <label className={"check" + (a.allowed ? "" : " disabled")} key={a.id}>
              <input
                type="checkbox"
                disabled={!a.allowed}
                checked={enab.enabled_agent_ids.includes(a.id)}
                onChange={() => toggle("enabled_agent_ids", a.id)}
              />
              {a.name}
              {!a.allowed && <span className="badge badge-off">利用不可</span>}
            </label>
          ))}
          {agents.length === 0 && <p className="muted">Agent がありません</p>}
        </section>
        <section className="card">
          <h3>MCP サーバ</h3>
          {servers.map((m) => (
            <label className={"check" + (m.allowed ? "" : " disabled")} key={m.id}>
              <input
                type="checkbox"
                disabled={!m.allowed}
                checked={enab.enabled_mcp_server_ids.includes(m.id)}
                onChange={() => toggle("enabled_mcp_server_ids", m.id)}
              />
              {m.name}
              {!m.allowed && <span className="badge badge-off">利用不可</span>}
            </label>
          ))}
          {servers.length === 0 && <p className="muted">MCP サーバがありません</p>}
        </section>
      </div>

      <div style={{ marginTop: 12 }}>
        <button className="primary" onClick={save}>保存</button>
        {savedMsg && <span style={{ marginLeft: 12 }} className="muted">{savedMsg}</span>}
      </div>
    </div>
  );
}
