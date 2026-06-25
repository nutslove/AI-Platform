import { useEffect, useState, type ReactNode } from "react";
import { api, getAppToken, setAppToken } from "../api/client";

type Status = "loading" | "login" | "ok";

// .env の共通パスワードによる簡易ログインゲート。
// APP_PASSWORD が未設定（login_required=false）ならそのまま通す。
export default function AuthGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await api.authConfig();
        if (!cfg.login_required) {
          setStatus("ok");
          return;
        }
        // 保存済みトークンがあれば検証
        if (getAppToken()) {
          try {
            await api.authVerify();
            setStatus("ok");
            return;
          } catch {
            setAppToken(null);
          }
        }
        setStatus("login");
      } catch {
        // 設定取得に失敗してもアプリは表示（バックエンド未起動時など）
        setStatus("ok");
      }
    })();
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { token } = await api.login(password);
      setAppToken(token);
      setStatus("ok");
    } catch {
      setError("パスワードが違います");
    } finally {
      setSubmitting(false);
    }
  }

  if (status === "loading") {
    return <div className="content">読み込み中…</div>;
  }

  if (status === "login") {
    return (
      <div className="login-screen">
        <form className="login-card" onSubmit={submit}>
          <h1>AI Platform</h1>
          <p className="muted">続けるにはパスワードを入力してください。</p>
          <input
            type="password"
            autoFocus
            placeholder="パスワード"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <p className="error">{error}</p>}
          <button className="primary" type="submit" disabled={submitting}>
            {submitting ? "確認中…" : "ログイン"}
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
