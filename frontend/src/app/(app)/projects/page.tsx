import { FolderKanban } from "lucide-react";
import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return (
    <ComingSoon
      icon={FolderKanban}
      title="Projects"
      summary="Client work broken into tasks, with owners and deadlines, visible without leaving NEXUS."
      poweredBy="Plane"
      points={[
        "Projects and tasks synced from Plane",
        "Tasks created directly from a customer conversation",
        "Progress the whole agency can read at a glance",
      ]}
    />
  );
}
