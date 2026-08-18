import ReactMarkdown from "react-markdown";
import type { Message } from "../types";
import CitationCard from "./CitationCard";

interface MessageBubbleProps {
  message: Message;
  streaming?: boolean;
}

function formatTime(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export default function MessageBubble({
  message,
  streaming = false,
}: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* Avatar */}
      <div className="flex-shrink-0">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
            isUser
              ? "bg-blue-600 text-white"
              : "bg-gray-200 text-gray-600"
          }`}
        >
          {isUser ? "我" : "AI"}
        </div>
      </div>

      {/* Content */}
      <div className={`flex flex-col max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-gray-400">
            {isUser ? "用户" : "助手"}
          </span>
          {message.created_at && (
            <span className="text-xs text-gray-300">
              {formatTime(message.created_at)}
            </span>
          )}
        </div>

        <div
          className={`px-4 py-2.5 ${
            isUser ? "chat-bubble-user" : "chat-bubble-assistant"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown>{message.content || (streaming ? "..." : "")}</ReactMarkdown>
              {streaming && (
                <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-0.5 align-middle" />
              )}
            </div>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-2 w-full space-y-2">
            <div className="text-xs text-gray-400 font-medium">
              参考来源 ({message.citations.length})
            </div>
            {message.citations.map((c, i) => (
              <CitationCard key={c.chunk_id || i} citation={c} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
