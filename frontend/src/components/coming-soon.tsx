import { Check, type LucideIcon } from "lucide-react";

import { PageHeader } from "@/components/shell/page-header";

/**
 * A clearly marked placeholder for pages that later lessons build.
 * It says what the page will do and which system will power it, so students
 * can see where the course is heading without mistaking it for a broken page.
 */
export function ComingSoon({
  icon: Icon,
  title,
  summary,
  poweredBy,
  points,
}: {
  icon: LucideIcon;
  title: string;
  summary: string;
  poweredBy: string;
  points: string[];
}) {
  return (
    <div className="flex h-full flex-col">
      <PageHeader title={title} description="Upcoming feature" />

      <div className="scroll-quiet flex flex-1 items-start justify-center overflow-y-auto px-4 py-10 sm:px-6 sm:py-16">
        <div className="w-full max-w-xl">
          <div className="relative overflow-hidden rounded-2xl border bg-card p-6 sm:p-8">
            {/* A faint grid: this space is planned, not empty. */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 opacity-[0.5] [background-image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] [background-size:28px_28px] [mask-image:radial-gradient(ellipse_at_top_right,black,transparent_65%)]"
            />

            <div className="relative">
              <div className="flex items-center justify-between gap-3">
                <span className="flex size-10 items-center justify-center rounded-xl bg-brand-soft text-brand">
                  <Icon className="size-5" strokeWidth={1.75} />
                </span>
                <span className="rounded-full border border-dashed border-attention/50 bg-attention-soft px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider text-attention">
                  Not built yet
                </span>
              </div>

              <h2 className="mt-5 text-xl font-semibold tracking-tight">{title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{summary}</p>

              <ul className="mt-6 space-y-2.5">
                {points.map((point) => (
                  <li key={point} className="flex gap-2.5 text-sm">
                    <Check className="mt-0.5 size-4 shrink-0 text-muted-foreground/60" strokeWidth={2} />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-2 border-t pt-4 text-[13px] text-muted-foreground">
                <span>
                  Powered by <span className="font-medium text-foreground">{poweredBy}</span>
                </span>
                <span>Arrives in a later lesson</span>
              </div>
            </div>
          </div>

          <p className="mt-4 text-center text-[13px] text-muted-foreground">
            Lesson 01 builds the foundation: this shell, the Dashboard and the Unified Inbox.
          </p>
        </div>
      </div>
    </div>
  );
}
