"use client";

import { ArrowUpRight, Bot, KeyRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useAIActivity, useAISettings, useKnowledge } from "@/hooks/use-nexus";
import { api, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { AIReply, AIReplyStatus, AISettings } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS: Record<AIReplyStatus, { label: string; className: string }> = {
  sent: { label: "Replied", className: "bg-positive-soft text-positive" },
  handoff: { label: "Handed to team", className: "bg-attention-soft text-attention" },
  skipped: { label: "Skipped", className: "bg-muted text-muted-foreground" },
  error: { label: "Error", className: "bg-destructive/10 text-destructive" },
  pending: { label: "Thinking", className: "bg-brand-soft text-brand" },
  sending: { label: "Sending", className: "bg-brand-soft text-brand" },
};

export function AIEmployeesView() {
  const settings = useAISettings();
  const knowledge = useKnowledge();
  const activity = useAIActivity(40);

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="AI Employees" description="Agents that answer customers for you" />

      <div className="scroll-quiet flex-1 overflow-y-auto">
        <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-5">
          <div className="lg:col-span-2">
            {settings.error ? (
              <ErrorNotice error={settings.error} onRetry={() => settings.mutate()} />
            ) : !settings.data ? (
              <Skeleton className="h-96 w-full rounded-xl" />
            ) : (
              <AgentCard
                // Re-created whenever the saved settings change, so the form shows them.
                key={JSON.stringify(settings.data)}
                settings={settings.data}
                articleCount={knowledge.data?.items.length}
                onSaved={(next) => settings.mutate(next, { revalidate: false })}
              />
            )}
          </div>

          <section className="overflow-hidden rounded-xl border bg-card lg:col-span-3">
            <header className="border-b px-4 py-3">
              <h2 className="text-sm font-semibold">Activity</h2>
              <p className="text-[12px] text-muted-foreground">
                Every customer message the agent looked at, newest first
              </p>
            </header>
            {activity.isLoading ? (
              <div className="space-y-3 p-4">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : !activity.data || activity.data.items.length === 0 ? (
              <p className="px-4 py-12 text-center text-[13px] text-muted-foreground">
                Nothing yet. When the agent is on, each new customer message appears here.
              </p>
            ) : (
              <ul className="divide-y">
                {activity.data.items.map((item) => (
                  <ActivityRow key={item.id} item={item} />
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function AgentCard({
  settings,
  articleCount,
  onSaved,
}: {
  settings: AISettings;
  articleCount: number | undefined;
  onSaved: (settings: AISettings) => void;
}) {
  const [enabled, setEnabled] = useState(settings.enabled);
  const [businessName, setBusinessName] = useState(settings.business_name);
  const [instructions, setInstructions] = useState(settings.instructions);
  const [saving, setSaving] = useState(false);

  const changed =
    enabled !== settings.enabled ||
    businessName !== settings.business_name ||
    instructions !== settings.instructions;

  async function save(next = { enabled, business_name: businessName, instructions }) {
    setSaving(true);
    try {
      const saved = await api<AISettings>("/api/v1/ai/settings", {
        method: "PUT",
        body: JSON.stringify(next),
      });
      onSaved(saved);
      toast.success(saved.enabled ? "The agent is answering customers" : "Settings saved");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not save the settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-start gap-3 border-b p-4">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand">
          <Bot className="size-5" strokeWidth={1.75} />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">Customer support agent</h2>
          <p className="text-[12px] text-muted-foreground">
            Replies on every channel from your knowledge base · {settings.model}
          </p>
        </div>
        <Switch
          checked={enabled}
          disabled={!settings.configured || saving}
          label="Agent on"
          onCheckedChange={(value) => {
            setEnabled(value);
            void save({ enabled: value, business_name: businessName, instructions });
          }}
        />
      </div>

      {!settings.configured && (
        <div className="flex gap-2.5 border-b bg-attention-soft/60 p-4 text-[13px]">
          <KeyRound className="mt-0.5 size-4 shrink-0 text-attention" strokeWidth={1.75} />
          <p>
            Add <code className="font-mono text-[12px]">ANTHROPIC_API_KEY</code> to the backend&apos;s
            environment (Railway → backend → Variables), then deploy. The switch unlocks once the key is
            present.
          </p>
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
        className="space-y-4 p-4"
      >
        <label className="block">
          <span className="text-[13px] font-medium">Business name</span>
          <input
            dir="auto"
            value={businessName}
            onChange={(event) => setBusinessName(event.target.value)}
            maxLength={120}
            placeholder="How the agent refers to you"
            className="mt-1.5 h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
          />
        </label>
        <label className="block">
          <span className="text-[13px] font-medium">Instructions</span>
          <span className="block text-[12px] text-muted-foreground">
            Tone, things to always mention, things never to say. Facts belong in the Knowledge Base.
          </span>
          <textarea
            dir="auto"
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            maxLength={8000}
            rows={6}
            placeholder="For example: Be warm and brief. Always offer to book a free consultation."
            className="mt-1.5 block w-full resize-y rounded-lg border bg-background px-3 py-2.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
          />
        </label>

        <div className="flex items-center justify-between gap-3">
          <Link
            href="/knowledge"
            className="inline-flex items-center gap-1 text-[13px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Knowledge Base
            {articleCount !== undefined && ` · ${articleCount} article${articleCount === 1 ? "" : "s"}`}
            <ArrowUpRight className="size-3.5" />
          </Link>
          <Button type="submit" size="sm" disabled={!changed || saving}>
            {saving ? "Saving" : "Save"}
          </Button>
        </div>
      </form>

      <div className="space-y-1.5 border-t p-4 text-[12px] leading-relaxed text-muted-foreground">
        <p>The agent answers only from the Knowledge Base and hands anything else to your team with an internal note.</p>
        <p>It steps back from a conversation as soon as a team member replies. Turn it back on from that conversation in the Inbox.</p>
      </div>
    </section>
  );
}

function ActivityRow({ item }: { item: AIReply }) {
  const status = STATUS[item.status];
  return (
    <li>
      <Link
        href={`/inbox?c=${item.conversation_id}`}
        className="block px-4 py-3 outline-none transition-colors hover:bg-muted/60 focus-visible:bg-muted/60"
      >
        <div className="flex items-center gap-2">
          <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{item.contact_name}</span>
          <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium", status.className)}>
            {status.label}
          </span>
          <span className="w-8 shrink-0 text-right text-[11px] tabular-nums text-muted-foreground">
            {relativeTime(item.created_at)}
          </span>
        </div>
        {item.reply_text && (
          <p dir="auto" className="mt-1 line-clamp-2 text-[13px]">
            {item.reply_text}
          </p>
        )}
        {item.reason && (
          <p dir="auto" className="mt-0.5 line-clamp-2 text-[12px] text-muted-foreground">
            {item.reason}
          </p>
        )}
        {item.input_tokens + item.output_tokens > 0 && (
          <p className="mt-1 font-mono text-[11px] text-muted-foreground/80">
            {item.input_tokens.toLocaleString()} in · {item.output_tokens.toLocaleString()} out tokens
          </p>
        )}
      </Link>
    </li>
  );
}
