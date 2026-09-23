import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  ClipboardCheck,
  FlaskConical,
  Home,
  Lightbulb,
  Menu,
  Moon,
  Settings,
  Sparkles,
  Sun,
  TrendingUp,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { HealthIndicator } from "@/components/common/HealthIndicator";

const NAV_ITEMS = [
  { to: "/creator", label: "Creator", icon: Sparkles, hint: "Generate and compare packages" },
  { to: "/dashboard", label: "Dashboard", icon: Home, hint: "Overview and signals" },
  { to: "/history", label: "History", icon: Activity, hint: "Saved packages and links" },
  { to: "/ideas", label: "Ideas", icon: Lightbulb, hint: "Idea workspace" },
  { to: "/demand", label: "Demand", icon: TrendingUp, hint: "Demand explorer" },
  { to: "/audits", label: "Audits", icon: ClipboardCheck, hint: "Published-video audits" },
  { to: "/experiments", label: "Experiments", icon: FlaskConical, hint: "Experiment center" },
  { to: "/watchlist", label: "Watchlist", icon: BarChart3, hint: "Channels and videos" },
  { to: "/settings", label: "Settings", icon: Settings, hint: "Connection and status" },
] as const;

function ThemeToggle() {
  const { resolvedTheme, toggle } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} theme`}
    >
      {resolvedTheme === "dark" ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-1">
      <div className="flex items-center gap-2.5 px-4 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-extrabold tracking-tight">Win-Engine</p>
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Creator intelligence
          </p>
        </div>
      </div>

      <Separator />

      <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto scrollbar-thin p-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, hint }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            title={hint}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      <Separator />

      <div className="p-3">
        <HealthIndicator />
      </div>
    </div>
  );
}

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  // Close the drawer on navigation so a tap never leaves it covering content.
  useEffect(() => setMobileOpen(false), [location.pathname]);

  // Escape closes the drawer; the sidebar is a dialog-like surface on mobile.
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary-foreground"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-sidebar-border bg-sidebar lg:block">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="absolute inset-y-0 left-0 w-64 border-r border-sidebar-border bg-sidebar shadow-xl"
          >
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 top-3"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
            >
              <X aria-hidden="true" />
            </Button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-border bg-background/85 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/70">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
          >
            <Menu aria-hidden="true" />
          </Button>
          <div className="flex-1" />
          <ThemeToggle />
        </header>

        <main id="main-content" className="px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
