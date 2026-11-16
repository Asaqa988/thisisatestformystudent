"use client";

import { ArrowLeft, Clapperboard, Loader2, Sparkles, Trash2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdVideos } from "@/hooks/use-nexus";
import { api, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { AdVideo } from "@/lib/types";
import { cn } from "@/lib/utils";

import { AdPlayer } from "./ad-player";
import type { AdStoryboard } from "./motion";

const STATUS = {
  building: { label: "Writing", className: "bg-brand-soft text-brand" },
  ready: { label: "Ready", className: "bg-positive-soft text-positive" },
  failed: { label: "Failed", className: "bg-destructive/10 text-destructive" },
} as const;

const IDEAS = ["Our most popular package", "A limited-time offer", "Why clients choose us"];

function slug(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "ad";
}

export function AdsView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const list = useAdVideos();
  const ads = list.data?.items ?? [];
  const selectedId = searchParams.get("id") ?? ads[0]?.id ?? null;
  const selected = ads.find((ad) => ad.id === selectedId) ?? null;
  const [brief, setBrief] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  function select(id: string | null) {
    router.replace(id ? `/campaigns?id=${id}` : "/campaigns", { scroll: false });
  }

  async function create() {
    setSubmitting(true);
    try {
      const created = await api<AdVideo>("/api/v1/ad-videos", {
        method: "POST",
        body: JSON.stringify({ brief: brief.trim() || null }),
      });
      setBrief("");
      await list.mutate();
      select(created.id);
      toast("Claude is writing your ad from the Knowledge Base…");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not start the ad");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: string) {
    try {
      await api(`/api/v1/ad-videos/${id}`, { method: "DELETE" });
      setConfirmDelete(null);
      await list.mutate();
      select(null);
      toast("Ad deleted");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not delete it");
    }
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Campaigns"
        description="15-second motion-graphic ads, written by Claude from your Knowledge Base."
      />

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <section aria-label="Ad videos" className="flex shrink-0 flex-col border-b md:w-80 md:border-b-0 md:border-r lg:w-[22rem]">
          <form
            className="space-y-2 border-b p-3"
            onSubmit={(event) => {
              event.preventDefault();
              void create();
            }}
          >
            <label htmlFor="ad-brief" className="text-[12px] font-medium text-muted-foreground">
              What should the ad focus on? (optional)
            </label>
            <textarea
              id="ad-brief"
              value={brief}
              onChange={(event) => setBrief(event.target.value)}
              maxLength={500}
              rows={2}
              placeholder="e.g. the Growth package, for small restaurants"
              className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <div className="flex flex-wrap gap-1.5">
              {IDEAS.map((idea) => (
                <button
                  key={idea}
                  type="button"
                  onClick={() => setBrief(idea)}
                  className="rounded-full border px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-muted"
                >
                  {idea}
                </button>
              ))}
            </div>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? <Loader2 className="animate-spin" /> : <Sparkles />}
              Create ad video
            </Button>
          </form>

          <div className="scroll-quiet max-h-60 min-h-0 flex-1 overflow-y-auto md:max-h-none">
            {list.error ? (
              <div className="p-3">
                <ErrorNotice error={list.error} onRetry={() => list.mutate()} />
              </div>
            ) : list.isLoading ? (
              <div className="space-y-3 p-3">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : ads.length === 0 ? (
              <p className="px-6 py-10 text-center text-[13px] text-muted-foreground">
                No ads yet. Create your first one above.
              </p>
            ) : (
              <ul>
                {ads.map((ad) => {
                  const status = STATUS[ad.status];
                  return (
                    <li key={ad.id}>
                      <button
                        type="button"
                        onClick={() => select(ad.id)}
                        aria-current={ad.id === selectedId ? "true" : undefined}
                        className={cn(
                          "relative flex w-full items-start gap-3 border-b px-3 py-3 text-left outline-none transition-colors focus-visible:bg-muted/70",
                          ad.id === selectedId ? "bg-accent" : "hover:bg-muted/60",
                        )}
                      >
                        {ad.id === selectedId && <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-brand" />}
                        <Clapperboard className="mt-0.5 size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} />
                        <span className="min-w-0 flex-1">
                          <span className="flex items-baseline justify-between gap-2">
                            <span className="truncate text-[13px] font-medium">{ad.title}</span>
                            <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
                              {relativeTime(ad.created_at)}
                            </span>
                          </span>
                          <span className="mt-1.5 flex items-center gap-2">
                            <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", status.className)}>
                              {status.label}
                            </span>
                            {ad.status === "ready" && "duration" in ad.storyboard && (
                              <span className="text-[11px] tabular-nums text-muted-foreground">
                                {ad.storyboard.duration.toFixed(1)} s · 9:16
                              </span>
                            )}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        <section className="scroll-quiet min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-4xl px-3 py-5 sm:px-6">
            {searchParams.get("id") && (
              <Button variant="ghost" size="sm" className="mb-3 md:hidden" onClick={() => select(null)}>
                <ArrowLeft />
                All ads
              </Button>
            )}
            {!selected ? (
              !list.isLoading && <Empty />
            ) : selected.status === "building" ? (
              <div className="flex flex-col items-center gap-3 rounded-xl border bg-card px-6 py-16 text-center">
                <Loader2 className="size-6 animate-spin text-brand" />
                <p className="text-sm font-medium">Claude is writing the storyboard</p>
                <p className="max-w-sm text-[13px] text-muted-foreground">
                  It reads the Knowledge Base and picks the facts, scenes and colours. This takes 10 to 30 seconds.
                </p>
              </div>
            ) : selected.status === "failed" ? (
              <div className="space-y-3 rounded-xl border bg-card p-5">
                <h2 className="text-base font-semibold">{selected.title}</h2>
                <p className="rounded-lg bg-destructive/5 px-3 py-2 text-[13px] text-destructive">{selected.error}</p>
                <DeleteButton id={selected.id} confirm={confirmDelete} setConfirm={setConfirmDelete} onDelete={remove} />
              </div>
            ) : (
              <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
                <AdPlayer
                  key={selected.id}
                  storyboard={selected.storyboard as AdStoryboard}
                  filename={slug(selected.title)}
                />
                <AdFacts ad={selected}>
                  <DeleteButton id={selected.id} confirm={confirmDelete} setConfirm={setConfirmDelete} onDelete={remove} />
                </AdFacts>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function AdFacts({ ad, children }: { ad: AdVideo; children: React.ReactNode }) {
  const board = ad.storyboard as AdStoryboard;
  return (
    <aside className="min-w-0 flex-1 space-y-4 rounded-xl border bg-card p-4 text-[13px]">
      <div>
        <h2 className="text-base font-semibold leading-snug">{ad.title}</h2>
        {ad.brief && <p className="mt-1 text-muted-foreground">You asked for: “{ad.brief}”</p>}
      </div>
      <div>
        <h3 className="text-[12px] font-medium uppercase tracking-wider text-muted-foreground">Scenes</h3>
        <ol className="mt-2 space-y-1.5">
          {board.scenes.map((scene, i) => (
            <li key={i} className="flex gap-2">
              <span className="w-12 shrink-0 text-[11px] tabular-nums text-muted-foreground">{scene.duration.toFixed(1)} s</span>
              <span className="min-w-0">
                <span className="mr-1.5 rounded bg-muted px-1.5 py-px text-[10px] font-medium uppercase">{scene.kind}</span>
                {scene.kind === "price"
                  ? `${scene.price_amount} ${scene.price_currency} ${scene.price_period}`.trim()
                  : scene.headline}
                {scene.items.length > 0 && <span className="text-muted-foreground"> — {scene.items.join(", ")}</span>}
              </span>
            </li>
          ))}
        </ol>
      </div>
      {board.facts_used.length > 0 && (
        <div>
          <h3 className="text-[12px] font-medium uppercase tracking-wider text-muted-foreground">
            Facts from the Knowledge Base
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-muted-foreground">
            {board.facts_used.map((fact, i) => (
              <li key={i}>{fact}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex items-center justify-between gap-2 border-t pt-3">
        <span className="text-[11px] text-muted-foreground">
          Written with {(ad.input_tokens + ad.output_tokens).toLocaleString()} tokens · {relativeTime(ad.created_at)}
        </span>
        {children}
      </div>
    </aside>
  );
}

function DeleteButton({
  id,
  confirm,
  setConfirm,
  onDelete,
}: {
  id: string;
  confirm: string | null;
  setConfirm: (id: string | null) => void;
  onDelete: (id: string) => void;
}) {
  return confirm === id ? (
    <span className="flex gap-2">
      <Button size="sm" variant="destructive" onClick={() => onDelete(id)}>
        Delete
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>
        Keep
      </Button>
    </span>
  ) : (
    <Button size="icon-sm" variant="ghost" aria-label="Delete ad" onClick={() => setConfirm(id)}>
      <Trash2 />
    </Button>
  );
}

function Empty() {
  return (
    <section className="rounded-xl border bg-card p-5 text-[13px] leading-relaxed">
      <h3 className="font-semibold">How ad videos work</h3>
      <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-muted-foreground">
        <li>Optionally say what the ad should focus on, then press Create.</li>
        <li>Claude reads your Knowledge Base and writes a storyboard: a hook, benefits, a price, a call to action. It only uses facts from your articles.</li>
        <li>NEXUS animates it here as a 9:16 motion graphic, at most 15 seconds, ready for Reels, Stories and TikTok.</li>
        <li>Every ad is saved on this page. Play it any time, or download it as a video file.</li>
      </ol>
    </section>
  );
}
