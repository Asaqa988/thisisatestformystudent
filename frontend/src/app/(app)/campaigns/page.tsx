import { Megaphone } from "lucide-react";
import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Campaigns" };

export default function CampaignsPage() {
  return (
    <ComingSoon
      icon={Megaphone}
      title="Campaigns"
      summary="Plan a campaign once and let automations carry it across channels, with results reported back here."
      poweredBy="Plane and Activepieces"
      points={[
        "Campaign plans linked to their tasks",
        "Automated workflows triggered by NEXUS events",
        "Drafts prepared by the marketing agent",
      ]}
    />
  );
}
