import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { ChevronRight, Menu, Moon, Plus, Search, Sun, X, Youtube } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme";
import { relativeTime, initialOf } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandMark } from "@/components/common/BrandMark";
import { HealthIndicator } from "@/components/common/HealthIndicator";
import { Kbd, modifierKeyLabel } from "@/components/common/Kbd";
import { useChannelStatus } from "@/hooks/useSystem";
import { CommandPalette } from "./CommandPalette";
import { NAV_GROUPS, locateNav } from "./navigation";

const SIDEBAR_WIDTH = "lg:pl-[17rem]";

function ThemeToggle() {
  const { resolvedTheme, toggle } = useTheme();
  const dark = resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label={`Switch to ${dark ? "light" : "dark"} theme`}
      className="relative overflow-hidden"
    >
      <Sun
        aria-hidden="true"
        className={cn("transition-all duration-300", dark ? "rotate-0 scale-100" : "-rotate-90 scale-0")}
      />
      <Moon
        aria-hidden="true"
        className={cn(
          "absolute transition-all duration-300",
          dark ? "rotate-90 scale-0" : "rotate-0 scale-100",
        )}
      />
    </Button>
  );
}

/** The connected channel at the foot of the sidebar, or the way to connect one. */
function SidebarChannel({ onNavigate }: { onNavigate?: () => void }) {
  const { data, isPending, isError } = useChannelStatus();

  if (isPending) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-sidebar-border p-2.5">
        <Skeleton className="size-8 rounded-full bg-sidebar-accent" />
        <div className="flex-1 space-y-1.5">
          <Skeleton className="h-2.5 w-24 bg-sidebar-accent" />
          <Skeleton className="h-2 w-16 bg-sidebar-accent" />
        </div>
      </div>
    );
  }

  const connected = Boolean(data?.connected);
  const title = data?.channel?.title || "YouTube channel";
  const syncedAt = data?.latest_sync?.synced_at;
  const subtitle = isError
    ? "Status unavailable"
    : connected
      ? syncedAt
        ? `Synced ${relativeTime(syncedAt)}`
        : "Not synced yet"
      : data?.configured === false
        ? "Needs OAuth setup"
        : "Unlock real channel stats";

  return (
    <Link
      to={connected || data?.configured !== false ? "/channel" : "/settings"}
      onClick={onNavigate}
      className="group flex items-center gap-3 rounded-xl border border-sidebar-border bg-white/[0.03] p-2.5 transition-colors hover:border-white/15 hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-brand"
    >
      {connected ? (
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-brand-gradient p-[2px]" aria-hidden="true">
          <span className="grid size-full place-items-center rounded-full bg-sidebar font-display text-[13px] font-semibold text-sidebar-foreground">
            {initialOf(title)}
          </span>
        </span>
      ) : (
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-[#ff0033]/15 text-[#ff4d6a]" aria-hidden="true">
          <Youtube className="size-4" />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium text-sidebar-foreground">
          {connected ? title : "Connect your channel"}
        </span>
        <span className="block truncate text-[11px] text-sidebar-muted">{subtitle}</span>
      </span>
      <ChevronRight
        className="size-4 shrink-0 text-sidebar-muted transition-transform group-hover:translate-x-0.5"
        aria-hidden="true"
      />
    </Link>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-sidebar text-sidebar-foreground">
      <div
        className="pointer-events-none absolute -left-28 -top-28 size-80 rounded-full bg-brand-gradient opacity-25 blur-3xl"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-[radial-gradient(oklch(1_0_0/0.05)_1px,transparent_1px)] [background-size:18px_18px] [mask-image:linear-gradient(to_bottom,black,transparent)]"
        aria-hidden="true"
      />

      <div className="relative flex items-center gap-3 px-5 pb-5 pt-6">
        <BrandMark />
        <div className="min-w-0 leading-tight">
          <p className="font-display text-[17px] font-semibold tracking-tight">Win-Engine</p>
          <p className="text-[11px] text-sidebar-muted">Creator intelligence</p>
        </div>
      </div>

      <div className="relative px-4">
        <Link
          to="/creator"
          onClick={onNavigate}
          className="flex h-10 items-center justify-center gap-2 rounded-xl bg-cta-gradient text-sm font-semibold text-white shadow-[inset_0_1px_0_oklch(1_0_0/0.2),0_10px_24px_-12px_oklch(0.55_0.25_300/0.9)] transition-[filter] hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-brand focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar"
        >
          <Plus className="size-4" aria-hidden="true" />
          New package
        </Link>
      </div>

      <nav aria-label="Main" className="relative mt-5 flex-1 space-y-5 overflow-y-auto px-4 pb-4 scrollbar-none">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-sidebar-muted">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon, hint, legacy }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    onClick={onNavigate}
                    title={legacy ? `${hint} · still served by the classic dashboard` : hint}
                    className={({ isActive }) =>
                      cn(
                        "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-[13.5px] font-medium transition-colors",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-brand",
                        isActive
                          ? "bg-sidebar-accent text-sidebar-foreground shadow-[inset_0_1px_0_oklch(1_0_0/0.05)]"
                          : "text-sidebar-muted hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive ? (
                          <span
                            className="absolute -left-4 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-brand-gradient"
                            aria-hidden="true"
                          />
                        ) : null}
                        <Icon
                          className={cn(
                            "size-[18px] shrink-0 transition-colors",
                            isActive ? "text-sidebar-brand" : "group-hover:text-sidebar-foreground",
                          )}
                          aria-hidden="true"
                        />
                        <span className="flex-1 truncate">{label}</span>
                        {legacy ? (
                          <span className="rounded-md border border-sidebar-border px-1.5 py-px text-[9.5px] font-semibold uppercase tracking-wider text-sidebar-muted">
                            Legacy
                          </span>
                        ) : null}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="relative space-y-3 border-t border-sidebar-border p-4">
        <SidebarChannel onNavigate={onNavigate} />
        <HealthIndicator />
      </div>
    </div>
  );
}

function Breadcrumb() {
  const { pathname } = useLocation();
  const located = locateNav(pathname);
  if (!located) return null;

  return (
    <nav aria-label="Breadcrumb" className="hidden min-w-0 items-center gap-2 text-sm sm:flex">
      <span className="text-muted-foreground">{located.group.label}</span>
      <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/60" aria-hidden="true" />
      <span className="truncate font-medium text-foreground" aria-current="page">
        {located.item.label}
      </span>
    </nav>
  );
}

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const drawerCloseRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  // Close the drawer on navigation so a tap never leaves it covering content.
  useEffect(() => setMobileOpen(false), [location.pathname]);

  // Escape closes the drawer; focus moves into it and returns to the menu button.
  useEffect(() => {
    if (!mobileOpen) {
      if (wasOpen.current) menuButtonRef.current?.focus();
      wasOpen.current = false;
      return;
    }
    wasOpen.current = true;
    drawerCloseRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileOpen]);

  // Ctrl/⌘ K opens the command palette from anywhere.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const closeDrawer = useCallback(() => setMobileOpen(false), []);
  const modifier = modifierKeyLabel();

  return (
    <div className="relative min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-xl focus:bg-primary focus:px-4 focus:py-2.5 focus:text-sm focus:font-semibold focus:text-primary-foreground focus:shadow-elevated"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[17rem] border-r border-sidebar-border lg:flex">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            tabIndex={-1}
            className="absolute inset-0 bg-[oklch(0.12_0.025_286/0.6)] backdrop-blur-[2px] animate-overlay-in"
            onClick={closeDrawer}
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="absolute inset-y-0 left-0 flex w-[18rem] max-w-[85vw] animate-drawer-in shadow-elevated"
          >
            <SidebarContent onNavigate={closeDrawer} />
            <Button
              ref={drawerCloseRef}
              variant="ghost"
              size="icon-sm"
              className="absolute right-3 top-6 text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-foreground"
              onClick={closeDrawer}
              aria-label="Close navigation"
            >
              <X aria-hidden="true" />
            </Button>
          </aside>
        </div>
      ) : null}

      <div className={cn("relative", SIDEBAR_WIDTH)}>
        {/* Ambient light at the top of every page. Decorative only. */}
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[560px] overflow-hidden"
          aria-hidden="true"
        >
          <div className="absolute inset-0 app-glow" />
          <div className="absolute inset-0 bg-dots [mask-image:linear-gradient(to_bottom,black,transparent_85%)]" />
        </div>

        <header className="sticky top-0 z-20 border-b border-border/70 bg-background/70 backdrop-blur-xl">
          <div className="flex h-16 items-center gap-2 px-4 sm:gap-3 sm:px-6 lg:px-10">
            <Button
              ref={menuButtonRef}
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              aria-expanded={mobileOpen}
            >
              <Menu aria-hidden="true" />
            </Button>
            <Link
              to="/dashboard"
              className="flex items-center gap-2 rounded-xl lg:hidden"
              aria-label="Win-Engine home"
            >
              <BrandMark className="size-8 rounded-lg" />
            </Link>
            <Breadcrumb />
            <div className="flex-1" />
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              aria-label="Search pages and actions"
              aria-keyshortcuts="Control+K Meta+K"
              className="flex h-9 items-center gap-2 rounded-xl border border-border bg-card/70 px-2.5 text-[13px] text-muted-foreground shadow-[0_1px_2px_oklch(0.2_0.03_286/0.05)] transition-colors hover:border-foreground/20 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:w-64 md:px-3"
            >
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="hidden flex-1 text-left md:inline">Jump to…</span>
              <Kbd className="hidden md:inline-flex">{modifier} K</Kbd>
            </button>
            <ThemeToggle />
          </div>
        </header>

        <main
          id="main-content"
          tabIndex={-1}
          className="relative z-10 px-4 pb-20 pt-6 outline-none sm:px-6 sm:pt-8 lg:px-10"
        >
          <Outlet />
        </main>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
