import { Users } from "lucide-react";
import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Customers" };

export default function CustomersPage() {
  return (
    <ComingSoon
      icon={Users}
      title="Customers"
      summary="One record per customer: who they are, every conversation they have had, and the deals in progress with them."
      poweredBy="Twenty CRM"
      points={[
        "Contacts and companies synced from the CRM",
        "Sales opportunities with stage and value",
        "A timeline that joins conversations, deals and tasks",
      ]}
    />
  );
}
