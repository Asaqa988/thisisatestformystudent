"use client";

import { ArrowLeft, Bot, Eye, Loader2, Play, ShieldCheck, Trash2, Workflow } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAutomation, useAutomations } from "@/hooks/use-nexus";
import { api, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { AutomationDetail, AutomationRun, AutomationSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

import { RUN_STATUS, RunCard } from "./run-card";
import { VoiceComposer } from "./voice-composer";

const BUILD_STATUS = {
  building: { label: "Crew is building", className: "bg-brand-soft text-brand" },
  ready: { label: "Ready", className: "bg-positive-soft text-positive" },
  unsupported: { label: "Not possible yet", className: "bg-muted text-muted-foreground" },
  failed: { label: "Build failed", className: "bg-destructive/10 text-destructive" },
} as const;

export function AutomationsView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams.get("id");
  const list = useAutomations();
  const [submitting, setSubmitting] = useState(false);

  function select(id: string | null) {
    router.replace(id ? `/automations?id=${id}` : "/automations", { scroll: false });
  }

  async function create(request: string, language: string) {
    setSubmitting(true);
    try {
      const created = await api<AutomationDetail>("/api/v1/automations", {
        method: "POST",
        body: JSON.stringify({ request, language }),
      });
      await list.mutate();
      select(created.id);
      toast("The crew is building your automation…");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not send the request");
    } finally {
      setSubmitting(false);
    }
  }

  const automations = list.data?.items ?? [];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Automations"
        description="Say what you need. An AI crew builds it from NEXUS tools."
        className={cn(selectedId && "hidden md:flex")}
      />

      <div className="flex min-h-0 flex-1">
        <section
          aria-label="Saved automations"
          className={cn(
            "w-full shrink-0 flex-col border-r md:flex md:w-80 lg:w-[22rem]",
            selectedId ? "hidden" : "flex",
          )}
        >
          <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
            {list.error ? (
              <div className="p-3">
                <ErrorNotice error={list.error} onRetry={() => list.mutate()} />
              </div>
            ) : list.isLoading ? (
              <div className="space-y-3 p-3">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : automations.length === 0 ? (
              <p className="px-6 py-12 text-center text-[13px] text-muted-foreground">
                No automations yet. Describe your first one on the right.
              </p>
            ) : (
              <ul>
                {automations.map((automation) => (
                  <li key={automation.id}>
                    <AutomationRow
                      automation={automation}
                      selected={automation.id === selectedId}
                      onSelect={select}
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="shrink-0 border-t p-3 md:hidden">
            <Button className="w-full" onClick={() => select(null)} variant="outline">
              New automation
            </Button>
          </div>
        </section>

        <section className={cn("min-w-0 flex-1 md:block", selectedId ? "block" : "hidden md:block")}>
          <div className="scroll-quiet h-full overflow-y-auto">
            <div className="mx-auto w-full max-w-3xl space-y-5 px-3 py-5 sm:px-6">
              {selectedId ? (
                <>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => select(null)}>
                      <ArrowLeft />
                      New automation
                    </Button>
                  </div>
                  <AutomationDetailView
                    automationId={selectedId}
                    onChanged={() => list.mutate()}
                    onDeleted={() => {
                      void list.mutate();
                      select(null);
                    }}
                  />
                </>
              ) : (
                <>
                  <VoiceComposer busy={submitting} onSubmit={create} />
                  <HowItWorks />
                </>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function AutomationRow({
  automation,
  selected,
  onSelect,
}: {
  automation: AutomationSummary;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const runStatus = automation.last_run_status ? RUN_STATUS[automation.last_run_status] : null;
  const build = BUILD_STATUS[automation.status];
  const badge = automation.status === "ready" && runStatus ? runStatus : build;
  return (
    <button
      type="button"
      onClick={() => onSelect(automation.id)}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "relative flex w-full items-start gap-3 border-b px-3 py-3 text-left outline-none transition-colors focus-visible:bg-muted/70",
        selected ? "bg-accent" : "hover:bg-muted/60",
      )}
    >
      {selected && <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-brand" />}
      <Workflow className="mt-0.5 size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span dir="auto" className="truncate text-[13px] font-medium">
            {automation.title}
          </span>
          <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
            {relativeTime(automation.last_run_at ?? automation.created_at)}
          </span>
        </span>
        <span dir="auto" className="mt-0.5 block truncate text-[12px] text-muted-foreground">
          “{automation.request_text}”
        </span>
        <span className="mt-1.5 flex items-center gap-2">
          <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", badge.className)}>
            {badge.label}
          </span>
          {automation.needs_approval && (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <ShieldCheck className="size-3" /> approval
            </span>
          )}
        </span>
      </span>
    </button>
  );
}

function AutomationDetailView({
  automationId,
  onChanged,
  onDeleted,
}: {
  automationId: string;
  onChanged: () => void;
  onDeleted: () => void;
}) {
  const { data: automation, error, mutate } = useAutomation(automationId);
  const [running, setRunning] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (error) return <ErrorNotice error={error} onRetry={() => mutate()} />;
  if (!automation) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  async function runAgain() {
    setRunning(true);
    try {
      await api<AutomationRun>(`/api/v1/automations/${automationId}/run`, { method: "POST" });
      await mutate();
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not run it");
    } finally {
      setRunning(false);
    }
  }

  async function remove() {
    try {
      await api(`/api/v1/automations/${automationId}`, { method: "DELETE" });
      toast("Automation deleted");
      onDeleted();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete it");
    }
  }

  const build = BUILD_STATUS[automation.status];
  const refresh = () => {
    void mutate();
    onChanged();
  };

  return (
    <div className="space-y-4">
      <section className="rounded-xl border bg-card p-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 dir="auto" className="text-base font-semibold leading-snug">
              {automation.title}
            </h2>
            <p dir="auto" className="mt-1 text-[13px] text-muted-foreground">
              You asked: “{automation.request_text}”
            </p>
          </div>
          <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium", build.className)}>
            {build.label}
          </span>
        </div>

        {automation.status === "building" && (
          <div className="mt-4 flex items-center gap-2.5 rounded-lg bg-brand-soft/50 px-3 py-2.5 text-[13px]">
            <Loader2 className="size-4 animate-spin text-brand" />
            The architect is designing the plan, then the reviewer checks it. This takes up to a minute.
          </div>
        )}
        {automation.summary && (
          <p dir="auto" className="mt-3 text-sm leading-relaxed">
            {automation.summary}
          </p>
        )}
        {automation.error && (
          <p
            dir="auto"
            className={cn(
              "mt-3 rounded-lg px-3 py-2 text-[13px]",
              automation.status === "unsupported" ? "bg-muted" : "bg-destructive/5 text-destructive",
            )}
          >
            {automation.error}
          </p>
        )}

        {automation.steps.length > 0 && (
          <ol className="mt-4 space-y-2">
            {automation.steps.map((step, index) => (
              <li key={step.id} className="flex items-start gap-2.5 text-[13px]">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-semibold tabular-nums">
                  {index + 1}
                </span>
                <span dir="auto" className="min-w-0 flex-1 break-words pt-px">
                  {step.description}
                </span>
                {step.kind === "action" ? (
                  <span className="shrink-0 rounded-full bg-attention-soft px-2 py-0.5 text-[11px] font-medium text-attention">
                    Needs approval
                  </span>
                ) : (
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                    <Eye className="size-3" /> Read only
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}

        {automation.review_notes && (
          <p dir="auto" className="mt-4 flex gap-2 border-t pt-3 text-[12px] text-muted-foreground">
            <Bot className="mt-px size-3.5 shrink-0" />
            Reviewer: {automation.review_notes}
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t pt-3">
          <span className="text-[11px] text-muted-foreground">
            {automation.input_tokens + automation.output_tokens > 0 &&
              `Built with ${(automation.input_tokens + automation.output_tokens).toLocaleString()} tokens · `}
            Run {automation.run_count} time{automation.run_count === 1 ? "" : "s"}
          </span>
          <div className="flex gap-2">
            {confirmDelete ? (
              <>
                <Button size="sm" variant="destructive" onClick={remove}>
                  Delete
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>
                  Keep
                </Button>
              </>
            ) : (
              <Button size="icon-sm" variant="ghost" aria-label="Delete automation" onClick={() => setConfirmDelete(true)}>
                <Trash2 />
              </Button>
            )}
            {automation.status === "ready" && (
              <Button size="sm" onClick={runAgain} disabled={running}>
                <Play />
                {running ? "Running" : "Run again"}
              </Button>
            )}
          </div>
        </div>
      </section>

      {automation.runs.map((run, index) => (
        <RunCard key={run.id} run={run} title={index === 0 ? "Latest run" : "Earlier run"} onChanged={refresh} />
      ))}
    </div>
  );
}

function HowItWorks() {
  return (
    <section className="rounded-xl border bg-card p-4 text-[13px] leading-relaxed">
      <h3 className="font-semibold">How it works</h3>
      <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-muted-foreground">
        <li>You say or type what you need, in Arabic or English.</li>
        <li>
          An AI crew of two agents works on it: an <span className="text-foreground">architect</span> designs a plan
          from NEXUS tools, and a <span className="text-foreground">reviewer</span> checks it.
        </li>
        <li>Reading and exporting run straight away. You get files to download, such as Excel sheets.</li>
        <li>
          Anything that messages customers or changes data shows you exactly what will happen and to whom, and waits
          for your approval.
        </li>
        <li>Every automation is saved. Run it again any time on fresh data, with no AI cost.</li>
      </ol>
    </section>
  );
}
