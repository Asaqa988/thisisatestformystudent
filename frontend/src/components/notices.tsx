import { KeyRound, TriangleAlert } from "lucide-react";

import type { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Shown when the backend says Chatwoot credentials are missing.
 * A missing credential is a setup step, not a crash, so the page explains it.
 */
export function SetupNotice({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-xl border border-dashed border-attention/50 bg-attention-soft/60 p-5", className)}>
      <div className="flex items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-attention-soft text-attention">
          <KeyRound className="size-4" strokeWidth={1.75} />
        </span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Connect Chatwoot to see conversations</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
            NEXUS is running, but it has no Chatwoot credentials yet.
          </p>
          <ol className="mt-3 list-decimal space-y-1.5 pl-4 text-[13px] leading-relaxed">
            <li>
              Open Chatwoot, go to <span className="font-medium">Profile Settings</span> and copy the{" "}
              <span className="font-medium">Access Token</span>.
            </li>
            <li>
              Put it in <Code>.env</Code> as <Code>CHATWOOT_API_TOKEN</Code>.
            </li>
            <li>
              Run <Code>docker compose up -d backend</Code> to reload the backend.
            </li>
          </ol>
          <p className="mt-3 text-[12px] text-muted-foreground">
            Full steps are in <Code>docs/lessons/lesson-01.md</Code>.
          </p>
        </div>
      </div>
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-background/80 px-1 py-0.5 font-mono text-[12px] ring-1 ring-border">
      {children}
    </code>
  );
}

/** A plain statement of what failed, with a way to try again. */
export function ErrorNotice({
  error,
  onRetry,
  className,
}: {
  error: ApiError;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn("flex items-start gap-3 rounded-xl border border-destructive/25 bg-destructive/5 p-4", className)}
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" strokeWidth={1.75} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{error.message}</p>
        <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{error.code}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 rounded-md px-2 py-1 text-[13px] font-medium text-foreground underline-offset-4 hover:underline focus-visible:outline-2"
        >
          Try again
        </button>
      )}
    </div>
  );
}
