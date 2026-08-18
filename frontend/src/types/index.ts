export interface User {
  user_id: string;
  username: string;
  email?: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
}

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface DocumentItem {
  doc_id: string;
  file_name: string;
  file_format: string;
  file_size: number;
  status: DocumentStatus;
  created_at: string;
}

export interface DocumentListResponse {
  total: number;
  documents: DocumentItem[];
}

export interface Stats {
  document_count: number;
  chunk_count: number;
  ready_count: number;
  processing_count: number;
  failed_count: number;
  total_size_mb: number;
}

export interface Chunk {
  chunk_id: string;
  doc_id: string;
  file_name: string;
  page_num: number;
  section_title: string;
  content: string;
  score: number;
}

export interface Citation {
  chunk_id: string;
  doc_id: string;
  file_name: string;
  page_num: number;
  section_title: string;
  content: string;
  score: number;
  source_type?: string;
  url?: string;
}

export interface ChatRequest {
  question: string;
  conv_id?: string;
  top_k?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  created_at: string;
}

export interface Conversation {
  conv_id: string;
  title: string;
  message_count?: number;
  last_message_at?: string;
  created_at: string;
}

export interface ConversationListResponse {
  total: number;
  conversations: Conversation[];
}

export interface ConversationDetail {
  conv_id: string;
  title: string;
  messages: Message[];
  created_at: string;
}

export type SSEEventType = "citations" | "token" | "done";

export interface SSECitationsEvent {
  type: "citations";
  citations: Citation[];
}

export interface SSETokenEvent {
  type: "token";
  content: string;
}

export interface SSEDoneEvent {
  type: "done";
  conv_id: string;
  answer: string;
}

export type SSEEvent =
  | SSECitationsEvent
  | SSETokenEvent
  | SSEDoneEvent;
