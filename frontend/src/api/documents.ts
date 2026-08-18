import client from "./client";
import type {
  DocumentListResponse,
  Stats,
  DocumentItem,
} from "../types";

export async function fetchDocuments(
  page = 1,
  pageSize = 50
): Promise<DocumentListResponse> {
  const resp = await client.get<DocumentListResponse>("/documents", {
    params: { page, page_size: pageSize },
  });
  return resp.data;
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await client.post<DocumentItem>("/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return resp.data;
}

export async function deleteDocument(docId: string): Promise<void> {
  await client.delete(`/documents/${docId}`);
}

export async function fetchStats(): Promise<Stats> {
  const resp = await client.get<Stats>("/stats");
  return resp.data;
}
