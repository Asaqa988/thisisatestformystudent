import type { Metadata } from "next";
import { Suspense } from "react";

import { InboxView } from "@/components/inbox/inbox-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Unified Inbox" };

export default function InboxPage() {
  // InboxView reads ?c=<conversation id> from the URL. Anything that depends on
  // the request must sit inside Suspense so the rest of the page can be prebuilt.
  return (
    <Suspense fallback={<InboxFallback />}>
      <InboxView />
    </Suspense>
  );
}

function InboxFallback() {
  return (
    <div className="flex h-full flex-col">
      <div className="h-14 shrink-0 border-b" />
      <div className="flex min-h-0 flex-1">
        <div className="w-full space-y-4 border-r p-3 md:w-80 lg:w-[22rem]">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex gap-3">
              <Skeleton className="size-8 rounded-full" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3.5 w-1/2" />
                <Skeleton className="h-3 w-5/6" />
              </div>
            </div>
          ))}
        </div>
        <div className="hidden flex-1 bg-muted/30 md:block" />
      </div>
    </div>
  );
}
