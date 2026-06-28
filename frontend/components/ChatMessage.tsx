"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { UIMessage } from "@/lib/types";

interface ChatMessageProps {
  message: UIMessage;
  onRetry: (message: UIMessage) => void;
}

// Renders a single chat bubble for either the customer or the assistant.
export default function ChatMessage({ message, onRetry }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] md:max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
        {/* Speaker label */}
        <div
          className={`mb-1 text-xs font-semibold ${
            isUser ? "text-right text-brand-navy" : "text-left text-brand-azure"
          }`}
        >
          {isUser ? "Customer" : "Assistant"}
        </div>

        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-2.5 shadow-sm ${
            isUser
              ? "rounded-br-sm bg-brand-navy text-white"
              : "rounded-bl-sm border border-slate-200 bg-white text-slate-800"
          } ${message.status === "error" ? "border-red-300 bg-red-50 text-red-800" : ""}`}
        >
          {isUser ? (
            // User content is plain text; preserve line breaks.
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
              {message.content}
            </p>
          ) : (
            // Assistant content may contain markdown (lists, bold, tables).
            // react-markdown sanitises by default (no raw HTML is rendered).
            <div className="prose prose-sm max-w-none break-words prose-p:my-1 prose-ul:my-1 prose-ol:my-1">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* Assistant metadata: escalation badge + latency */}
        {!isUser && message.status === "sent" && (
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            {message.escalated && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-700">
                Escalated to human agent
              </span>
            )}
            {typeof message.latencyMs === "number" && <span>{message.latencyMs} ms</span>}
          </div>
        )}

        {/* Retrieved sources (collapsible) */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <details className="mt-1 text-xs text-slate-500">
            <summary className="cursor-pointer select-none hover:text-brand-azure">
              Sources ({message.sources.length})
            </summary>
            <ul className="mt-1 space-y-1 pl-4">
              {message.sources.map((source, idx) => (
                <li key={source.chunk_id ?? idx} className="list-disc">
                  <span className="font-medium">{source.intent_label ?? "unknown"}</span>
                  {source.category ? ` · ${source.category}` : ""}
                  {typeof source.relevance_score === "number"
                    ? ` · score ${source.relevance_score.toFixed(3)}`
                    : ""}
                </li>
              ))}
            </ul>
          </details>
        )}

        {/* Error state with retry */}
        {message.status === "error" && (
          <div className="mt-1 flex items-center gap-2 text-xs text-red-600">
            <span>{message.error ?? "Failed to send."}</span>
            <button
              type="button"
              onClick={() => onRetry(message)}
              className="rounded border border-red-300 px-2 py-0.5 font-medium hover:bg-red-100"
            >
              Retry
            </button>
          </div>
        )}

        {/* Sending indicator on the user bubble */}
        {message.status === "sending" && isUser && (
          <div className="mt-1 text-right text-[11px] text-slate-400">Sending…</div>
        )}
      </div>
    </div>
  );
}
