// API client for the FastAPI backend.
// The base URL is injected at build/runtime via NEXT_PUBLIC_API_BASE_URL.

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

// Shape of the backend chat response (mirrors ChatResponse in the backend).
export type ChatResponse = {
  answer: string;
  session_id: string;
  intent?: string;
  confidence?: number;
  faithfulness?: number;
  latency_ms?: number;
  escalated: boolean;
  cached: boolean;
  sources: unknown[];
};

// Send a customer message to the backend RAG chat endpoint.
export async function sendChatMessage(
  message: string,
  sessionId: string | null,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  return (await response.json()) as ChatResponse;
}
