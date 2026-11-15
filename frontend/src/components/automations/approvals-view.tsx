"use client";

import { ShieldCheck } from "lucide-react";
import Link from "next/link";

import { ErrorNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useApprovals } from "@/hooks/use-nexus";

import { RunCard } from "./run-card";

/** Everything waiting for a person to say yes or no. */
export function ApprovalsView() {
  const approvals = useApprovals();
  const items = approvals.data?.items ?? [];

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Approvals" description="Actions waiting for a person to approve them" />
      <div className="scroll-quiet flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl space-y-4 px-3 py-5 sm:px-6">
          {approvals.error ? (
            <ErrorNotice error={approvals.error} onRetry={() => approvals.mutate()} />
          ) : approvals.isLoading ? (
            <Skeleton className="h-48 w-full rounded-xl" />
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center rounded-xl border bg-card px-6 py-14 text-center">
              <span className="flex size-10 items-center justify-center rounded-xl bg-positive-soft text-positive">
                <ShieldCheck className="size-5" strokeWidth={1.75} />
              </span>
              <p className="mt-3 text-sm font-medium">Nothing is waiting for you</p>
              <p className="mt-1 max-w-sm text-[13px] text-muted-foreground">
                When an automation wants to message customers or change data, it appears here first.
              </p>
              <Link href="/automations" className="mt-4 text-[13px] font-medium underline-offset-4 hover:underline">
                Go to Automations
              </Link>
            </div>
          ) : (
            items.map((run) => (
              <div key={run.id} className="space-y-1.5">
                <Link
                  href={`/automations?id=${run.automation_id}`}
                  className="text-[12px] text-muted-foreground underline-offset-4 hover:underline"
                >
                  From the automation
                </Link>
                <RunCard run={run} title={run.automation_title ?? "Automation"} onChanged={() => approvals.mutate()} />
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
