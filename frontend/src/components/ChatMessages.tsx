import { useEffect, useRef } from "react";
import type { Message } from "../types";
import MessageBubble from "./MessageBubble";

interface ChatMessagesProps {
  messages: Message[];
  streamingMessage?: Message | null;
  isStreaming: boolean;
}

export default function ChatMessages({
  messages,
  streamingMessage,
  isStreaming,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingMessage]);

  const allMessages = streamingMessage
    ? [...messages, streamingMessage]
    : messages;

  if (allMessages.length === 0) {
    return (
      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center overflow-y-auto scrollbar-thin"
      >
        <div className="text-center max-w-md px-6">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-blue-50 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 3v-3z"
              />
            </svg>
          </div>
          <h2 className="text-lg font-medium text-gray-700 mb-2">
            知识问答系统
          </h2>
          <p className="text-sm text-gray-400">
            在下方输入框中提问，系统将从您的知识库中检索相关内容并生成回答
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto scrollbar-thin px-4 py-6"
    >
      <div className="max-w-3xl mx-auto space-y-6">
        {allMessages.map((msg, i) => (
          <MessageBubble
            key={msg.id || i}
            message={msg}
            streaming={isStreaming && i === allMessages.length - 1 && msg.role === "assistant"}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
