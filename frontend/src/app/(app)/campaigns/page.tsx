import type { Metadata } from "next";
import { Suspense } from "react";

import { AdsView } from "@/components/ads/ads-view";

export const metadata: Metadata = { title: "Campaigns" };

export default function CampaignsPage() {
  // AdsView reads ?id=<ad id> from the URL, so it sits inside Suspense.
  return (
    <Suspense fallback={<div className="h-full" />}>
      <AdsView />
    </Suspense>
  );
}
