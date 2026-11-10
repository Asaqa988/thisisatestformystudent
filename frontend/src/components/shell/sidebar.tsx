"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo } from "@/components/brand/logo";
import { useChatwootStatus, useConversations } from "@/hooks/use-nexus";
import { cn } from "@/lib/utils";

import { isActive, NAV_GROUPS, type NavItem, SETTINGS_ITEM } from "./nav-config";

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { data } = useConversations();

  // Conversations whose last message came from the customer: a human or an
  // agent still owes them an answer.
  const awaiting =
    data?.items.filter(
      (c) => c.status !== "resolved" && c.last_message?.direction === "inbound",
    ).length ?? 0;

  return (
    <div className="flex h-full w-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 shrink-0 items-center px-4">
        <Link href="/" onClick={onNavigate} className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Logo />
        </Link>
      </div>

      <div className="mx-3 mb-2 flex items-center gap-2.5 rounded-lg border border-sidebar-border bg-background/60 px-2.5 py-2">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-attention-soft text-[11px] font-semibold text-attention">
          A
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[13px] font-medium leading-tight text-foreground">
            Acme Agency
          </span>
          <span className="block truncate text-[11px] leading-tight text-muted-foreground">
            Demo workspace
          </span>
        </span>
      </div>

      <nav aria-label="Main" className="scroll-quiet flex-1 overflow-y-auto px-3 pb-3">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mt-4 first:mt-2">
            <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => (
                <li key={item.href}>
                  <NavLink
                    item={item}
                    active={isActive(pathname, item.href)}
                    count={item.href === "/inbox" ? awaiting : 0}
                    onNavigate={onNavigate}
                  />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 space-y-2 border-t border-sidebar-border p-3">
        <NavLink
          item={SETTINGS_ITEM}
          active={isActive(pathname, SETTINGS_ITEM.href)}
          count={0}
          onNavigate={onNavigate}
        />
        <ConnectionStatus />
      </div>
    </div>
  );
}

function NavLink({
  item,
  active,
  count,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  count: number;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] font-medium outline-none transition-colors",
        "focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/80 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
      )}
    >
      {active && (
        <span aria-hidden className="absolute -left-3 top-1.5 h-5 w-[3px] rounded-r-full bg-brand" />
      )}
      <Icon
        className={cn("size-4 shrink-0", active ? "text-brand" : "text-muted-foreground group-hover:text-foreground")}
        strokeWidth={1.75}
      />
      <span className="truncate">{item.label}</span>

      {count > 0 && (
        <span
          className="ml-auto flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-attention-soft px-1 text-[11px] font-semibold tabular-nums text-attention"
          aria-label={`${count} awaiting reply`}
        >
          {count}
        </span>
      )}
      {item.upcoming && (
        <span className="ml-auto rounded-full border border-sidebar-border px-1.5 py-px text-[10px] font-medium text-muted-foreground">
          Soon
        </span>
      )}
    </Link>
  );
}

function ConnectionStatus() {
  const { data, error } = useChatwootStatus();

  let tone: "ok" | "warn" | "down" | "idle" = "idle";
  let label = "Checking Chatwoot…";

  if (error) {
    tone = "down";
    label = "Backend unreachable";
  } else if (data) {
    if (!data.configured) {
      tone = "warn";
      label = "Chatwoot not configured";
    } else if (data.ok) {
      tone = "ok";
      label = "Chatwoot connected";
    } else {
      tone = "down";
      label = "Chatwoot not responding";
    }
  }

  return (
    <div
      className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[12px] text-muted-foreground"
      title={data?.detail ?? error?.message}
    >
      <span className="relative flex size-2">
        {tone === "ok" && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-positive opacity-50" />
        )}
        <span
          className={cn(
            "relative inline-flex size-2 rounded-full",
            tone === "ok" && "bg-positive",
            tone === "warn" && "bg-attention",
            tone === "down" && "bg-destructive",
            tone === "idle" && "bg-muted-foreground/40",
          )}
        />
      </span>
      <span className="truncate">{label}</span>
    </div>
  );
}
