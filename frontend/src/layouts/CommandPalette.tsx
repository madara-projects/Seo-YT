import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CornerDownLeft,
  ExternalLink,
  Moon,
  Search,
  Sparkles,
  Sun,
  type LucideIcon,
} from "lucide-react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Kbd } from "@/components/common/Kbd";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme";
import { NAV_ITEMS } from "./navigation";

interface Command {
  id: string;
  group: "Go to" | "Actions";
  label: string;
  hint?: string;
  icon: LucideIcon;
  run: () => void;
}

function matches(command: Command, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  const haystack = `${command.label} ${command.hint ?? ""} ${command.group}`.toLowerCase();
  return needle.split(/\s+/).every((word) => haystack.includes(word));
}

/**
 * Keyboard-first navigation (Ctrl/⌘ K). It only navigates and toggles local
 * preferences; nothing here calls the API.
 */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const { resolvedTheme, setTheme } = useTheme();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();
  const listRef = useRef<HTMLDivElement>(null);

  const commands = useMemo<Command[]>(
    () => [
      ...NAV_ITEMS.map((item) => ({
        id: `nav-${item.to.slice(1)}`,
        group: "Go to" as const,
        label: item.label,
        hint: item.hint,
        icon: item.icon,
        run: () => navigate(item.to),
      })),
      {
        id: "action-new-package",
        group: "Actions",
        label: "Start a new SEO package",
        hint: "Open Creator",
        icon: Sparkles,
        run: () => navigate("/creator"),
      },
      {
        id: "action-theme",
        group: "Actions",
        label: resolvedTheme === "dark" ? "Use light theme" : "Use dark theme",
        hint: "Appearance",
        icon: resolvedTheme === "dark" ? Sun : Moon,
        run: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
      },
      {
        id: "action-legacy",
        group: "Actions",
        label: "Open the classic dashboard",
        hint: "The original interface, still available",
        icon: ExternalLink,
        run: () => window.open("/dashboard_legacy", "_blank", "noopener"),
      },
    ],
    [navigate, resolvedTheme, setTheme],
  );

  const results = useMemo(() => commands.filter((command) => matches(command, query)), [
    commands,
    query,
  ]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  useEffect(() => setActive(0), [query]);

  // Keep the highlighted option in view while arrowing through a long list.
  useEffect(() => {
    const node = listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`);
    node?.scrollIntoView?.({ block: "nearest" });
  }, [active]);

  const execute = (command: Command | undefined) => {
    if (!command) return;
    onOpenChange(false);
    command.run();
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!results.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => (index + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => (index - 1 + results.length) % results.length);
    } else if (event.key === "Home") {
      event.preventDefault();
      setActive(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActive(results.length - 1);
    } else if (event.key === "Enter") {
      event.preventDefault();
      execute(results[active]);
    }
  };

  const groups = (["Go to", "Actions"] as const)
    .map((group) => ({
      group,
      items: results
        .map((command, index) => ({ command, index }))
        .filter(({ command }) => command.group === group),
    }))
    .filter((entry) => entry.items.length);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="top-[12vh] max-w-xl translate-y-0 gap-0 overflow-hidden p-0"
      >
        <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
        <DialogPrimitive.Description className="sr-only">
          Search pages and actions. Use the arrow keys to move and Enter to open.
        </DialogPrimitive.Description>

        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Jump to a page or run an action…"
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={results.length ? `${listId}-${active}` : undefined}
            aria-label="Search pages and actions"
            className="h-14 flex-1 bg-transparent text-[0.9375rem] text-foreground outline-none placeholder:text-muted-foreground"
          />
          <Kbd>Esc</Kbd>
        </div>

        <div
          ref={listRef}
          id={listId}
          role="listbox"
          aria-label="Results"
          className="max-h-[min(60vh,26.25rem)] overflow-y-auto p-2 scrollbar-thin"
        >
          {groups.length ? (
            groups.map(({ group, items }) => (
              <div key={group} role="group" aria-label={group} className="pb-1">
                <p className="px-2.5 pb-1 pt-2 text-[0.6875rem] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  {group}
                </p>
                {items.map(({ command, index }) => {
                  const Icon = command.icon;
                  const selected = index === active;
                  return (
                    <div
                      key={command.id}
                      id={`${listId}-${index}`}
                      data-index={index}
                      role="option"
                      aria-selected={selected}
                      onMouseMove={() => setActive(index)}
                      onClick={() => execute(command)}
                      className={cn(
                        "flex cursor-pointer items-center gap-3 rounded-xl px-2.5 py-2.5 text-sm",
                        selected ? "bg-accent text-foreground" : "text-foreground/90",
                      )}
                    >
                      <span
                        className={cn(
                          "grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-card",
                          selected && "border-brand-border bg-brand-soft text-brand",
                        )}
                        aria-hidden="true"
                      >
                        <Icon className="size-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{command.label}</span>
                        {command.hint ? (
                          <span className="block truncate text-xs text-muted-foreground">
                            {command.hint}
                          </span>
                        ) : null}
                      </span>
                      {selected ? (
                        <CornerDownLeft className="size-3.5 text-muted-foreground" aria-hidden="true" />
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ))
          ) : (
            <p className="px-3 py-10 text-center text-sm text-muted-foreground">
              Nothing matches “{query.trim()}”.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
