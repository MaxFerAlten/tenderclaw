import { Copy } from "lucide-react";
import { CodeBlock } from "../shared/CodeBlock";

interface HistoryMessage {
  role: string;
  content: string | unknown[];
  message_id?: string;
  timestamp?: string;
}

interface Props {
  message: HistoryMessage;
  onCopy: () => void;
}

type Block = Record<string, unknown>;

export function HistoryMessageBubble({ message, onCopy }: Props) {
  const role = visualRole(message);
  const isUser = role === "user";
  const isTool = role === "tool";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} group`}>
      <article
        className={`max-w-[86%] rounded-xl border px-4 py-3 ${
          isUser
            ? "border-violet-500/30 bg-violet-600 text-white"
            : isTool
              ? "border-amber-700/50 bg-amber-950/20 text-zinc-200"
              : "border-zinc-800 bg-zinc-900 text-zinc-100"
        }`}
      >
        <div className="mb-2 flex items-center gap-2 text-xs">
          <span className={roleClass(role)}>{roleLabel(role)}</span>
          {message.timestamp && <span className="text-zinc-500">{new Date(message.timestamp).toLocaleTimeString()}</span>}
          <button
            onClick={onCopy}
            className="ml-auto rounded p-1 opacity-0 transition-opacity hover:bg-black/20 group-hover:opacity-100"
            title="Copy"
          >
            <Copy className="h-3 w-3 text-zinc-400" />
          </button>
        </div>
        <div className="space-y-3">{renderContent(message.content)}</div>
      </article>
    </div>
  );
}

export function historyMessageText(message: HistoryMessage): string {
  if (typeof message.content === "string") return message.content;
  return message.content.map((block) => blockText(block)).filter(Boolean).join("\n\n");
}

function renderContent(content: string | unknown[]) {
  if (typeof content === "string") return <TextContent text={content} />;
  return content.map((block, index) => renderBlock(block, index));
}

function renderBlock(block: unknown, index: number) {
  if (!isBlock(block)) return <JsonBlock key={index} value={block} />;
  if (block.type === "text") return <TextContent key={index} text={textValue(block.text)} />;
  if (block.type === "image") return <ImageContent key={index} block={block} />;
  if (block.type === "tool_use") return <ToolBlock key={index} block={block} kind="use" />;
  if (block.type === "tool_result") return <ToolBlock key={index} block={block} kind="result" />;
  if (block.type === "thinking") return <ToolBlock key={index} block={block} kind="thinking" />;
  return <JsonBlock key={index} value={block} />;
}

function TextContent({ text }: { text: string }) {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return (
    <>
      {parts.map((part, index) => {
        if (!part) return null;
        if (!part.startsWith("```")) {
          return <div key={index} className="whitespace-pre-wrap break-words text-sm leading-relaxed">{part}</div>;
        }
        const lines = part.slice(3, -3).split("\n");
        return <CodeBlock key={index} code={lines.slice(1).join("\n")} language={lines[0]?.trim()} />;
      })}
    </>
  );
}

function ImageContent({ block }: { block: Block }) {
  const source = textValue(block.source);
  const caption = [textValue(block.name), textValue(block.mime_type), formatBytes(block.size_bytes)].filter(Boolean).join(" - ");
  return (
    <figure className="overflow-hidden rounded-lg border border-white/15 bg-black/20">
      <img src={source} alt={textValue(block.name) || "Attached image"} className="max-h-96 w-full object-contain" />
      {caption && (
        <figcaption className="border-t border-white/10 px-3 py-2 text-xs text-zinc-400">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}

function ToolBlock({ block, kind }: { block: Block; kind: "use" | "result" | "thinking" }) {
  const title = kind === "use" ? `Tool: ${textValue(block.name) || "tool"}` : kind === "thinking" ? "Thinking" : "Tool result";
  const body = kind === "use" ? JSON.stringify(block.input ?? {}, null, 2) : textValue(block.content ?? block.thinking);
  return (
    <details className="rounded-lg border border-zinc-700 bg-zinc-950/50 text-xs">
      <summary className="cursor-pointer px-3 py-2 font-mono text-zinc-300">{title}</summary>
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words px-3 pb-3 text-zinc-400">{body || "No output"}</pre>
    </details>
  );
}

function JsonBlock({ value }: { value: unknown }) {
  return <CodeBlock code={JSON.stringify(value, null, 2)} language="json" />;
}

function visualRole(message: HistoryMessage): string {
  if (Array.isArray(message.content) && message.content.every((block) => isBlock(block) && block.type === "tool_result")) {
    return "tool";
  }
  return message.role || "assistant";
}

function roleLabel(role: string): string {
  if (role === "user") return "You";
  if (role === "assistant") return "TenderClaw";
  if (role === "tool") return "Tool";
  return role;
}

function roleClass(role: string): string {
  if (role === "user") return "rounded bg-blue-500/20 px-2 py-0.5 font-medium text-blue-200";
  if (role === "tool") return "rounded bg-amber-500/20 px-2 py-0.5 font-medium text-amber-300";
  return "rounded bg-emerald-500/20 px-2 py-0.5 font-medium text-emerald-300";
}

function blockText(block: unknown): string {
  if (!isBlock(block)) return textValue(block);
  if (block.type === "text") return textValue(block.text);
  if (block.type === "tool_result") return textValue(block.content);
  if (block.type === "tool_use") return `${textValue(block.name)} ${JSON.stringify(block.input ?? {})}`.trim();
  if (block.type === "image") return textValue(block.name) || textValue(block.mime_type) || "image";
  return JSON.stringify(block);
}

function isBlock(value: unknown): value is Block {
  return Boolean(value) && typeof value === "object";
}

function textValue(value: unknown): string {
  return value == null ? "" : String(value);
}

function formatBytes(value: unknown): string {
  return typeof value === "number" && value > 0 ? `${Math.round(value / 1024)} KB` : "";
}
