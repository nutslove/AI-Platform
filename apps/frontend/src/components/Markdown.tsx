import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// エージェントの出力（Markdown）を描画する。
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
