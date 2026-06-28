// ---------------------------------------------------------------------------
// API client for the FastAPI RAG backend.
// Provides typed functions and a unified error model. The base URL is injected
// at build/runtime via NEXT_PUBLIC_API_BASE_URL.
// ---------------------------------------------------------------------------

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

// --- Backend DTOs (mirror the Pydantic schemas) ---------------------------

// Request body for POST /chat.
export interface ChatRequestPayload {
  message: string;
  session_id?: string | null;
  customer_id?: string | null;
}

// A knowledge-base chunk used to ground the answer (ChatResponse.sources[]).
export interface SourceChunk {
  chunk_id: string | null;
  content_text: string;
  intent_label?: string | null;
  category?: string | null;
  relevance_score?: number | null;
}

// Response body for POST /chat.
export interface ChatResponse {
  answer: string;
  session_id: string;
  intent?: string | null;
  confidence?: number | null;
  faithfulness?: number | null;
  latency_ms?: number | null;
  escalated: boolean;
  cached: boolean;
  sources: SourceChunk[];
}

// A single stored message returned by GET /sessions/{id}.
export interface TranscriptMessage {
  message_id: string;
  role: string; // "user" | "bot"
  content: string;
  timestamp: string;
}

// Response body for GET /sessions/{id}.
export interface SessionTranscript {
  session_id: string;
  customer_id?: string | null;
  last_activity?: string | null;
  messages: TranscriptMessage[];
}

// A single indexing job (GET /index/status).
export interface IndexJobStatus {
  job_id: string;
  status: string;
  chunk_profile: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  stats?: unknown;
}

// Response body for GET /index/status.
export interface IndexStatusResponse {
  jobs: IndexJobStatus[];
}

// --- Error model ----------------------------------------------------------

// Unified error carrying the HTTP status (0 == network/transport failure).
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Translate an HTTP status + raw server detail into a user-friendly message.
function friendlyMessage(status: number, serverMessage: string): string {
  switch (status) {
    case 400:
    case 422:
      return serverMessage || "Your message was invalid. Please rephrase and try again.";
    case 401:
      return "You are not authorised. Please sign in again.";
    case 404:
      return serverMessage || "The requested resource was not found.";
    case 429:
      return "Too many requests. Please wait a moment and try again.";
    case 500:
      return "The server hit an unexpected error. Please try again shortly.";
    case 502:
      return serverMessage || "The assistant pipeline failed upstream. Please retry.";
    case 503:
      return serverMessage || "A required service is temporarily unavailable. Please retry.";
    default:
      return serverMessage || `Request failed (HTTP ${status}).`;
  }
}

// Extract and normalise an error detail from a non-OK response.
async function extractErrorDetail(response: Response): Promise<string> {
  let serverMessage = "";
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") {
      serverMessage = data.detail;
    } else if (data?.detail) {
      serverMessage = JSON.stringify(data.detail);
    }
  } catch {
    // Body was not JSON; fall back to the status-based message.
  }
  return friendlyMessage(response.status, serverMessage);
}

// Core request helper - throws ApiError on network or HTTP failures.
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
    });
  } catch {
    // Transport-level failure (server down, DNS, CORS, offline, ...).
    throw new ApiError(
      "Network error: unable to reach the server. Check your connection and that the backend is running.",
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await extractErrorDetail(response), response.status);
  }

  return (await response.json()) as T;
}

// --- Public API functions -------------------------------------------------

// Send a customer message to the RAG chat endpoint.
export function sendChatMessage(payload: ChatRequestPayload): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Fetch a session transcript (history) by id.
export function getSession(sessionId: string): Promise<SessionTranscript> {
  return request<SessionTranscript>(`/sessions/${encodeURIComponent(sessionId)}`, {
    method: "GET",
  });
}

// Fetch the knowledge-base indexing job statuses (optional dashboard).
export function getIndexStatus(): Promise<IndexStatusResponse> {
  return request<IndexStatusResponse>("/index/status", { method: "GET" });
}
