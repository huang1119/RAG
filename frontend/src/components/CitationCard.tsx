import { useState } from "react";
import type { Citation } from "../types";

interface CitationCardProps {
  citation: Citation;
  index: number;
}

const statusColors: Record<string, string> = {
  high: "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-gray-100 text-gray-500",
};

function scoreLabel(score: number): string {
  if (score >= 0.8) return "high";
  if (score >= 0.5) return "medium";
  return "low";
}

function scoreText(score: number): string {
  return (score * 100).toFixed(1) + "%";
}

export default function CitationCard({ citation, index }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const toggle = () => {
    setExpanded(!expanded);
  };

  const label = scoreLabel(citation.score);
  const isWeb = citation.source_type === "web";

  return (
    <div
      className="border border-gray-200 rounded-lg bg-white hover:border-gray-300 transition-colors"
      style={{ cursor: "pointer" }}
      onClick={toggle}
    >
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 text-gray-600 text-xs flex items-center justify-center font-medium">
            {index + 1}
          </span>
          {isWeb ? (
            <svg
              className="w-4 h-4 text-blue-500 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c2.5-2.7 4-6.3 4-9s-1.5-6.3-4-9m0 18c-2.5-2.7-4-6.3-4-9s1.5-6.3 4-9"
              />
            </svg>
          ) : (
            <svg
              className="w-4 h-4 text-gray-400 flex-shrink-0"
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
          )}
          <span className="text-sm text-gray-700 truncate font-medium">
            {citation.file_name}
          </span>
          {isWeb ? (
            <span className="flex-shrink-0 text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-600">
              网络
            </span>
          ) : (
            <span className="flex-shrink-0 text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
              知识库
            </span>
          )}
          {citation.page_num > 0 && (
            <span className="flex-shrink-0 text-xs text-gray-400">
              第 {citation.page_num} 页
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span
            className={`text-xs px-1.5 py-0.5 rounded ${statusColors[label]}`}
          >
            {scoreText(citation.score)}
          </span>
          <svg
            className="w-4 h-4 text-gray-400 transition-transform"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            style={{ transform: expanded ? "rotate(180deg)" : "none" }}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </div>
      {citation.section_title && (
        <div className="px-3 pb-1 text-xs text-gray-400">
          {citation.section_title}
        </div>
      )}
      <div
        className="px-3 pb-3 pt-1 text-sm text-gray-500 leading-relaxed"
        style={{ display: expanded ? "block" : "none" }}
      >
        {citation.content}
        {isWeb && citation.url && (
          <a
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-2 text-xs text-blue-500 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {citation.url}
          </a>
        )}
      </div>
    </div>
  );
}
