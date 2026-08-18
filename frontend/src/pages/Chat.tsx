import { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "../components/Sidebar";
import ChatMessages from "../components/ChatMessages";
import ChatInput from "../components/ChatInput";
import DocumentManager from "../components/DocumentManager";
import { useAuth } from "../contexts/AuthContext";
import {
  fetchConversations,
  fetchConversation,
  streamChat,
} from "../api/chat";
import type { Conversation, Message, Citation } from "../types";

function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export default function Chat() {
  const { user, logout } = useAuth();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConvId, setCurrentConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const isAdmin = user?.role === "admin";
  const [showDocuments, setShowDocuments] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loadingConv, setLoadingConv] = useState(false);

  const abortRef = useRef<boolean>(false);
  const citationsRef = useRef<Citation[]>([]);

  // Load conversation list
  const loadConversations = useCallback(async () => {
    try {
      const resp = await fetchConversations();
      setConversations(resp.conversations);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const streamingMessage: Message | null =
    isStreaming
      ? {
          id: "streaming",
          role: "assistant",
          content: streamingContent,
          citations: streamingCitations,
          created_at: new Date().toISOString(),
        }
      : null;

  const handleNewChat = () => {
    if (isStreaming) {
      abortRef.current = true;
    }
    setCurrentConvId(null);
    setMessages([]);
    setStreamingContent("");
    setStreamingCitations([]);
    citationsRef.current = [];
    setSidebarOpen(false);
  };

  const handleSelectConversation = async (convId: string) => {
    if (isStreaming) {
      abortRef.current = true;
    }
    setCurrentConvId(convId);
    setMessages([]);
    setStreamingContent("");
    setStreamingCitations([]);
    citationsRef.current = [];
    setSidebarOpen(false);
    setLoadingConv(true);
    try {
      const detail = await fetchConversation(convId);
      setMessages(detail.messages || []);
    } catch {
      // silent
    } finally {
      setLoadingConv(false);
    }
  };

  const handleSend = async (text: string) => {
    if (isStreaming) return;

    const userMsg: Message = {
      id: genId(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setStreamingContent("");
    setStreamingCitations([]);
    citationsRef.current = [];
    setIsStreaming(true);
    abortRef.current = false;

    await streamChat(
      text,
      currentConvId,
      5,
      {
        onCitations: (citations) => {
          citationsRef.current = citations;
          setStreamingCitations(citations);
        },
        onToken: (content) => {
          setStreamingContent((prev) => prev + content);
        },
        onDone: (convId, answer) => {
          const assistantMsg: Message = {
            id: genId(),
            role: "assistant",
            content: answer,
            citations: citationsRef.current.length > 0 ? [...citationsRef.current] : undefined,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
          setStreamingContent("");
          setStreamingCitations([]);
          setIsStreaming(false);

          if (convId && convId !== currentConvId) {
            setCurrentConvId(convId);
          }
          // refresh conversation list to pick up new title
          loadConversations();
        },
        onError: (error) => {
          const errorMsg: Message = {
            id: genId(),
            role: "assistant",
            content: `请求出错: ${error.message}`,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, errorMsg]);
          setStreamingContent("");
          setStreamingCitations([]);
          setIsStreaming(false);
        },
      }
    );
  };

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        currentConvId={currentConvId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onToggleDocuments={() => setShowDocuments(true)}
        onLogout={logout}
        user={user}
        mobileOpen={sidebarOpen}
        onCloseMobile={() => setSidebarOpen(false)}
      />

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-200">
          <button
            onClick={() => setSidebarOpen(true)}
            className="md:hidden w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 hover:bg-gray-100"
            aria-label="菜单"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="text-sm font-medium text-gray-600 truncate">
            {currentConvId
              ? conversations.find((c) => c.conv_id === currentConvId)?.title || "对话"
              : "新对话"}
          </div>
        </div>

        {/* Messages */}
        {loadingConv ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-sm text-gray-400">加载对话中...</div>
          </div>
        ) : (
          <ChatMessages
            messages={messages}
            streamingMessage={streamingMessage}
            isStreaming={isStreaming}
          />
        )}

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>

      {/* Document Manager Modal - admin only */}
      {showDocuments && isAdmin && (
        <DocumentManager
          onClose={() => {
            setShowDocuments(false);
            loadConversations();
          }}
        />
      )}
    </div>
  );
}
