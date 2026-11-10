"use client";

import { Search } from "lucide-react";

import { CustomerAvatar } from "@/components/customer-avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { relativeTime } from "@/lib/format";
import type { Conversation } from "@/lib/types";
import { cn } from "@/lib/utils";

export type InboxFilter = "open" | "all" | "resolved";

const FILTERS: { key: InboxFilter; label: string }[] = [
  { key: "open", label: "Open" },
  { key: "all", label: "All" },
  { key: "resolved", label: "Resolved" },
];

export function ConversationList({
  conversations,
  loading,
  selectedId,
  onSelect,
  filter,
  onFilterChange,
  query,
  onQueryChange,
}: {
  conversations: Conversation[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  filter: InboxFilter;
  onFilterChange: (filter: InboxFilter) => void;
  query: string;
  onQueryChange: (query: string) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 space-y-2.5 border-b p-3">
        <label className="relative block">
          <span className="sr-only">Search conversations</span>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search by name or message"
            className="h-8 w-full rounded-lg border bg-background pl-8 pr-2.5 text-[13px] outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
          />
        </label>

        <div role="tablist" aria-label="Filter conversations" className="flex gap-1 rounded-lg bg-muted p-0.5">
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              role="tab"
              type="button"
              aria-selected={filter === key}
              onClick={() => onFilterChange(key)}
              className={cn(
                "h-6 flex-1 rounded-md text-[12px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                filter === key
                  ? "bg-background text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="space-y-4 p-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex gap-3">
                <Skeleton className="size-8 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-1/2" />
                  <Skeleton className="h-3 w-5/6" />
                </div>
              </div>
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <p className="px-6 py-12 text-center text-[13px] text-muted-foreground">
            {query ? "No conversation matches your search." : "No conversations in this view."}
          </p>
        ) : (
          <ul>
            {conversations.map((conversation) => (
              <li key={conversation.id}>
                <ConversationRow
                  conversation={conversation}
                  selected={conversation.id === selectedId}
                  onSelect={onSelect}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ConversationRow({
  conversation,
  selected,
  onSelect,
}: {
  conversation: Conversation;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const { contact, last_message: last } = conversation;
  const waiting = conversation.status !== "resolved" && last?.direction === "inbound";

  return (
    <button
      type="button"
      onClick={() => onSelect(conversation.id)}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "relative flex w-full items-start gap-3 border-b px-3 py-3 text-left outline-none transition-colors",
        "focus-visible:bg-muted/70",
        selected ? "bg-accent" : "hover:bg-muted/60",
      )}
    >
      {selected && <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-brand" />}
      <CustomerAvatar name={contact.name} />

      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className={cn("truncate text-[13px]", waiting ? "font-semibold" : "font-medium")}>
            {contact.name}
          </span>
          <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
            {relativeTime(last?.at ?? conversation.updated_at)}
          </span>
        </span>

        <span className="mt-0.5 flex items-center gap-2">
          <span
            className={cn(
              "min-w-0 flex-1 truncate text-[13px]",
              waiting ? "text-foreground" : "text-muted-foreground",
            )}
          >
            {last ? (
              <>
                {last.direction === "outbound" && <span className="text-muted-foreground">You: </span>}
                {last.preview}
              </>
            ) : (
              "No messages yet"
            )}
          </span>
          {waiting && (
            <span className="size-2 shrink-0 rounded-full bg-attention" aria-label="Awaiting reply" />
          )}
          {conversation.status === "resolved" && (
            <span className="shrink-0 text-[11px] text-muted-foreground">Resolved</span>
          )}
        </span>
      </span>
    </button>
  );
}
