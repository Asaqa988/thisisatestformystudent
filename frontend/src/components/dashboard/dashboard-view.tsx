"use client";

import { ArrowUpRight, CopyCheck, Inbox, MessageCircleReply, Radio } from "lucide-react";
import Link from "next/link";

import { CustomerAvatar } from "@/components/customer-avatar";
import { ErrorNotice, SetupNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useConversations, useDashboardSummary, useEvents } from "@/hooks/use-nexus";
import { channelLabel, eventLabel, relativeTime } from "@/lib/format";
import type { IntegrationStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Systems the course connects later. Listed so the dashboard shows the whole plan. */
const PLANNED_SYSTEMS = [
  { name: "Twenty CRM", role: "Customers and deals" },
  { name: "Plane", role: "Projects and tasks" },
  { name: "Activepieces", role: "Workflow automation" },
];

function ago(iso: string) {
  const time = relativeTime(iso);
  return time === "now" ? "just now" : `${time} ago`;
}

export function DashboardView() {
  const summary = useDashboardSummary();
  const conversations = useConversations();
  const events = useEvents(10);

  const data = summary.data;
  const chatwoot = data?.integrations.find((i) => i.key === "chatwoot");
  const aiAgent = data?.integrations.find((i) => i.key === "ai");
  const awaiting =
    conversations.data?.items.filter(
      (c) => c.status !== "resolved" && c.last_message?.direction === "inbound",
    ) ?? [];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Dashboard"
        description="What needs attention across the agency"
        actions={
          <Link href="/inbox" className={buttonVariants({ variant: "default", size: "sm" })}>
            Open Inbox
            <ArrowUpRight />
          </Link>
        }
      />

      <div className="scroll-quiet flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6">
          {summary.error && <ErrorNotice error={summary.error} onRetry={() => summary.mutate()} />}
          {chatwoot && !chatwoot.configured && <SetupNotice />}

          <section aria-label="Key numbers" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              icon={Inbox}
              label="Open conversations"
              value={data?.conversations.open}
              hint={data ? `${data.conversations.total} in total` : undefined}
            />
            <StatCard
              icon={MessageCircleReply}
              label="Awaiting reply"
              value={data?.conversations.awaiting_reply}
              hint="Customer spoke last"
              attention={(data?.conversations.awaiting_reply ?? 0) > 0}
            />
            <StatCard
              icon={Radio}
              label="Events received"
              value={data?.events.received_24h}
              hint={
                data?.events.last_received_at
                  ? `Last one ${ago(data.events.last_received_at)}`
                  : "Last 24 hours"
              }
            />
            <StatCard
              icon={CopyCheck}
              label="Duplicates ignored"
              value={data?.events.duplicates_ignored}
              hint="Stored only once"
            />
          </section>

          <div className="grid gap-6 lg:grid-cols-3">
            <Panel
              title="Needs a reply"
              subtitle="Conversations where the customer is waiting"
              className="lg:col-span-2"
            >
              {conversations.isLoading ? (
                <RowSkeletons />
              ) : awaiting.length === 0 ? (
                <Empty
                  title="Nobody is waiting"
                  text="When a customer writes in, the conversation appears here."
                />
              ) : (
                <ul className="divide-y">
                  {awaiting.slice(0, 6).map((c) => (
                    <li key={c.id}>
                      <Link
                        href={`/inbox?c=${c.id}`}
                        className="flex items-center gap-3 px-4 py-3 outline-none transition-colors hover:bg-muted/60 focus-visible:bg-muted/60"
                      >
                        <CustomerAvatar name={c.contact.name} />
                        <span className="min-w-0 flex-1">
                          <span className="flex items-baseline justify-between gap-3">
                            <span className="truncate text-sm font-medium">{c.contact.name}</span>
                            <span className="shrink-0 text-[12px] tabular-nums text-muted-foreground">
                              {relativeTime(c.last_message?.at)}
                            </span>
                          </span>
                          <span className="mt-0.5 block truncate text-[13px] text-muted-foreground">
                            {c.last_message?.preview}
                          </span>
                        </span>
                        <span className="hidden shrink-0 rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground sm:inline">
                          {channelLabel(c.channel)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Connected systems" subtitle="One interface, several engines">
              <ul className="divide-y">
                <SystemRow
                  name="Chatwoot"
                  role="Conversations and messaging"
                  status={chatwoot}
                  loading={summary.isLoading}
                />
                <SystemRow
                  name="AI agent (Claude)"
                  role="Answers customers from the Knowledge Base"
                  status={aiAgent}
                  loading={summary.isLoading}
                  offLabel="Off"
                />
                {PLANNED_SYSTEMS.map((system) => (
                  <li key={system.name} className="flex items-center gap-3 px-4 py-3">
                    <span className="size-2 shrink-0 rounded-full border border-muted-foreground/40" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-muted-foreground">{system.name}</span>
                      <span className="block truncate text-[12px] text-muted-foreground/80">{system.role}</span>
                    </span>
                    <span className="shrink-0 text-[11px] text-muted-foreground">Later lesson</span>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>

          <Panel
            title="Event stream"
            subtitle="What Chatwoot has told NEXUS, newest first"
          >
            {events.isLoading ? (
              <RowSkeletons />
            ) : !events.data || events.data.items.length === 0 ? (
              <Empty
                title="No events yet"
                text="Each webhook NEXUS receives is verified, stored once and listed here."
              />
            ) : (
              <ul className="divide-y">
                {events.data.items.map((event) => (
                  <li key={event.id} className="flex items-center gap-3 px-4 py-2.5">
                    <span className="w-36 shrink-0 truncate font-mono text-[12px] text-brand">
                      {event.event_type}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[13px]" title={eventLabel(event.event_type)}>
                      {event.summary}
                    </span>
                    {event.duplicate_count > 0 && (
                      <span className="shrink-0 rounded-full bg-attention-soft px-2 py-0.5 text-[11px] font-medium text-attention">
                        {event.duplicate_count} duplicate{event.duplicate_count === 1 ? "" : "s"} ignored
                      </span>
                    )}
                    <span className="w-10 shrink-0 text-right text-[12px] tabular-nums text-muted-foreground">
                      {relativeTime(event.received_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  attention,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  label: string;
  value: number | undefined;
  hint?: string;
  attention?: boolean;
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] text-muted-foreground">{label}</span>
        <Icon
          className={cn("size-4 shrink-0", attention ? "text-attention" : "text-muted-foreground/60")}
          strokeWidth={1.75}
        />
      </div>
      <div className="mt-2 h-9">
        {value === undefined ? (
          <Skeleton className="h-8 w-12" />
        ) : (
          <span className="text-3xl font-semibold tracking-tight tabular-nums">{value}</span>
        )}
      </div>
      {hint && <p className="mt-1 truncate text-[12px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Panel({
  title,
  subtitle,
  className,
  children,
}: {
  title: string;
  subtitle?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn("overflow-hidden rounded-xl border bg-card", className)}>
      <header className="border-b px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle && <p className="text-[12px] text-muted-foreground">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

function SystemRow({
  name,
  role,
  status,
  loading,
  offLabel = "Not responding",
}: {
  name: string;
  role: string;
  status: IntegrationStatus | undefined;
  loading: boolean;
  offLabel?: string;
}) {
  const state = !status ? "idle" : !status.configured ? "setup" : status.ok ? "ok" : "down";
  const label = { idle: loading ? "Checking" : "Unknown", setup: "Needs setup", ok: "Connected", down: offLabel }[state];

  return (
    <li className="flex items-center gap-3 px-4 py-3" title={status?.detail}>
      <span
        className={cn(
          "size-2 shrink-0 rounded-full",
          state === "ok" && "bg-positive",
          state === "setup" && "bg-attention",
          state === "down" && "bg-destructive",
          state === "idle" && "bg-muted-foreground/40",
        )}
      />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{name}</span>
        <span className="block truncate text-[12px] text-muted-foreground">{role}</span>
      </span>
      <span
        className={cn(
          "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
          state === "ok" && "bg-positive-soft text-positive",
          state === "setup" && "bg-attention-soft text-attention",
          state === "down" && "bg-destructive/10 text-destructive",
          state === "idle" && "bg-muted text-muted-foreground",
        )}
      >
        {label}
      </span>
    </li>
  );
}

function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="px-4 py-10 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted-foreground">{text}</p>
    </div>
  );
}

function RowSkeletons() {
  return (
    <div className="space-y-3 p-4">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="size-8 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
