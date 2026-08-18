import client, { getToken } from "./client";
import type {
  ConversationListResponse,
  ConversationDetail,
  SSEEvent,
  Citation,
} from "../types";

export async function fetchConversations(): Promise<ConversationListResponse> {
  const resp = await client.get<ConversationListResponse>("/conversations");
  return resp.data;
}

export async function fetchConversation(
  convId: string
): Promise<ConversationDetail> {
  const resp = await client.get<ConversationDetail>(`/conversations/${convId}`);
  return resp.data;
}

export async function deleteConversation(convId: string): Promise<void> {
  await client.delete(`/conversations/${convId}`);
}

export interface StreamCallbacks {
  onCitations: (citations: Citation[]) => void;
  onToken: (content: string) => void;
  onDone: (convId: string, answer: string) => void;
  onError: (error: Error) => void;
}

export async function streamChat(
  question: string,
  convId: string | null,
  topK: number,
  callbacks: StreamCallbacks
): Promise<void> {
  const token = getToken();
  if (!token) {
    callbacks.onError(new Error("未登录"));
    return;
  }

  try {
    const resp = await fetch("/api/v1/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        question,
        conv_id: convId || undefined,
        top_k: topK,
      }),
    });

    if (!resp.ok) {
      throw new Error(`请求失败: ${resp.status}`);
    }

    if (!resp.body) {
      throw new Error("响应体为空");
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;

        const dataStr = trimmed.slice(5).trim();
        if (!dataStr || dataStr === "[DONE]") continue;

        try {
          const event = JSON.parse(dataStr) as SSEEvent;
          switch (event.type) {
            case "citations":
              callbacks.onCitations(event.citations);
              break;
            case "token":
              callbacks.onToken(event.content);
              break;
            case "done":
              callbacks.onDone(event.conv_id, event.answer);
              break;
          }
        } catch {
          // skip malformed JSON
        }
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error(String(err)));
  }
}
