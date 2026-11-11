"use client";

import { BookOpen, FileText, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useKnowledge } from "@/hooks/use-nexus";
import { api, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { KnowledgeArticle } from "@/lib/types";
import { cn } from "@/lib/utils";

const NEW = "new";

/**
 * What the AI agent knows about the business. Every article is given to the
 * model, which may only answer from it. One topic per article works best.
 */
export function KnowledgeView() {
  const knowledge = useKnowledge();
  const articles = knowledge.data?.items ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected = articles.find((a) => a.id === selectedId) ?? null;
  const editing = selectedId === NEW ? null : selected;
  const showEditor = selectedId === NEW || selected !== null;

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Knowledge Base"
        description="What the AI agent may tell customers. It answers only from these articles."
        className={cn(showEditor && "hidden md:flex")}
        actions={
          <Button size="sm" onClick={() => setSelectedId(NEW)}>
            <Plus />
            New article
          </Button>
        }
      />

      <div className="flex min-h-0 flex-1">
        <section
          aria-label="Articles"
          className={cn(
            "w-full shrink-0 flex-col border-r md:flex md:w-80",
            showEditor ? "hidden" : "flex",
          )}
        >
          {knowledge.error ? (
            <div className="p-3">
              <ErrorNotice error={knowledge.error} onRetry={() => knowledge.mutate()} />
            </div>
          ) : knowledge.isLoading ? (
            <div className="space-y-3 p-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : articles.length === 0 ? (
            <EmptyList onCreate={() => setSelectedId(NEW)} />
          ) : (
            <>
              <ul className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
                {articles.map((article) => (
                  <li key={article.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(article.id)}
                      aria-current={article.id === selectedId ? "true" : undefined}
                      className={cn(
                        "relative flex w-full items-start gap-3 border-b px-3 py-3 text-left outline-none transition-colors focus-visible:bg-muted/70",
                        article.id === selectedId ? "bg-accent" : "hover:bg-muted/60",
                      )}
                    >
                      {article.id === selectedId && (
                        <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-brand" />
                      )}
                      <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} />
                      <span className="min-w-0 flex-1">
                        <span dir="auto" className="block truncate text-[13px] font-medium">
                          {article.title}
                        </span>
                        <span dir="auto" className="mt-0.5 block truncate text-[12px] text-muted-foreground">
                          {article.content}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="shrink-0 border-t px-3 py-2 text-[12px] text-muted-foreground">
                {articles.length} article{articles.length === 1 ? "" : "s"} ·{" "}
                {(knowledge.data?.total_chars ?? 0).toLocaleString()} characters
              </p>
            </>
          )}
        </section>

        <section aria-label="Editor" className={cn("min-w-0 flex-1 md:block", showEditor ? "block" : "hidden")}>
          {showEditor ? (
            <ArticleEditor
              key={selectedId}
              article={editing}
              onClose={() => setSelectedId(null)}
              onSaved={async (saved) => {
                await knowledge.mutate();
                setSelectedId(saved.id);
              }}
              onDeleted={async () => {
                await knowledge.mutate();
                setSelectedId(null);
              }}
            />
          ) : (
            <Guide />
          )}
        </section>
      </div>
    </div>
  );
}

function ArticleEditor({
  article,
  onClose,
  onSaved,
  onDeleted,
}: {
  article: KnowledgeArticle | null;
  onClose: () => void;
  onSaved: (article: KnowledgeArticle) => Promise<void>;
  onDeleted: () => Promise<void>;
}) {
  const [title, setTitle] = useState(article?.title ?? "");
  const [content, setContent] = useState(article?.content ?? "");
  const [busy, setBusy] = useState(false);
  // The editor is keyed by article id, so this resets when another article opens.
  const [confirmDelete, setConfirmDelete] = useState(false);

  const changed = title !== (article?.title ?? "") || content !== (article?.content ?? "");
  const canSave = title.trim().length > 0 && content.trim().length > 0 && changed && !busy;

  async function save() {
    if (!canSave) return;
    setBusy(true);
    try {
      const body = JSON.stringify({ title, content });
      const saved = article
        ? await api<KnowledgeArticle>(`/api/v1/knowledge/${article.id}`, { method: "PUT", body })
        : await api<KnowledgeArticle>("/api/v1/knowledge", { method: "POST", body });
      await onSaved(saved);
      toast.success(article ? "Article updated" : "Article added");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not save the article");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!article) return;
    setBusy(true);
    try {
      await api(`/api/v1/knowledge/${article.id}`, { method: "DELETE" });
      await onDeleted();
      toast.success("Article deleted");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not delete the article");
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
      className="flex h-full flex-col"
    >
      <div className="flex h-14 shrink-0 items-center justify-between gap-2 border-b px-3 sm:px-4">
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
        <div className="flex items-center gap-2">
          {article &&
            (confirmDelete ? (
              <>
                <span className="hidden text-[12px] text-muted-foreground sm:inline">Delete this article?</span>
                <Button type="button" variant="destructive" size="sm" onClick={remove} disabled={busy}>
                  Delete
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
                  Keep
                </Button>
              </>
            ) : (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Delete article"
                onClick={() => setConfirmDelete(true)}
              >
                <Trash2 />
              </Button>
            ))}
          <Button type="submit" size="sm" disabled={!canSave}>
            {busy ? "Saving" : "Save"}
          </Button>
        </div>
      </div>

      <div className="scroll-quiet flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl space-y-4 px-4 py-6 sm:px-6">
          <label className="block">
            <span className="text-[13px] font-medium">Title</span>
            <input
              dir="auto"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={200}
              placeholder="For example: Prices and packages"
              className="mt-1.5 h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
            />
          </label>
          <label className="block">
            <span className="text-[13px] font-medium">Content</span>
            <textarea
              dir="auto"
              value={content}
              onChange={(event) => setContent(event.target.value)}
              maxLength={50000}
              rows={18}
              placeholder="Write the facts the AI may share: prices, what is included, opening hours, how to book, policies…"
              className="mt-1.5 block w-full resize-y rounded-lg border bg-background px-3 py-2.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
            />
          </label>
          {article && (
            <p className="text-[12px] text-muted-foreground">Last updated {relativeTime(article.updated_at)} ago</p>
          )}
        </div>
      </div>
    </form>
  );
}

function EmptyList({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 text-center">
      <span className="flex size-10 items-center justify-center rounded-xl bg-brand-soft text-brand">
        <BookOpen className="size-5" strokeWidth={1.75} />
      </span>
      <p className="mt-3 text-sm font-medium">No articles yet</p>
      <p className="mt-1 max-w-xs text-[13px] text-muted-foreground">
        Until you add knowledge, the AI greets customers and hands every question to your team.
      </p>
      <Button size="sm" className="mt-4" onClick={onCreate}>
        <Plus />
        Add the first article
      </Button>
    </div>
  );
}

function Guide() {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-muted/30 px-6 text-center">
      <div className="max-w-md">
        <p className="text-sm font-medium">Good articles make good answers</p>
        <ul className="mt-3 space-y-2 text-left text-[13px] leading-relaxed text-muted-foreground">
          <li>One topic per article: prices, services, hours, delivery, booking, policies.</li>
          <li>Write facts, not marketing. Include exact prices, times and conditions.</li>
          <li>Arabic, English or both are fine. The AI replies in the customer&apos;s language.</li>
          <li>Anything not written here, the AI will not promise. It hands the question to your team instead.</li>
        </ul>
      </div>
    </div>
  );
}
