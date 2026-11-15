"use client";

import {
  ArrowLeft,
  Building2,
  Clock,
  Mail,
  MapPin,
  MessageSquare,
  Phone,
  RefreshCw,
  Search,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { CustomerAvatar } from "@/components/customer-avatar";
import { ErrorNotice, SetupNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCustomer, useCustomers } from "@/hooks/use-nexus";
import { api, ApiError } from "@/lib/api";
import { channelLabel, relativeTime } from "@/lib/format";
import type { CustomerDetail, CustomerSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const CHANNEL_FILTERS: { key: string | null; label: string }[] = [
  { key: null, label: "All" },
  { key: "whatsapp", label: "WhatsApp" },
  { key: "instagram", label: "Instagram" },
  { key: "facebook", label: "Messenger" },
  { key: "web_widget", label: "Website" },
];

const CHANNEL_DOT: Record<string, string> = {
  whatsapp: "bg-[oklch(0.66_0.15_150)]",
  instagram: "bg-[oklch(0.62_0.2_350)]",
  facebook: "bg-[oklch(0.55_0.17_255)]",
  web_widget: "bg-brand",
  email: "bg-attention",
};

export function CustomersView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams.get("id");

  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const list = useCustomers(query, channel);
  const customers = list.data?.items ?? [];

  function select(id: string | null) {
    router.replace(id ? `/customers?id=${id}` : "/customers", { scroll: false });
  }

  async function sync() {
    setSyncing(true);
    try {
      const result = await api<{ customers: number; conversations: number }>("/api/v1/customers/sync", {
        method: "POST",
      });
      await list.mutate();
      toast.success(`${result.customers} customer${result.customers === 1 ? "" : "s"} up to date`);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Customers"
        description="Everyone who has written to you, on every channel"
        className={cn(selectedId && "hidden md:flex")}
        actions={
          <Button variant="outline" size="sm" onClick={sync} disabled={syncing}>
            <RefreshCw className={cn(syncing && "animate-spin")} />
            {syncing ? "Syncing" : "Sync"}
          </Button>
        }
      />

      <div className="flex min-h-0 flex-1">
        <section
          aria-label="Customer list"
          className={cn(
            "w-full shrink-0 flex-col border-r md:flex md:w-80 lg:w-[24rem]",
            selectedId ? "hidden" : "flex",
          )}
        >
          <div className="shrink-0 space-y-2.5 border-b p-3">
            <label className="relative block">
              <span className="sr-only">Search customers</span>
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="search"
                dir="auto"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Name, phone, email or company"
                className="h-8 w-full rounded-lg border bg-background pl-8 pr-2.5 text-[13px] outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
              />
            </label>
            <div role="tablist" aria-label="Filter by channel" className="flex flex-wrap gap-1">
              {CHANNEL_FILTERS.map(({ key, label }) => (
                <button
                  key={label}
                  type="button"
                  role="tab"
                  aria-selected={channel === key}
                  onClick={() => setChannel(key)}
                  className={cn(
                    "h-6 shrink-0 rounded-full border px-2.5 text-[12px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                    channel === key
                      ? "border-transparent bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
            {list.error ? (
              <div className="p-3">
                {list.error.notConfigured ? (
                  <SetupNotice />
                ) : (
                  <ErrorNotice error={list.error} onRetry={() => list.mutate()} />
                )}
              </div>
            ) : list.isLoading ? (
              <div className="space-y-4 p-3">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex gap-3">
                    <Skeleton className="size-9 rounded-full" />
                    <div className="flex-1 space-y-1.5">
                      <Skeleton className="h-3.5 w-1/2" />
                      <Skeleton className="h-3 w-3/4" />
                    </div>
                  </div>
                ))}
              </div>
            ) : customers.length === 0 ? (
              <EmptyList filtered={Boolean(query || channel)} onSync={sync} />
            ) : (
              <ul>
                {customers.map((customer) => (
                  <li key={customer.id}>
                    <CustomerRow
                      customer={customer}
                      selected={customer.id === selectedId}
                      onSelect={select}
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>

          {list.data && list.data.total > 0 && (
            <p className="shrink-0 border-t px-3 py-2 text-[12px] text-muted-foreground">
              {list.data.total} customer{list.data.total === 1 ? "" : "s"}
              {list.data.total > customers.length && ` · showing ${customers.length}`}
            </p>
          )}
        </section>

        <section aria-label="Customer profile" className={cn("min-w-0 flex-1 md:block", selectedId ? "block" : "hidden")}>
          {selectedId ? (
            <CustomerProfile customerId={selectedId} onBack={() => select(null)} onChanged={() => list.mutate()} />
          ) : (
            <NothingSelected />
          )}
        </section>
      </div>
    </div>
  );
}

function CustomerRow({
  customer,
  selected,
  onSelect,
}: {
  customer: CustomerSummary;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const contactLine = customer.phone || customer.email || [customer.city, customer.country].filter(Boolean).join(", ");
  return (
    <button
      type="button"
      onClick={() => onSelect(customer.id)}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "relative flex w-full items-start gap-3 border-b px-3 py-3 text-left outline-none transition-colors focus-visible:bg-muted/70",
        selected ? "bg-accent" : "hover:bg-muted/60",
      )}
    >
      {selected && <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-brand" />}
      <CustomerAvatar name={customer.name} className="size-9" />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span dir="auto" className="truncate text-[13px] font-medium">
            {customer.name}
          </span>
          <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
            {relativeTime(customer.last_message_at)}
          </span>
        </span>
        <span dir="auto" className="mt-0.5 block truncate text-[12px] text-muted-foreground">
          {contactLine || customer.last_message_preview || "No contact details yet"}
        </span>
        <span className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
          {customer.channels.map((channel) => (
            <ChannelTag key={channel} channel={channel} />
          ))}
          <span className="text-[11px] text-muted-foreground">
            {customer.conversation_count} conversation{customer.conversation_count === 1 ? "" : "s"}
          </span>
        </span>
      </span>
    </button>
  );
}

function ChannelTag({ channel }: { channel: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
      <span className={cn("size-1.5 rounded-full", CHANNEL_DOT[channel] ?? "bg-muted-foreground/50")} />
      {channelLabel(channel)}
    </span>
  );
}

function CustomerProfile({
  customerId,
  onBack,
  onChanged,
}: {
  customerId: string;
  onBack: () => void;
  onChanged: () => void;
}) {
  const { data: customer, error, isLoading, mutate } = useCustomer(customerId);
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    try {
      const fresh = await api<CustomerDetail>(`/api/v1/customers/${customerId}/refresh`, { method: "POST" });
      await mutate(fresh, { revalidate: false });
      onChanged();
      toast.success("Details refreshed from Chatwoot");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not refresh");
    } finally {
      setRefreshing(false);
    }
  }

  if (error) {
    return (
      <div className="p-4">
        <Button variant="ghost" size="sm" onClick={onBack} className="mb-3 md:hidden">
          <ArrowLeft /> Back
        </Button>
        <ErrorNotice error={error} onRetry={() => mutate()} />
      </div>
    );
  }
  if (isLoading || !customer) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-16 w-1/2" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const location = [customer.city, customer.country].filter(Boolean).join(", ");
  const social = Object.entries(customer.social_profiles);
  const custom = Object.entries(customer.custom_attributes);

  return (
    <div className="flex h-full flex-col">
      <header className="flex shrink-0 items-center gap-3 border-b px-3 py-3 sm:px-5">
        <Button variant="ghost" size="icon-sm" aria-label="Back to customers" onClick={onBack} className="md:hidden">
          <ArrowLeft />
        </Button>
        <CustomerAvatar name={customer.name} className="size-11 text-sm" />
        <div className="min-w-0 flex-1">
          <h2 dir="auto" className="truncate text-base font-semibold leading-tight">
            {customer.name}
          </h2>
          <p className="truncate text-[12px] text-muted-foreground">
            {[customer.company, location].filter(Boolean).join(" · ") ||
              `Customer since ${customer.first_seen_at ? new Date(customer.first_seen_at).toLocaleDateString() : "unknown"}`}
          </p>
        </div>
        {customer.blocked && (
          <span className="shrink-0 rounded-full bg-destructive/10 px-2 py-0.5 text-[11px] font-medium text-destructive">
            Blocked
          </span>
        )}
        <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
          <RefreshCw className={cn(refreshing && "animate-spin")} />
          <span className="hidden sm:inline">Refresh</span>
        </Button>
      </header>

      <div className="scroll-quiet flex-1 overflow-y-auto">
        <div className="mx-auto grid w-full max-w-5xl gap-4 px-3 py-5 sm:px-5 lg:grid-cols-5">
          <div className="space-y-4 lg:col-span-2">
            <Card title="Contact">
              <dl className="space-y-3 text-[13px]">
                <Field icon={Phone} label="Phone">
                  {customer.phone ? (
                    <a href={`tel:${customer.phone}`} dir="ltr" className="underline-offset-4 hover:underline">
                      {customer.phone}
                    </a>
                  ) : null}
                </Field>
                <Field icon={Mail} label="Email">
                  {customer.email ? (
                    <a href={`mailto:${customer.email}`} className="break-all underline-offset-4 hover:underline">
                      {customer.email}
                    </a>
                  ) : null}
                </Field>
                <Field icon={MapPin} label="Location">
                  {location || null}
                </Field>
                <Field icon={Building2} label="Company">
                  {customer.company}
                </Field>
              </dl>
            </Card>

            <Card title="Activity">
              <dl className="grid grid-cols-2 gap-3 text-[13px]">
                <Stat label="Conversations" value={customer.conversation_count} />
                <Stat label="Open now" value={customer.open_conversations} />
                <Stat
                  label="Last message"
                  value={customer.last_message_at ? `${relativeTime(customer.last_message_at)} ago` : "Never"}
                />
                <Stat
                  label="First contact"
                  value={customer.first_seen_at ? new Date(customer.first_seen_at).toLocaleDateString() : "Unknown"}
                />
              </dl>
              <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1.5 border-t pt-3">
                {customer.channels.length ? (
                  customer.channels.map((channel) => <ChannelTag key={channel} channel={channel} />)
                ) : (
                  <span className="text-[12px] text-muted-foreground">No channel recorded yet</span>
                )}
              </div>
            </Card>

            {(customer.description || social.length > 0 || custom.length > 0 || customer.identifier) && (
              <Card title="More details">
                <dl className="space-y-3 text-[13px]">
                  {customer.description && (
                    <div>
                      <dt className="text-[12px] text-muted-foreground">About</dt>
                      <dd dir="auto" className="mt-0.5 whitespace-pre-wrap">
                        {customer.description}
                      </dd>
                    </div>
                  )}
                  {customer.identifier && <KeyValue label="Identifier" value={customer.identifier} />}
                  {social.map(([network, handle]) => (
                    <KeyValue key={network} label={network} value={handle} />
                  ))}
                  {custom.map(([key, value]) => (
                    <KeyValue key={key} label={key.replace(/_/g, " ")} value={String(value)} />
                  ))}
                </dl>
              </Card>
            )}
          </div>

          <div className="lg:col-span-3">
            <Card title="Conversations" flush>
              {customer.conversations.length === 0 ? (
                <p className="px-4 py-8 text-center text-[13px] text-muted-foreground">No conversations yet.</p>
              ) : (
                <ul className="divide-y">
                  {customer.conversations.map((conversation) => (
                    <li key={conversation.id}>
                      <Link
                        href={`/inbox?c=${conversation.id}`}
                        className="flex items-start gap-3 px-4 py-3 outline-none transition-colors hover:bg-muted/60 focus-visible:bg-muted/60"
                      >
                        <MessageSquare className="mt-0.5 size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} />
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-2">
                            <ChannelTag channel={conversation.channel} />
                            {conversation.inbox_name && (
                              <span className="truncate text-[11px] text-muted-foreground">· {conversation.inbox_name}</span>
                            )}
                            <span
                              className={cn(
                                "ml-auto shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
                                conversation.status === "resolved"
                                  ? "bg-muted text-muted-foreground"
                                  : "bg-brand-soft text-brand",
                              )}
                            >
                              {conversation.status}
                            </span>
                          </span>
                          <span dir="auto" className="mt-1 block truncate text-[13px]">
                            {conversation.last_message ? (
                              <>
                                {conversation.last_message.direction === "outbound" && (
                                  <span className="text-muted-foreground">You: </span>
                                )}
                                {conversation.last_message.preview}
                              </>
                            ) : (
                              <span className="text-muted-foreground">No messages yet</span>
                            )}
                          </span>
                          <span className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                            <Clock className="size-3" />
                            {relativeTime(conversation.last_message?.at ?? conversation.updated_at)} ago
                            {!conversation.ai_enabled && " · AI paused"}
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

function Card({ title, children, flush }: { title: string; children: React.ReactNode; flush?: boolean }) {
  return (
    <section className="overflow-hidden rounded-xl border bg-card">
      <h3 className="border-b px-4 py-2.5 text-[13px] font-semibold">{title}</h3>
      <div className={flush ? "" : "p-4"}>{children}</div>
    </section>
  );
}

function Field({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} />
      <div className="min-w-0">
        <dt className="text-[12px] text-muted-foreground">{label}</dt>
        <dd dir="auto" className="mt-0.5">
          {children || <span className="text-muted-foreground/70">Not shared</span>}
        </dd>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-[12px] text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-[12px] capitalize text-muted-foreground">{label}</dt>
      <dd dir="auto" className="min-w-0 truncate text-right">
        {value}
      </dd>
    </div>
  );
}

function EmptyList({ filtered, onSync }: { filtered: boolean; onSync: () => void }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <span className="flex size-10 items-center justify-center rounded-xl bg-brand-soft text-brand">
        <Users className="size-5" strokeWidth={1.75} />
      </span>
      <p className="mt-3 text-sm font-medium">{filtered ? "No customer matches" : "No customers yet"}</p>
      <p className="mt-1 max-w-xs text-[13px] text-muted-foreground">
        {filtered
          ? "Try another name, number or channel."
          : "Customers appear here as soon as they write in. Sync to bring in everyone who wrote before."}
      </p>
      {!filtered && (
        <Button size="sm" className="mt-4" onClick={onSync}>
          <RefreshCw />
          Sync from Chatwoot
        </Button>
      )}
    </div>
  );
}

function NothingSelected() {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-muted/30 px-6 text-center">
      <span className="flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
        <Users className="size-5" strokeWidth={1.75} />
      </span>
      <p className="mt-4 text-sm font-medium">Select a customer</p>
      <p className="mt-1 max-w-xs text-[13px] text-muted-foreground">
        See their contact details, the channels they use, and every conversation you have had with them.
      </p>
    </div>
  );
}
