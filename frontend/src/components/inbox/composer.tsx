"use client";

import { CornerDownLeft, SendHorizontal } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * The reply box. The text goes to the NEXUS backend, which sends it to
 * Chatwoot with the API token. The browser never sees that token.
 */
export function Composer({
  contactName,
  disabled,
  onSend,
}: {
  contactName: string;
  disabled?: boolean;
  onSend: (content: string) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  const canSend = text.trim().length > 0 && !sending && !disabled;

  async function submit() {
    if (!canSend) return;
    const content = text.trim();
    setSending(true);
    setText("");
    try {
      await onSend(content);
    } catch {
      // Sending failed: give the text back so nothing the agent typed is lost.
      setText(content);
    } finally {
      setSending(false);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
      className="shrink-0 border-t bg-background p-3 sm:px-4"
    >
      <div className="mx-auto w-full max-w-3xl rounded-xl border bg-card transition-shadow focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30">
        <label htmlFor="reply" className="sr-only">
          Reply to {contactName}
        </label>
        <textarea
          id="reply"
          rows={2}
          value={text}
          disabled={disabled}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              void submit();
            }
          }}
          placeholder={disabled ? "Connect Chatwoot to reply" : `Reply to ${contactName}…`}
          className="block max-h-40 min-h-[3.25rem] w-full resize-none bg-transparent px-3.5 pt-3 text-sm outline-none placeholder:text-muted-foreground/70 disabled:cursor-not-allowed"
        />
        <div className="flex items-center justify-between gap-2 px-2.5 pb-2.5">
          <span className="hidden items-center gap-1 pl-1 text-[11px] text-muted-foreground sm:flex">
            <CornerDownLeft className="size-3" /> Enter to send, Shift + Enter for a new line
          </span>
          <Button type="submit" size="sm" disabled={!canSend} className="ml-auto">
            {sending ? "Sending" : "Send"}
            <SendHorizontal />
          </Button>
        </div>
      </div>
    </form>
  );
}
