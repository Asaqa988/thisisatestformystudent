import type { Metadata } from "next";

import { AIEmployeesView } from "@/components/ai/ai-employees-view";

export const metadata: Metadata = { title: "AI Employees" };

export default function AiEmployeesPage() {
  return <AIEmployeesView />;
}
