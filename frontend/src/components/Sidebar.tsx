import type { Conversation, User } from "../types";

interface SidebarProps {
  conversations: Conversation[];
  currentConvId: string | null;
  onSelectConversation: (convId: string) => void;
  onNewChat: () => void;
  onToggleDocuments: () => void;
  onLogout: () => void;
  user: User | null;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export default function Sidebar({
  conversations,
  currentConvId,
  onSelectConversation,
  onNewChat,
  onToggleDocuments,
  onLogout,
  user,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-30 md:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed md:relative z-40 w-72 h-full bg-gray-50 border-r border-gray-200 flex flex-col transition-transform duration-200 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* Logo / Title */}
        <div className="px-4 py-3.5 border-b border-gray-200">
          <h1 className="text-base font-semibold text-gray-800">
            RAG 知识问答
          </h1>
        </div>

        {/* New Chat */}
        <div className="px-3 pt-3">
          <button
            onClick={onNewChat}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            新建对话
          </button>
        </div>

        {/* Documents button - admin only */}
        {user?.role === "admin" && (
          <div className="px-3 pt-2">
            <button
              onClick={onToggleDocuments}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-100 transition-colors"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              文档管理
            </button>
          </div>
        )}

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto scrollbar-thin mt-3 px-3">
          <div className="text-xs font-medium text-gray-400 px-1 mb-1.5">
            历史对话
          </div>
          {conversations.length === 0 ? (
            <div className="text-xs text-gray-300 px-1 py-2">
              暂无对话记录
            </div>
          ) : (
            <div className="space-y-0.5">
              {conversations.map((conv) => (
                <button
                  key={conv.conv_id}
                  onClick={() => onSelectConversation(conv.conv_id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors truncate ${
                    currentConvId === conv.conv_id
                      ? "bg-blue-100 text-blue-700"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {conv.title || "新对话"}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* User info & logout */}
        <div className="border-t border-gray-200 px-3 py-3">
          <div className="flex items-center gap-2">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-300 text-gray-600 flex items-center justify-center text-sm font-medium">
              {user?.username?.charAt(0).toUpperCase() || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-medium text-gray-700 truncate">
                  {user?.username || "未登录"}
                </span>
                {user?.role === "admin" ? (
                  <span className="flex-shrink-0 px-1.5 py-0.5 text-[10px] font-medium rounded bg-blue-100 text-blue-700">
                    管理员
                  </span>
                ) : (
                  <span className="flex-shrink-0 px-1.5 py-0.5 text-[10px] font-medium rounded bg-gray-100 text-gray-500">
                    员工
                  </span>
                )}
              </div>
              {user?.email && (
                <div className="text-xs text-gray-400 truncate">
                  {user.email}
                </div>
              )}
            </div>
            <button
              onClick={onLogout}
              className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              aria-label="退出登录"
              title="退出登录"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
