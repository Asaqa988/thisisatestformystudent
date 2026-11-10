import { Settings } from "lucide-react";
import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <ComingSoon
      icon={Settings}
      title="Settings"
      summary="Workspace, team and integration settings. In Lesson 01 integrations are configured in the .env file instead."
      poweredBy="NEXUS"
      points={[
        "Connect and disconnect integrations from the interface",
        "Team members and roles",
        "Workspace name, branding and preferences",
      ]}
    />
  );
}
