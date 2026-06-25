import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { getAppToken, setAppToken } from "./api/client";
import { useUser } from "./context/UserContext";
import RegistryPage from "./pages/RegistryPage";
import AdminRbacPage from "./pages/AdminRbacPage";
import MyToolsPage from "./pages/MyToolsPage";
import ExecutePage from "./pages/ExecutePage";
import CustomAgentsPage from "./pages/CustomAgentsPage";

export default function App() {
  const { user, users, loading, switchUser, isAdmin } = useUser();

  if (loading) return <div className="content">読み込み中…</div>;
  if (!user) return <div className="content">ユーザが見つかりません。Backend を起動してください。</div>;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>AI Platform</h1>
        <nav>
          <NavLink to="/registry">レジストリ</NavLink>
          <NavLink to="/my-tools">マイツール</NavLink>
          <NavLink to="/custom-agents">カスタムAgent</NavLink>
          <NavLink to="/execute">実行</NavLink>
          {isAdmin && <NavLink to="/admin">RBAC 管理</NavLink>}
        </nav>
        <div className="user-switch">
          <div className="muted">現在のユーザ（簡易ログイン）</div>
          <select
            value={user.id}
            onChange={(e) => void switchUser(e.target.value)}
          >
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
                {u.attributes?.department ? ` / ${u.attributes.department}` : ""} ({u.role})
              </option>
            ))}
          </select>
          {getAppToken() && (
            <button
              className="logout"
              onClick={() => {
                setAppToken(null);
                window.location.reload();
              }}
            >
              ログアウト
            </button>
          )}
        </div>
      </aside>

      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/registry" replace />} />
          <Route path="/registry" element={<RegistryPage />} />
          <Route path="/my-tools" element={<MyToolsPage />} />
          <Route path="/custom-agents" element={<CustomAgentsPage />} />
          <Route path="/execute" element={<ExecutePage />} />
          <Route
            path="/admin"
            element={isAdmin ? <AdminRbacPage /> : <Navigate to="/registry" replace />}
          />
        </Routes>
      </main>
    </div>
  );
}
