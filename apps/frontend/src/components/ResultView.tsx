import type { ExecuteResponse } from "../types";
import Markdown from "./Markdown";

// 実行結果の表示。処理ログ（ステップ）は折りたたみ、出力は Markdown 描画。
const STATUS_LABEL: Record<string, string> = {
  running: "実行中…",
  completed: "完了",
  error: "エラー",
};

export default function ResultView({ result }: { result: ExecuteResponse }) {
  return (
    <div>
      <div className="muted" style={{ marginBottom: 6 }}>
        {STATUS_LABEL[result.status] ?? result.status}
      </div>
      <details className="trace-details">
        <summary>処理ログ（{result.steps.length} ステップ・クリックで展開）</summary>
        <pre className="trace">
          {result.steps.map((s) => `[${s.source}] ${s.detail}`).join("\n")}
        </pre>
      </details>
      <div className="result-output">
        <Markdown>{result.output}</Markdown>
      </div>
    </div>
  );
}
