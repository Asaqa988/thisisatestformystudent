"use client";

import { ArrowLeft, Lock } from "lucide-react";
import { useEffect, useRef } from "react";

import { CustomerAvatar } from "@/components/customer-avatar";
import { ErrorNotice, SetupNotice } from "@/components/notices";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApiError } from "@/lib/api";
import { channelLabel, clockTime, dayLabel } from "@/lib/format";
import type { Conversation, ConversationStatus, Message } from "@/lib/types";
import { cn } from "@/lib/utils";

import { Composer } from "./composer";

const STATUS_STYLES: Record<ConversationStatus, string> = {
  open: "bg-brand-soft text-brand",
  pending: "bg-attention-soft text-attention",
  snoozed: "bg-muted text-muted-foreground",
  resolved: "bg-muted text-muted-foreground",
};

export function Thread({
  conversation,
  messages,
  loading,
  error,
  onRetry,
  onBack,
  onSend,
}: {
  conversation: Conversation;
  messages: Message[] | undefined;
  loading: boolean;
  error: ApiError | undefined;
  onRetry: () => void;
  onBack: () => void;
  onSend: (content: string) => Promise<void>;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const count = messages?.length ?? 0;

  // Keep the newest message in view: when the conversation changes and
  // whenever a message arrives.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [conversation.id, count]);

  return (
    <div className="flex h-full min-w-0 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b px-3 sm:px-4">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Back to conversations"
          onClick={onBack}
          className="md:hidden"
        >
          <ArrowLeft />
        </Button>
        <CustomerAvatar name={conversation.contact.name} />
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold leading-tight">{conversation.contact.name}</h2>
          <p className="truncate text-[12px] leading-tight text-muted-foreground">
            {channelLabel(conversation.channel)}
            {conversation.inbox_name ? ` · ${conversation.inbox_name}` : ""}
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
            STATUS_STYLES[conversation.status],
          )}
        >
          {conversation.status}
        </span>
      </header>

      <div ref={scrollRef} className="scroll-quiet min-h-0 flex-1 overflow-y-auto bg-muted/30">
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-end gap-1 px-3 py-4 sm:px-6">
          {error && !messages ? (
            error.notConfigured ? (
              <SetupNotice className="my-auto" />
            ) : (
              <ErrorNotice error={error} onRetry={onRetry} className="my-auto" />
            )
          ) : loading && !messages ? (
            <div className="space-y-3">
              <Skeleton className="h-10 w-2/5 rounded-2xl" />
              <Skeleton className="ml-auto h-10 w-1/2 rounded-2xl" />
              <Skeleton className="h-10 w-1/3 rounded-2xl" />
            </div>
          ) : count === 0 ? (
            <p className="my-auto text-center text-[13px] text-muted-foreground">
              No messages in this conversation yet.
            </p>
          ) : (
            <>
              {messages!.map((message, index) => {
                const previous = messages![index - 1];
                const newDay = !previous || dayLabel(previous.sent_at) !== dayLabel(message.sent_at);
                return (
                  <div key={message.id}>
                    {newDay && <DaySeparator label={dayLabel(message.sent_at)} />}
                    <MessageItem message={message} />
                  </div>
                );
              })}
              {/* A refresh failed but we still have the last messages we loaded:
                  keep them on screen and say that they may be out of date. */}
              {error && <ErrorNotice error={error} onRetry={onRetry} className="mt-3" />}
            </>
          )}
        </div>
      </div>

      <Composer
        key={conversation.id}
        disabled={Boolean(error?.notConfigured)}
        contactName={conversation.contact.name}
        onSend={onSend}
      />
    </div>
  );
}

function DaySeparator({ label }: { label: string }) {
  return (
    <div className="my-3 flex items-center gap-3">
      <span className="h-px flex-1 bg-border" />
      <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

function MessageItem({ message }: { message: Message }) {
  if (message.direction === "system") {
    return (
      <p className="my-2 text-center text-[12px] text-muted-foreground">
        {message.content} · {clockTime(message.sent_at)}
      </p>
    );
  }

  const outbound = message.direction === "outbound";
  const pending = message.id.startsWith("pending-");

  return (
    <div className={cn("my-1 flex flex-col", outbound ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm leading-relaxed sm:max-w-[75%]",
          message.private
            ? "rounded-br-md border border-dashed border-attention/50 bg-attention-soft text-foreground"
            : outbound
              ? "rounded-br-md bg-primary text-primary-foreground"
              : "rounded-bl-md border bg-card",
          pending && "opacity-60",
        )}
      >
        {message.private && (
          <span className="mb-1 flex items-center gap-1 text-[11px] font-medium text-attention">
            <Lock className="size-3" /> Internal note
          </span>
        )}
        {message.content || <span className="italic opacity-70">No text content</span>}
      </div>
      <span className="mt-1 px-1 text-[11px] text-muted-foreground">
        {pending ? "Sending…" : `${message.author.name} · ${clockTime(message.sent_at)}`}
      </span>
    </div>
  );
}
