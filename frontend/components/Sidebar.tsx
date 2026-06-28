"use client";

import type { SessionMeta } from "@/lib/types";

interface SidebarProps {
  sessions: SessionMeta[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  backendOnline: boolean | null;
  indexStatusLabel: string | null;
}

// Left rail: create a new chat, switch between past sessions, and view backend status.
export default function Sidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNew,
  onDelete,
  backendOnline,
  indexStatusLabel,
}: SidebarProps) {
  return (
    <aside className="flex h-full w-72 flex-col bg-brand-navy text-white">
      {/* Header + new chat */}
      <div className="border-b border-white/10 p-4">
        <h1 className="text-sm font-bold tracking-wide text-brand-light">SUPPORT ASSISTANT</h1>
        <button
          type="button"
          onClick={onNew}
          className="mt-3 w-full rounded-lg bg-white/10 px-3 py-2 text-sm font-semibold transition hover:bg-white/20"
        >
          + New chat
        </button>
      </div>

      {/* Session list */}
      <nav className="thin-scrollbar flex-1 space-y-1 overflow-y-auto p-2">
        {sessions.length === 0 && (
          <p className="px-2 py-3 text-xs text-white/50">No conversations yet.</p>
        )}
        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          return (
            <div
              key={session.id}
              className={`group flex items-center gap-1 rounded-lg px-2 ${
                isActive ? "bg-white/15" : "hover:bg-white/10"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect(session.id)}
                className="flex-1 truncate py-2 text-left text-sm"
                title={session.title}
              >
                {session.title}
              </button>
              <button
                type="button"
                onClick={() => onDelete(session.id)}
                aria-label="Delete conversation"
                className="opacity-0 transition group-hover:opacity-100 hover:text-red-300"
              >
                ×
              </button>
            </div>
          );
        })}
      </nav>

      {/* Status footer */}
      <div className="space-y-1 border-t border-white/10 p-4 text-xs text-white/60">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              backendOnline === null
                ? "bg-slate-400"
                : backendOnline
                  ? "bg-green-400"
                  : "bg-red-400"
            }`}
          />
          Backend: {backendOnline === null ? "checking…" : backendOnline ? "online" : "offline"}
        </div>
        {indexStatusLabel && <div>Knowledge base: {indexStatusLabel}</div>}
      </div>
    </aside>
  );
}
