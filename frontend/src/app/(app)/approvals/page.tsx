import { ShieldCheck } from "lucide-react";
import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return (
    <ComingSoon
      icon={ShieldCheck}
      title="Approvals"
      summary="Where humans stay in control. Agents propose sensitive actions here and wait for a yes or a no."
      poweredBy="NEXUS agents"
      points={[
        "A queue of proposed actions with their reasoning",
        "Approve, edit or reject in one step",
        "A full history of who approved what",
      ]}
    />
  );
}
