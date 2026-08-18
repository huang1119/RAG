import { useState, useEffect, useRef, useCallback, type DragEvent } from "react";
import type { DocumentItem, Stats, DocumentStatus } from "../types";
import {
  fetchDocuments,
  uploadDocument,
  deleteDocument,
  fetchStats,
} from "../api/documents";

interface DocumentManagerProps {
  onClose: () => void;
}

const statusConfig: Record<
  DocumentStatus,
  { label: string; className: string }
> = {
  pending: { label: "等待中", className: "bg-gray-100 text-gray-600" },
  processing: { label: "处理中", className: "bg-blue-100 text-blue-600" },
  ready: { label: "就绪", className: "bg-green-100 text-green-600" },
  failed: { label: "失败", className: "bg-red-100 text-red-600" },
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export default function DocumentManager({ onClose }: DocumentManagerProps) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [docsResp, statsResp] = await Promise.all([
        fetchDocuments(),
        fetchStats(),
      ]);
      setDocuments(docsResp.documents);
      setStats(statsResp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(file);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    handleUpload(files[0]);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleUpload(files[0]);
    }
  };

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
      const statsResp = await fetchStats();
      setStats(statsResp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-800">文档管理</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 transition-colors"
            aria-label="关闭"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-4 gap-3 px-5 py-4 border-b border-gray-100">
            <div className="text-center">
              <div className="text-xl font-semibold text-gray-700">{stats.document_count}</div>
              <div className="text-xs text-gray-400 mt-0.5">文档总数</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-gray-700">{stats.chunk_count}</div>
              <div className="text-xs text-gray-400 mt-0.5">分块数量</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-green-600">{stats.ready_count}</div>
              <div className="text-xs text-gray-400 mt-0.5">就绪</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-semibold text-gray-700">{stats.total_size_mb.toFixed(1)}</div>
              <div className="text-xs text-gray-400 mt-0.5">总大小 (MB)</div>
            </div>
          </div>
        )}

        {/* Upload area */}
        <div className="px-5 py-3">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg px-4 py-6 text-center cursor-pointer transition-colors ${
              dragOver
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400"
            }`}
          >
            <svg className="w-8 h-8 mx-auto mb-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <div className="text-sm text-gray-500">
              {uploading ? "上传中..." : "点击或拖拽文件到此处上传"}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              支持 PDF, DOCX, TXT, MD 等格式
            </div>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={(e) => handleFileSelect(e.target.files)}
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="px-5 pb-2">
            <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>
          </div>
        )}

        {/* Document list */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-5 pb-4">
          {loading ? (
            <div className="text-center text-sm text-gray-400 py-8">加载中...</div>
          ) : documents.length === 0 ? (
            <div className="text-center text-sm text-gray-400 py-8">暂无文档</div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => {
                const sc = statusConfig[doc.status] || statusConfig.pending;
                return (
                  <div
                    key={doc.doc_id}
                    className="flex items-center gap-3 border border-gray-200 rounded-lg px-3 py-2.5 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex-shrink-0 w-9 h-9 rounded bg-gray-100 flex items-center justify-center">
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-700 truncate">
                        {doc.file_name}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {formatFileSize(doc.file_size)} | {formatDate(doc.created_at)}
                      </div>
                    </div>
                    <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded ${sc.className}`}>
                      {sc.label}
                    </span>
                    <button
                      onClick={() => handleDelete(doc.doc_id)}
                      className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                      aria-label="删除"
                      title="删除"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
