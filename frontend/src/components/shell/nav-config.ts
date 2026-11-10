import {
  Bot,
  FolderKanban,
  Inbox,
  LayoutDashboard,
  type LucideIcon,
  Megaphone,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Pages that exist only as a marked placeholder in Lesson 01. */
  upcoming?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/inbox", label: "Unified Inbox", icon: Inbox },
      { href: "/customers", label: "Customers", icon: Users, upcoming: true },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/ai-employees", label: "AI Employees", icon: Bot, upcoming: true },
      { href: "/projects", label: "Projects", icon: FolderKanban, upcoming: true },
      { href: "/campaigns", label: "Campaigns", icon: Megaphone, upcoming: true },
      { href: "/approvals", label: "Approvals", icon: ShieldCheck, upcoming: true },
    ],
  },
];

export const SETTINGS_ITEM: NavItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
  upcoming: true,
};

export function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
