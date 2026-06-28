"use client";

import { KeyboardEvent } from "react";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled: boolean;
}

// Multi-line input with a send button. Enter sends, Shift+Enter inserts a newline.
export default function ChatInput({ value, onChange, onSend, disabled }: ChatInputProps) {
  const canSend = !disabled && value.trim().length > 0;

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSend) onSend();
    }
  }

  return (
    <div className="border-t border-slate-200 bg-white p-3">
      <div className="flex items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Type your message…"
          className="max-h-40 min-h-[44px] flex-1 resize-y rounded-xl border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-brand-azure focus:ring-2 focus:ring-brand-light"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={!canSend}
          className="h-[44px] shrink-0 rounded-xl bg-brand-azure px-5 text-sm font-semibold text-white transition hover:bg-brand-navy disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-400">
        Press <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
      </p>
    </div>
  );
}
