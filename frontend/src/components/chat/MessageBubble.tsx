/**
 * MessageBubble — renders a single conversation message.
 * Supports text, tool_use, and tool_result content blocks.
 */

import type { Message, ContentBlock } from "../../api/types";
import { CodeBlock } from "../shared/CodeBlock";
import { ToolUseCard } from "../tools/ToolUseCard";

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-xl px-4 py-3 ${
          isUser
            ? "bg-violet-600 text-white"
            : "bg-zinc-900 text-zinc-100 border border-zinc-800"
        }`}
      >
        {/* Role label */}
        <div
          className={`text-xs font-medium mb-1 ${
            isUser ? "text-violet-200" : "text-zinc-500"
          }`}
        >
          {isUser ? "You" : "TenderClaw"}
        </div>

        {/* Content */}
        {typeof message.content === "string" ? (
          <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
            {renderTextContent(message.content)}
          </div>
        ) : (
          renderBlocks(message.content)
        )}
      </div>
    </div>
  );
}

function renderBlocks(blocks: ContentBlock[]) {
  return blocks.map((block, i) => {
    if (block.type === "text") {
      return (
        <div key={i} className="text-sm leading-relaxed whitespace-pre-wrap break-words">
          {renderTextContent(block.text)}
        </div>
      );
    }
    if (block.type === "tool_use" || block.type === "tool_result") {
      return <ToolUseCard key={i} block={block} />;
    }
    return null;
  });
}

function renderTextContent(text: string) {
  const parts = text.split(/(```[\s\S]*?```)/g);

  return parts.map((part, i) => {
    if (part.startsWith("```")) {
      const lines = part.slice(3, -3).split("\n");
      const lang = lines[0]?.trim() || "";
      const code = lines.slice(1).join("\n");
      return <CodeBlock key={i} code={code} language={lang} />;
    }
    return <span key={i}>{part}</span>;
  });
}
