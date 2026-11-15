"use client";

import { Check, Download, FileSpreadsheet, ShieldAlert, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { channelLabel, relativeTime } from "@/lib/format";
import type { AutomationRun, PendingAction, RunStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export const RUN_STATUS: Record<RunStatus, { label: string; className: string }> = {
  running: { label: "Running", className: "bg-brand-soft text-brand" },
  awaiting_approval: { label: "Needs approval", className: "bg-attention-soft text-attention" },
  succeeded: { label: "Done", className: "bg-positive-soft text-positive" },
  failed: { label: "Failed", className: "bg-destructive/10 text-destructive" },
  rejected: { label: "Rejected", className: "bg-muted text-muted-foreground" },
};

export function fileUrl(fileId: string) {
  return `/api/nexus/api/v1/automation-files/${fileId}`;
}

function formatSize(bytes: number) {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
}

/** One run: what it produced, files to download, and actions waiting for approval. */
export function RunCard({
  run,
  title,
  onChanged,
}: {
  run: AutomationRun;
  title?: string;
  onChanged: () => void;
}) {
  const status = RUN_STATUS[run.status];
  return (
    <article className="overflow-hidden rounded-xl border bg-card">
      <header className="flex items-center gap-2 border-b px-4 py-2.5">
        <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{title ?? "Run"}</span>
        <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium", status.className)}>
          {status.label}
        </span>
        <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
          {relativeTime(run.started_at)} ago
        </span>
      </header>

      <div className="space-y-3 p-4">
        <ul className="space-y-1.5">
          {run.outputs.map((output) => (
            <li key={`${output.step_id}-${output.kind}`} className="flex items-start gap-2 text-[13px]">
              <span
                className={cn(
                  "mt-1.5 size-1.5 shrink-0 rounded-full",
                  output.kind === "delivery_failure"
                    ? "bg-destructive"
                    : output.kind === "action"
                      ? "bg-attention"
                      : "bg-positive",
                )}
              />
              <span dir="auto" className={cn(output.kind === "delivery_failure" && "text-destructive")}>
                {output.summary}
              </span>
            </li>
          ))}
        </ul>

        {run.files.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {run.files.map((file) => (
              <a
                key={file.id}
                href={fileUrl(file.id)}
                download={file.filename}
                className="inline-flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-[13px] font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
              >
                <FileSpreadsheet className="size-4 text-positive" strokeWidth={1.75} />
                {file.filename}
                <span className="text-[11px] font-normal text-muted-foreground">{formatSize(file.size)}</span>
                <Download className="size-3.5 text-muted-foreground" />
              </a>
            ))}
          </div>
        )}

        {run.error && (
          <p className="rounded-lg bg-destructive/5 px-3 py-2 text-[12px] text-destructive">{run.error}</p>
        )}

        {run.status === "awaiting_approval" && <Approval run={run} onChanged={onChanged} />}
      </div>
    </article>
  );
}

function Approval({ run, onChanged }: { run: AutomationRun; onChanged: () => void }) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);

  async function decide(decision: "approve" | "reject") {
    setBusy(decision);
    try {
      const result = await api<AutomationRun>(`/api/v1/automation-runs/${run.id}/${decision}`, { method: "POST" });
      if (decision === "reject") toast("Rejected. Nothing was changed.");
      else if (result.status === "succeeded" && !result.error) toast.success("Approved and done");
      else toast.warning(result.error ?? "Finished with problems");
      onChanged();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not record the decision");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-xl border border-attention/40 bg-attention-soft/40 p-3.5">
      <p className="flex items-center gap-1.5 text-[13px] font-semibold">
        <ShieldAlert className="size-4 text-attention" />
        Approve before anything happens
      </p>
      <div className="mt-3 space-y-3">
        {run.pending_actions.map((action) => (
          <ActionPreview key={action.step_id} action={action} />
        ))}
      </div>
      <div className="mt-3.5 flex flex-wrap gap-2">
        <Button size="sm" onClick={() => decide("approve")} disabled={busy !== null}>
          <Check />
          {busy === "approve" ? "Working…" : "Approve and run"}
        </Button>
        <Button size="sm" variant="outline" onClick={() => decide("reject")} disabled={busy !== null}>
          <X />
          Reject
        </Button>
      </div>
    </div>
  );
}

function ActionPreview({ action }: { action: PendingAction }) {
  const extra = action.target_count - action.targets.length;
  return (
    <div className="rounded-lg bg-background/80 p-3 text-[13px] ring-1 ring-border">
      <p className="font-medium">
        {action.label} · {action.target_count} conversation{action.target_count === 1 ? "" : "s"}
      </p>
      {action.text && (
        <blockquote dir="auto" className="mt-2 whitespace-pre-wrap border-l-2 border-attention/60 pl-2.5 text-[13px]">
          {action.text}
        </blockquote>
      )}
      {action.status && <p className="mt-1.5 text-muted-foreground">New status: {action.status}</p>}
      {action.enabled !== undefined && action.tool === "set_ai" && (
        <p className="mt-1.5 text-muted-foreground">AI agent: {action.enabled ? "on" : "off"}</p>
      )}
      <ul className="mt-2 flex flex-wrap gap-1.5">
        {action.targets.map((target) => (
          <li
            key={target.conversation_id}
            dir="auto"
            className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
          >
            {target.name} · {channelLabel(target.channel)}
          </li>
        ))}
        {extra > 0 && <li className="px-1 text-[11px] text-muted-foreground">and {extra} more</li>}
      </ul>
      {action.skipped && action.skipped.length > 0 && (
        <div className="mt-2.5 border-t pt-2 text-[12px] text-muted-foreground">
          <p>
            Left out ({action.skipped.length}): Meta only allows replies within 24 hours of the customer&apos;s last
            message, so these would not be delivered.
          </p>
          <p dir="auto" className="mt-1">
            {action.skipped.map((s) => s.name).join(" · ")}
          </p>
        </div>
      )}
    </div>
  );
}
