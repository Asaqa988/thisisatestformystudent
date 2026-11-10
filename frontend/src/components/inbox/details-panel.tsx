import { CustomerAvatar } from "@/components/customer-avatar";
import { channelLabel, relativeTime } from "@/lib/format";
import type { Conversation } from "@/lib/types";

/** Context about the selected conversation. Grows into a customer profile once the CRM is connected. */
export function DetailsPanel({ conversation }: { conversation: Conversation }) {
  const { contact } = conversation;

  return (
    <div className="scroll-quiet flex h-full flex-col overflow-y-auto">
      <div className="flex flex-col items-center border-b px-4 py-6 text-center">
        <CustomerAvatar name={contact.name} className="size-12 text-sm" />
        <p className="mt-3 text-sm font-semibold">{contact.name}</p>
        <p className="text-[12px] text-muted-foreground">{contact.email ?? "No email on file"}</p>
      </div>

      <dl className="space-y-3 border-b px-4 py-4 text-[13px]">
        <Row label="Channel" value={channelLabel(conversation.channel)} />
        <Row label="Inbox" value={conversation.inbox_name ?? "Unknown"} />
        <Row label="Status" value={<span className="capitalize">{conversation.status}</span>} />
        <Row label="Last activity" value={relativeTime(conversation.updated_at) || "Unknown"} />
      </dl>

      <dl className="space-y-3 border-b px-4 py-4 text-[13px]">
        <Row label="Source" value={<span className="capitalize">{conversation.source}</span>} />
        <Row label="Source id" value={<Mono>#{conversation.external_id}</Mono>} />
        <Row label="NEXUS id" value={<Mono>{conversation.id.slice(0, 8)}</Mono>} />
      </dl>

      <p className="px-4 py-4 text-[12px] leading-relaxed text-muted-foreground">
        Deals, tasks and the full customer history appear here once Twenty CRM and Plane are connected.
      </p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 truncate text-right font-medium">{value}</dd>
    </div>
  );
}

function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-[12px]">{children}</span>;
}
