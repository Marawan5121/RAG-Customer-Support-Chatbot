"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import ChatInput from "@/components/ChatInput";
import ChatMessage from "@/components/ChatMessage";
import Sidebar from "@/components/Sidebar";
import { ApiError, getIndexStatus, getSession, sendChatMessage } from "@/lib/api";
import type { SessionMeta, UIMessage } from "@/lib/types";

// localStorage keys.
const LS_SESSIONS = "rag.sessions";
const LS_ACTIVE = "rag.activeSession";
const LS_MESSAGES_PREFIX = "rag.messages.";

// Example prompts shown on the empty state.
const SUGGESTIONS = [
  "How do I cancel my order?",
  "Where is my refund?",
  "I want to track my order",
];

// --- localStorage helpers (guarded for SSR) -------------------------------
function loadSessions(): SessionMeta[] {
  try {
    return JSON.parse(localStorage.getItem(LS_SESSIONS) ?? "[]") as SessionMeta[];
  } catch {
    return [];
  }
}
function loadMessages(sessionId: string): UIMessage[] {
  try {
    return JSON.parse(localStorage.getItem(LS_MESSAGES_PREFIX + sessionId) ?? "[]") as UIMessage[];
  } catch {
    return [];
  }
}
function deriveTitle(text: string): string {
  const clean = text.trim().replace(/\s+/g, " ");
  return clean.length > 40 ? `${clean.slice(0, 40)}…` : clean || "New chat";
}
function newId(): string {
  // crypto.randomUUID is available in modern browsers; fall back if absent.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function HomePage() {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [indexStatusLabel, setIndexStatusLabel] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Refresh a session transcript from the backend (authoritative history).
  const refreshTranscript = useCallback(async (sessionId: string) => {
    try {
      const transcript = await getSession(sessionId);
      const mapped: UIMessage[] = transcript.messages.map((m) => ({
        id: m.message_id,
        role: m.role === "user" ? "user" : "assistant",
        content: m.content,
        status: "sent",
        createdAt: m.timestamp,
      }));
      if (mapped.length > 0) setMessages(mapped);
    } catch {
      // 404 (new session) or 503 (Cosmos disabled): keep the local cache.
    }
  }, []);

  // Initial hydration from localStorage (runs once after mount).
  useEffect(() => {
    const storedSessions = loadSessions();
    setSessions(storedSessions);
    const active = localStorage.getItem(LS_ACTIVE);
    if (active && storedSessions.some((s) => s.id === active)) {
      setActiveSessionId(active);
      setMessages(loadMessages(active));
      void refreshTranscript(active);
    }
    setHydrated(true);
  }, [refreshTranscript]);

  // Probe backend availability and latest indexing job for the sidebar.
  useEffect(() => {
    getIndexStatus()
      .then((res) => {
        setBackendOnline(true);
        const latest = res.jobs?.[0];
        setIndexStatusLabel(latest ? `${latest.status} (profile ${latest.chunk_profile})` : "no jobs yet");
      })
      .catch(() => {
        setBackendOnline(false);
        setIndexStatusLabel(null);
      });
  }, []);

  // Persist sessions whenever they change.
  useEffect(() => {
    if (hydrated) localStorage.setItem(LS_SESSIONS, JSON.stringify(sessions));
  }, [sessions, hydrated]);

  // Persist the active session id and its messages.
  useEffect(() => {
    if (!hydrated || !activeSessionId) return;
    localStorage.setItem(LS_ACTIVE, activeSessionId);
    localStorage.setItem(LS_MESSAGES_PREFIX + activeSessionId, JSON.stringify(messages));
  }, [messages, activeSessionId, hydrated]);

  // Auto-scroll to the newest message (or the typing indicator).
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Create a fresh conversation and make it active.
  const createSession = useCallback((): string => {
    const id = newId();
    const now = new Date().toISOString();
    const meta: SessionMeta = { id, title: "New chat", createdAt: now, updatedAt: now };
    setSessions((prev) => [meta, ...prev]);
    setActiveSessionId(id);
    setMessages([]);
    setError(null);
    return id;
  }, []);

  function handleSelect(id: string) {
    setActiveSessionId(id);
    setMessages(loadMessages(id));
    setError(null);
    setSidebarOpen(false);
    void refreshTranscript(id);
  }

  function handleDelete(id: string) {
    localStorage.removeItem(LS_MESSAGES_PREFIX + id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (id === activeSessionId) {
      setActiveSessionId(null);
      setMessages([]);
    }
  }

  // Core send routine; supports retrying an existing failed user message.
  const sendMessage = useCallback(
    async (text: string, retryId?: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      // Ensure there is an active session to attach the message to.
      const sessionId = activeSessionId ?? createSession();
      const userMsgId = retryId ?? newId();
      const now = new Date().toISOString();

      setError(null);
      setMessages((prev) => {
        if (retryId) {
          return prev.map((m) =>
            m.id === retryId ? { ...m, status: "sending", error: undefined } : m,
          );
        }
        return [
          ...prev,
          { id: userMsgId, role: "user", content: trimmed, status: "sending", createdAt: now },
        ];
      });
      if (!retryId) setInput("");
      setIsLoading(true);

      try {
        const res = await sendChatMessage({ message: trimmed, session_id: sessionId });
        setMessages((prev) => {
          const updated = prev.map((m) =>
            m.id === userMsgId ? { ...m, status: "sent" as const } : m,
          );
          return [
            ...updated,
            {
              id: newId(),
              role: "assistant",
              content: res.answer,
              status: "sent",
              createdAt: new Date().toISOString(),
              escalated: res.escalated,
              latencyMs: res.latency_ms,
              sources: res.sources,
            },
          ];
        });
        // Update the session title (from the first message) and timestamp.
        setSessions((prev) =>
          prev.map((s) =>
            s.id === sessionId
              ? {
                  ...s,
                  title: s.title === "New chat" ? deriveTitle(trimmed) : s.title,
                  updatedAt: new Date().toISOString(),
                }
              : s,
          ),
        );
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "An unexpected error occurred.";
        setMessages((prev) =>
          prev.map((m) => (m.id === userMsgId ? { ...m, status: "error", error: message } : m)),
        );
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [activeSessionId, createSession, isLoading],
  );

  const showEmptyState = !activeSessionId || messages.length === 0;

  return (
    <div className="flex h-full">
      {/* Sidebar - permanent on desktop, slide-over on mobile */}
      <div className="hidden md:block">
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelect={handleSelect}
          onNew={createSession}
          onDelete={handleDelete}
          backendOnline={backendOnline}
          indexStatusLabel={indexStatusLabel}
        />
      </div>
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 flex md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
          <div className="relative z-40">
            <Sidebar
              sessions={sessions}
              activeSessionId={activeSessionId}
              onSelect={handleSelect}
              onNew={() => {
                createSession();
                setSidebarOpen(false);
              }}
              onDelete={handleDelete}
              backendOnline={backendOnline}
              indexStatusLabel={indexStatusLabel}
            />
          </div>
        </div>
      )}

      {/* Main chat column */}
      <main className="flex h-full flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-1 text-slate-600 hover:bg-slate-100 md:hidden"
            aria-label="Open menu"
          >
            ☰
          </button>
          <div>
            <h2 className="text-sm font-semibold text-brand-navy">Customer Support</h2>
            <p className="text-xs text-slate-400">Powered by RAG · Gemini · Azure AI Search</p>
          </div>
        </header>

        {/* Error banner */}
        {error && (
          <div className="flex items-center justify-between gap-3 border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="rounded px-2 text-red-500 hover:bg-red-100"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        )}

        {/* Message thread */}
        <div className="thin-scrollbar flex-1 space-y-4 overflow-y-auto bg-slate-50 p-4">
          {showEmptyState ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <h3 className="text-lg font-semibold text-slate-600">How can I help you today?</h3>
              <p className="mt-1 text-sm text-slate-400">Ask about orders, refunds, or your account.</p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void sendMessage(suggestion)}
                    disabled={isLoading}
                    className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-brand-azure hover:text-brand-azure disabled:opacity-50"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} onRetry={(m) => void sendMessage(m.content, m.id)} />
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
                    <div className="flex gap-1">
                      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={() => void sendMessage(input)}
          disabled={isLoading}
        />
      </main>
    </div>
  );
}
