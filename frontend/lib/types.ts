// ---------------------------------------------------------------------------
// UI-side types for the chat interface (distinct from the backend DTOs).
// ---------------------------------------------------------------------------

import type { SourceChunk } from "@/lib/api";

// Roles as rendered in the UI ("bot" from the backend maps to "assistant").
export type ChatRole = "user" | "assistant";

// Delivery state of a message, used to drive spinners and the retry control.
export type MessageStatus = "sending" | "sent" | "error";

// A message as displayed in the chat thread.
export interface UIMessage {
  id: string;
  role: ChatRole;
  content: string;
  status: MessageStatus;
  createdAt: string;
  escalated?: boolean;
  latencyMs?: number | null;
  sources?: SourceChunk[];
  error?: string; // populated when status === "error"
}

// Lightweight session descriptor persisted in localStorage for the sidebar.
export interface SessionMeta {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}
