import type { Metadata } from "next";
import { Suspense } from "react";

import { AutomationsView } from "@/components/automations/automations-view";

export const metadata: Metadata = { title: "Automations" };

export default function AutomationsPage() {
  // AutomationsView reads ?id=<automation id> from the URL, so it sits inside Suspense.
  return (
    <Suspense fallback={<div className="h-full" />}>
      <AutomationsView />
    </Suspense>
  );
}
