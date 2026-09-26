import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronRight, Menu, Moon, Plus, Search, Sun, X, Youtube } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme";
import { relativeTime, initialOf } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { DialogOverlay } from "@/components/ui/dialog";
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
  // A failed status request says nothing about the connection, so it must not
  // read as "not connected".
  const unknown = isError && !data;

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
      to={!unknown && (connected || data?.configured !== false) ? "/channel" : "/settings"}
      onClick={onNavigate}
      className="group flex items-center gap-3 rounded-xl border border-sidebar-border bg-white/[0.03] p-2.5 transition-colors hover:border-white/15 hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-brand"
    >
      {unknown ? (
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-sidebar-accent text-sidebar-muted" aria-hidden="true">
          <Youtube className="size-4" />
        </span>
      ) : connected ? (
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-brand-gradient p-0.5" aria-hidden="true">
          <span className="grid size-full place-items-center rounded-full bg-sidebar font-display text-[0.8125rem] font-semibold text-sidebar-foreground">
            {initialOf(title)}
          </span>
        </span>
      ) : (
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-[#ff0033]/15 text-[#ff4d6a]" aria-hidden="true">
          <Youtube className="size-4" />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[0.8125rem] font-medium text-sidebar-foreground">
          {unknown ? "Channel status unavailable" : connected ? title : "Connect your channel"}
        </span>
        <span className="block truncate text-[0.6875rem] text-sidebar-muted">{subtitle}</span>
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
        className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-[radial-gradient(oklch(1_0_0/0.05)_1px,transparent_1px)] [background-size:1.125rem_1.125rem] [mask-image:linear-gradient(to_bottom,black,transparent)]"
        aria-hidden="true"
      />

      <div className="relative flex items-center gap-3 px-5 pb-5 pt-6">
        <BrandMark />
        <div className="min-w-0 leading-tight">
          <p className="font-display text-[1.0625rem] font-semibold tracking-tight">Win-Engine</p>
          <p className="text-[0.6875rem] text-sidebar-muted">Creator intelligence</p>
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
            <p className="px-3 pb-1.5 text-[0.65625rem] font-semibold uppercase tracking-[0.16em] text-sidebar-muted">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon, hint }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    onClick={onNavigate}
                    title={hint}
                    className={({ isActive }) =>
                      cn(
                        "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-[0.84375rem] font-medium transition-colors",
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
                            "size-4.5 shrink-0 transition-colors",
                            isActive ? "text-sidebar-brand" : "group-hover:text-sidebar-foreground",
                          )}
                          aria-hidden="true"
                        />
                        <span className="flex-1 truncate">{label}</span>
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
  const drawerCloseRef = useRef<HTMLButtonElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  // Close the drawer on navigation so a tap never leaves it covering content.
  useEffect(() => setMobileOpen(false), [location.pathname]);

  // Past the lg breakpoint the drawer is hidden but would still be modal,
  // leaving the whole page inert behind nothing; close it instead.
  useEffect(() => {
    const wide = window.matchMedia?.("(min-width: 64rem)");
    if (!wide) return;
    const onChange = (event: MediaQueryListEvent) => {
      if (event.matches) setMobileOpen(false);
    };
    wide.addEventListener?.("change", onChange);
    return () => wide.removeEventListener?.("change", onChange);
  }, []);

  // Each page names the browser tab, so history and tabs tell pages apart.
  useEffect(() => {
    const located = locateNav(location.pathname);
    document.title = located ? `${located.item.label} · Win-Engine` : "Win-Engine · Creator Intelligence";
  }, [location.pathname]);

  // Ctrl/⌘ K opens the command palette from anywhere, and closes it again.
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

      {/* Mobile drawer. A Radix dialog, so focus is trapped inside it, the page
          behind is inert and Escape closes it. It opens from state, with no
          Dialog.Trigger, so focus is sent back to the menu button explicitly. */}
      <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogPrimitive.Portal>
          <DialogOverlay className="lg:hidden" />
          <DialogPrimitive.Content
            aria-describedby={undefined}
            onOpenAutoFocus={(event) => {
              event.preventDefault();
              drawerCloseRef.current?.focus();
            }}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              menuButtonRef.current?.focus();
            }}
            className="fixed inset-y-0 left-0 z-50 flex w-[18rem] max-w-[85vw] animate-drawer-in shadow-elevated focus-visible:outline-none lg:hidden"
          >
            <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
            <SidebarContent onNavigate={closeDrawer} />
            <DialogPrimitive.Close asChild>
              <Button
                ref={drawerCloseRef}
                variant="ghost"
                size="icon-sm"
                className="absolute right-3 top-6 text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-foreground"
                aria-label="Close navigation"
              >
                <X aria-hidden="true" />
              </Button>
            </DialogPrimitive.Close>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      <div className={cn("relative", SIDEBAR_WIDTH)}>
        {/* Ambient light at the top of every page. Decorative only. */}
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-0 h-140 overflow-hidden"
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
              className="flex h-9 items-center gap-2 rounded-xl border border-border bg-card/70 px-2.5 text-[0.8125rem] text-muted-foreground shadow-[0_1px_2px_oklch(0.2_0.03_286/0.05)] transition-colors hover:border-foreground/20 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:w-64 md:px-3"
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
