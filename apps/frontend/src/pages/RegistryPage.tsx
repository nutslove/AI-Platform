import { useEffect, useState } from "react";
import type { Agent, McpServer } from "../types";
import { api } from "../api/client";
import { useUser } from "../context/UserContext";

export default function RegistryPage() {
  const { isAdmin } = useUser();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [servers, setServers] = useState<McpServer[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    try {
      const [a, s] = await Promise.all([api.listAgents(), api.listMcpServers()]);
      setAgents(a);
      setServers(s);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  return (
    <div>
      <h2>レジストリ</h2>
      <p className="muted">
        {isAdmin
          ? "登録されているすべての Agent / MCPサーバ。ADMIN は登録・削除できます。"
          : "あなたが利用を許可されている Agent / MCPサーバの一覧です。"}
      </p>
      {error && <p className="error">{error}</p>}

      <div className="grid-2">
        <section>
          <h3>Agents（A2A）</h3>
          {isAdmin && (
            <AgentForm onCreated={reload} />
          )}
          {agents.map((a) => (
            <div className={"card" + (a.allowed ? "" : " disabled")} key={a.id}>
              <h3>
                {a.name}
                {!a.allowed && <span className="badge badge-off">利用不可</span>}
              </h3>
              <div className="muted">{a.description}</div>
              <div className="muted">A2A: {a.a2a_url}</div>
              <div style={{ marginTop: 6 }}>
                {a.skills.map((s) => (
                  <span className="badge" key={s}>{s}</span>
                ))}
              </div>
              {isAdmin && (
                <button
                  style={{ marginTop: 8 }}
                  onClick={() => api.deleteAgent(a.id).then(reload)}
                >
                  削除
                </button>
              )}
            </div>
          ))}
          {agents.length === 0 && <p className="muted">登録なし</p>}
        </section>

        <section>
          <h3>MCP サーバ</h3>
          {isAdmin && <McpForm onCreated={reload} />}
          {servers.map((m) => (
            <div className={"card" + (m.allowed ? "" : " disabled")} key={m.id}>
              <h3>
                {m.name}
                {!m.allowed && <span className="badge badge-off">利用不可</span>}
              </h3>
              <div className="muted">{m.description}</div>
              <div className="muted">
                <span className="badge">{m.transport}</span> {m.url}
              </div>
              {isAdmin && (
                <button
                  style={{ marginTop: 8 }}
                  onClick={() => api.deleteMcpServer(m.id).then(reload)}
                >
                  削除
                </button>
              )}
            </div>
          ))}
          {servers.length === 0 && <p className="muted">登録なし</p>}
        </section>
      </div>
    </div>
  );
}

function AgentForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [a2aUrl, setA2aUrl] = useState("");
  const [skills, setSkills] = useState("");

  async function submit() {
    if (!name) return;
    await api.createAgent({
      name,
      description,
      a2a_url: a2aUrl,
      skills: skills.split(",").map((s) => s.trim()).filter(Boolean),
    });
    setName(""); setDescription(""); setA2aUrl(""); setSkills("");
    onCreated();
  }

  return (
    <div className="card">
      <h3>Agent を登録</h3>
      <input placeholder="名前" value={name} onChange={(e) => setName(e.target.value)} />
      <input placeholder="説明" value={description} onChange={(e) => setDescription(e.target.value)} style={{ marginTop: 6, width: "100%" }} />
      <input placeholder="A2A URL" value={a2aUrl} onChange={(e) => setA2aUrl(e.target.value)} style={{ marginTop: 6, width: "100%" }} />
      <input placeholder="スキル（カンマ区切り）" value={skills} onChange={(e) => setSkills(e.target.value)} style={{ marginTop: 6, width: "100%" }} />
      <button className="primary" style={{ marginTop: 8 }} onClick={submit}>登録</button>
    </div>
  );
}

function McpForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [transport, setTransport] = useState<"http" | "stdio">("http");
  const [url, setUrl] = useState("");

  async function submit() {
    if (!name) return;
    await api.createMcpServer({ name, description, transport, url });
    setName(""); setDescription(""); setUrl("");
    onCreated();
  }

  return (
    <div className="card">
      <h3>MCP サーバを登録</h3>
      <input placeholder="名前" value={name} onChange={(e) => setName(e.target.value)} />
      <input placeholder="説明" value={description} onChange={(e) => setDescription(e.target.value)} style={{ marginTop: 6, width: "100%" }} />
      <select value={transport} onChange={(e) => setTransport(e.target.value as "http" | "stdio")} style={{ marginTop: 6 }}>
        <option value="http">http</option>
        <option value="stdio">stdio</option>
      </select>
      <input placeholder="URL / コマンド" value={url} onChange={(e) => setUrl(e.target.value)} style={{ marginTop: 6, width: "100%" }} />
      <button className="primary" style={{ marginTop: 8 }} onClick={submit}>登録</button>
    </div>
  );
}
