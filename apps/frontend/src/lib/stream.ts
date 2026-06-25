import type { ExecuteResponse } from "../types";

export function emptyResult(): ExecuteResponse {
  return { status: "running", steps: [], output: "" };
}

// SSE イベントを実行結果に反映する。
export function applyEvent(
  prev: ExecuteResponse,
  ev: Record<string, unknown>,
): ExecuteResponse {
  switch (ev.type) {
    case "step":
      return {
        ...prev,
        steps: [...prev.steps, { source: String(ev.source), detail: String(ev.detail) }],
      };
    case "agent_start":
      // 複数 Agent 連鎖時は、現在の Agent の出力に切り替える
      return { ...prev, output: "" };
    case "token":
      return { ...prev, output: prev.output + String(ev.text ?? "") };
    case "done":
      return {
        ...prev,
        status: String(ev.status),
        output: String(ev.output ?? prev.output),
      };
    default:
      return prev;
  }
}
