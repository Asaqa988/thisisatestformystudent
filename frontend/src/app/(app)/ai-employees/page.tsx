import { Bot } from "lucide-react";
import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "AI Employees" };

export default function AiEmployeesPage() {
  return (
    <ComingSoon
      icon={Bot}
      title="AI Employees"
      summary="Agents that do the routine work: answer customers, qualify leads, draft campaigns and keep projects moving."
      poweredBy="NEXUS agents"
      points={[
        "Sales, marketing, support and project coordination agents",
        "A clear record of what each agent did and why",
        "Sensitive actions wait for a human in Approvals",
      ]}
    />
  );
}
