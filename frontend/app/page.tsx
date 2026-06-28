"use client";

import { useState } from "react";
import { sendChatMessage } from "@/lib/api";

// A single chat message rendered in the conversation thread.
type ChatMessage = {
  role: "user" | "bot";
  content: string;
};

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Send the current input to the backend and append the response.
  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    try {
      const data = await sendChatMessage(text, sessionId);
      setSessionId(data.session_id);
      setMessages((prev) => [...prev, { role: "bot", content: data.answer }]);
    } catch (error) {
      // The backend pipeline is a placeholder, so surface a friendly notice.
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: "The chat pipeline is not implemented yet (Milestone 2)." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1 style={{ color: "var(--navy)", marginBottom: "1rem" }}>Support Assistant</h1>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1rem" }}>
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              background: msg.role === "user" ? "var(--navy)" : "var(--bot-bubble)",
              color: msg.role === "user" ? "#fff" : "#1e293b",
              padding: "0.6rem 0.9rem",
              borderRadius: "12px",
              maxWidth: "80%",
            }}
          >
            {msg.content}
          </div>
        ))}
        {loading && <div style={{ color: "#64748b" }}>Assistant is typing…</div>}
      </div>

      <div style={{ display: "flex", gap: "0.5rem" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Type your message…"
          style={{ flex: 1, padding: "0.6rem 0.9rem", borderRadius: "8px", border: "1px solid #cbd5e1" }}
        />
        <button
          onClick={handleSend}
          disabled={loading}
          style={{
            padding: "0.6rem 1.2rem",
            borderRadius: "8px",
            border: "none",
            background: "var(--azure)",
            color: "#fff",
            cursor: "pointer",
          }}
        >
          Send
        </button>
      </div>
    </main>
  );
}
