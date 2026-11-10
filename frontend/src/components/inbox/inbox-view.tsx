"use client";

import { MessagesSquare, RefreshCw } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ErrorNotice, SetupNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { useConversations, useMessages } from "@/hooks/use-nexus";
import { api, ApiError } from "@/lib/api";
import type { ItemList, Message } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ConversationList, type InboxFilter } from "./conversation-list";
import { DetailsPanel } from "./details-panel";
import { Thread } from "./thread";

export function InboxView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams.get("c");

  const [filter, setFilter] = useState<InboxFilter>("open");
  const [query, setQuery] = useState("");
  const [syncing, setSyncing] = useState(false);

  const conversations = useConversations();
  const messages = useMessages(selectedId);

  const all = useMemo(() => conversations.data?.items ?? [], [conversations.data]);
  const selected = all.find((c) => c.id === selectedId) ?? null;

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return all.filter((c) => {
      if (filter === "open" && c.status === "resolved") return false;
      if (filter === "resolved" && c.status !== "resolved") return false;
      if (!needle) return true;
      return (
        c.contact.name.toLowerCase().includes(needle) ||
        (c.last_message?.preview ?? "").toLowerCase().includes(needle)
      );
    });
  }, [all, filter, query]);

  // The selected conversation lives in the URL (?c=...), so a link from the
  // Dashboard opens the right thread and the browser's Back button works.
  function select(id: string | null) {
    router.replace(id ? `/inbox?c=${id}` : "/inbox", { scroll: false });
  }

  async function sync() {
    setSyncing(true);
    try {
      const result = await api<{ synced: number }>("/api/v1/conversations/sync", { method: "POST" });
      await conversations.mutate();
      toast.success(`Synced ${result.synced} conversation${result.synced === 1 ? "" : "s"} from Chatwoot`);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function send(content: string) {
    if (!selectedId) return;
    const path = `/api/v1/conversations/${selectedId}/messages`;

    // Show the reply at once, then swap in the real message Chatwoot created.
    const pending: Message = {
      id: `pending-${Date.now()}`,
      direction: "outbound",
      author: { type: "agent", name: "You" },
      content,
      private: false,
      sent_at: new Date().toISOString(),
    };

    try {
      await messages.mutate(
        async (current) => {
          const created = await api<Message>(path, {
            method: "POST",
            body: JSON.stringify({ content }),
          });
          return { items: [...(current?.items ?? []), created] } satisfies ItemList<Message>;
        },
        {
          optimisticData: (current) => ({ items: [...(current?.items ?? []), pending] }),
          rollbackOnError: true,
          revalidate: true,
        },
      );
      void conversations.mutate();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "The reply could not be sent");
      throw error;
    }
  }

  const listError = conversations.error;

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Unified Inbox"
        description="Every customer conversation in one place"
        className={cn(selected && "hidden md:flex")}
        actions={
          <Button variant="outline" size="sm" onClick={sync} disabled={syncing}>
            <RefreshCw className={cn(syncing && "animate-spin")} />
            {syncing ? "Syncing" : "Sync"}
          </Button>
        }
      />

      <div className="flex min-h-0 flex-1">
        <section
          aria-label="Conversations"
          className={cn(
            "w-full shrink-0 flex-col border-r md:flex md:w-80 lg:w-[22rem]",
            selected ? "hidden" : "flex",
          )}
        >
          {listError ? (
            <div className="p-3">
              {listError.notConfigured ? (
                <SetupNotice />
              ) : (
                <ErrorNotice error={listError} onRetry={() => conversations.mutate()} />
              )}
            </div>
          ) : (
            <ConversationList
              conversations={visible}
              loading={conversations.isLoading}
              selectedId={selectedId}
              onSelect={select}
              filter={filter}
              onFilterChange={setFilter}
              query={query}
              onQueryChange={setQuery}
            />
          )}
        </section>

        <section
          aria-label="Conversation"
          className={cn("min-w-0 flex-1 md:block", selected ? "block" : "hidden")}
        >
          {selected ? (
            <Thread
              conversation={selected}
              messages={messages.data?.items}
              loading={messages.isLoading}
              error={messages.error}
              onRetry={() => messages.mutate()}
              onBack={() => select(null)}
              onSend={send}
            />
          ) : (
            <NothingSelected hasConversations={all.length > 0} />
          )}
        </section>

        {selected && (
          <aside aria-label="Details" className="hidden w-72 shrink-0 border-l xl:block">
            <DetailsPanel conversation={selected} />
          </aside>
        )}
      </div>
    </div>
  );
}

function NothingSelected({ hasConversations }: { hasConversations: boolean }) {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-muted/30 px-6 text-center">
      <span className="flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
        <MessagesSquare className="size-5" strokeWidth={1.75} />
      </span>
      <p className="mt-4 text-sm font-medium">
        {hasConversations ? "Select a conversation" : "No conversations yet"}
      </p>
      <p className="mt-1 max-w-xs text-[13px] text-muted-foreground">
        {hasConversations
          ? "Choose a conversation on the left to read it and reply."
          : "Send a message through a Chatwoot channel and it will appear here within a few seconds."}
      </p>
    </div>
  );
}
