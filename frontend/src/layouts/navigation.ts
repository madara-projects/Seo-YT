import {
  ClipboardCheck,
  Eye,
  FlaskConical,
  Library,
  Lightbulb,
  LayoutDashboard,
  Settings2,
  Sparkles,
  TrendingUp,
  Youtube,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  hint: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/** One source for the sidebar, the command palette and the top-bar breadcrumb. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Studio",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, hint: "Overview and signals" },
      { to: "/creator", label: "Creator", icon: Sparkles, hint: "Generate and compare packages" },
      { to: "/history", label: "History", icon: Library, hint: "Saved packages and links" },
    ],
  },
  {
    label: "Performance",
    items: [
      { to: "/channel", label: "Channel", icon: Youtube, hint: "Real numbers from your channel" },
    ],
  },
  {
    label: "Research lab",
    items: [
      { to: "/ideas", label: "Ideas", icon: Lightbulb, hint: "Your backlog of video ideas" },
      { to: "/demand", label: "Demand", icon: TrendingUp, hint: "Check interest before you film" },
      { to: "/audits", label: "Audits", icon: ClipboardCheck, hint: "What went live, and how it did" },
      { to: "/experiments", label: "Experiments", icon: FlaskConical, hint: "Test one decision at a time" },
      { to: "/watchlist", label: "Watchlist", icon: Eye, hint: "Channels and videos to learn from" },
    ],
  },
  {
    label: "System",
    items: [
      { to: "/settings", label: "Settings", icon: Settings2, hint: "Connections, sync and status" },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

/** The group and item for a pathname, for the breadcrumb. */
export function locateNav(pathname: string): { group: NavGroup; item: NavItem } | null {
  for (const group of NAV_GROUPS) {
    const item = group.items.find(
      (candidate) => pathname === candidate.to || pathname.startsWith(`${candidate.to}/`),
    );
    if (item) return { group, item };
  }
  return null;
}
