import { useEffect, useState } from "react";
import type { AccessPolicy, Agent, McpServer, User } from "../types";
import { api } from "../api/client";

// 属性ベースアクセス制御（ABAC）の管理画面。
// ① 各ユーザの部署（属性）を設定
// ② 各 Agent / MCP サーバを「どの部署が使えるか」で設定
export default function AdminRbacPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [servers, setServers] = useState<McpServer[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    try {
      const [u, a, s, d] = await Promise.all([
        api.listUsers(),
        api.listAgents(),
        api.listMcpServers(),
        api.listDepartments(),
      ]);
      setUsers(u);
      setAgents(a);
      setServers(s);
      setDepartments(d);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  function flash(text: string) {
    setMsg(text);
    setTimeout(() => setMsg(null), 1500);
  }

  async function changeDept(user: User, dept: string) {
    try {
      await api.setUserAttributes(user.id, { ...user.attributes, department: dept });
      await reload();
      flash(`${user.username} の部署を更新しました`);
    } catch (e) {
      setError(String(e));
    }
  }

  // リソースの許可部署を 1 つトグルして保存（department 属性で制御）
  async function toggleAccess(
    kind: "agent" | "mcp",
    id: string,
    current: string[],
    dept: string,
  ) {
    const set = new Set(current);
    if (set.has(dept)) set.delete(dept);
    else set.add(dept);
    const depts = [...set];
    // 空なら「全員可」= access を空に
    const access: AccessPolicy = depts.length ? { department: depts } : {};
    try {
      if (kind === "agent") await api.setAgentAccess(id, access);
      else await api.setMcpAccess(id, access);
      await reload();
    } catch (e) {
      setError(String(e));
    }
  }

  const deptsOf = (access: Record<string, string[]>) => access?.department ?? [];

  return (
    <div>
      <h2>RBAC 管理（属性ベース / ABAC）</h2>
      <p className="muted">
        ユーザに部署属性を与え、各 Agent / MCP サーバを「どの部署が使えるか」で制御します。
      </p>
      {error && <p className="error">{error}</p>}
      {msg && <p className="muted">{msg}</p>}

      <section className="card">
        <h3>① ユーザの部署</h3>
        {users
          .filter((u) => u.role !== "admin")
          .map((u) => (
            <div key={u.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
              <span style={{ width: 80 }}>{u.username}</span>
              <select
                value={u.attributes?.department ?? ""}
                onChange={(e) => changeDept(u, e.target.value)}
              >
                <option value="">(未設定)</option>
                {departments.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
          ))}
      </section>

      <section className="card">
        <h3>② リソースのアクセスポリシー（利用可能な部署）</h3>
        <p className="muted">部署を1つも選ばない場合は「全員可（公開）」になります。</p>

        <h4>Agents</h4>
        {agents.map((a) => (
          <AccessRow
            key={a.id}
            name={a.name}
            depts={deptsOf(a.access)}
            departments={departments}
            onToggle={(d) => toggleAccess("agent", a.id, deptsOf(a.access), d)}
          />
        ))}

        <h4 style={{ marginTop: 12 }}>MCP サーバ</h4>
        {servers.map((m) => (
          <AccessRow
            key={m.id}
            name={m.name}
            depts={deptsOf(m.access)}
            departments={departments}
            onToggle={(d) => toggleAccess("mcp", m.id, deptsOf(m.access), d)}
          />
        ))}
      </section>
    </div>
  );
}

function AccessRow({
  name,
  depts,
  departments,
  onToggle,
}: {
  name: string;
  depts: string[];
  departments: string[];
  onToggle: (dept: string) => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "4px 0", flexWrap: "wrap" }}>
      <span style={{ width: 180 }}>{name}</span>
      {departments.map((d) => (
        <label key={d} className="check" style={{ padding: 0 }}>
          <input type="checkbox" checked={depts.includes(d)} onChange={() => onToggle(d)} />
          {d}
        </label>
      ))}
      {depts.length === 0 && <span className="badge">全員可</span>}
    </div>
  );
}
