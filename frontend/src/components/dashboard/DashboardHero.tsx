import { Link } from "react-router-dom";
import {
  ArrowRight,
  ClipboardCheck,
  Library,
  Lightbulb,
  MonitorPlay,
  Sparkles,
  Telescope,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { greetingFor } from "@/lib/historyFormat";

/** The creator loop, as the legacy dashboard framed it. Publishing is manual. */
const LOOP_STEPS: { label: string; to: string | null; icon: LucideIcon }[] = [
  { label: "Idea", to: "/ideas", icon: Lightbulb },
  { label: "Research", to: "/demand", icon: Telescope },
  { label: "Package", to: "/creator", icon: Sparkles },
  { label: "Publish", to: null, icon: MonitorPlay },
  { label: "Audit", to: "/audits", icon: ClipboardCheck },
  { label: "Learn", to: "/history", icon: TrendingUp },
];

/** Node centres on a circle of radius 38% around the middle, starting at the top. */
function nodePosition(index: number, total: number) {
  const angle = (-90 + (360 / total) * index) * (Math.PI / 180);
  return { left: `${50 + 38 * Math.cos(angle)}%`, top: `${50 + 38 * Math.sin(angle)}%` };
}

function CreatorLoop() {
  return (
    <div
      role="group"
      aria-label="Creator loop"
      className="relative mx-auto aspect-square w-full max-w-80"
    >
      <svg viewBox="0 0 100 100" className="absolute inset-0 size-full" aria-hidden="true">
        <defs>
          <linearGradient id="loop-stroke" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--grad-1)" />
            <stop offset="0.55" stopColor="var(--grad-2)" />
            <stop offset="1" stopColor="var(--grad-3)" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="38" fill="none" stroke="var(--border)" strokeWidth="0.5" />
        <circle
          cx="50"
          cy="50"
          r="38"
          fill="none"
          stroke="url(#loop-stroke)"
          strokeWidth="0.7"
          strokeDasharray="1.4 2.2"
          strokeLinecap="round"
        />
      </svg>

      {/* A pulse travelling the loop. Stopped by the reduced-motion rule. */}
      <div className="absolute inset-0 animate-[spin_14s_linear_infinite]" aria-hidden="true">
        <span className="absolute left-1/2 top-[12%] size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow-[0_0_14px_5px_oklch(0.7_0.2_330/0.6)]" />
      </div>

      <div className="absolute inset-[26%] grid place-items-center rounded-full border border-border bg-card/80 text-center shadow-card backdrop-blur-sm">
        <div className="px-2">
          <p className="font-display text-[0.9375rem] font-semibold leading-tight text-foreground">
            Creator loop
          </p>
          <p className="mt-1 text-[0.6875rem] leading-snug text-muted-foreground">
            Idea to insight. Publishing stays manual.
          </p>
        </div>
      </div>

      <ol className="absolute inset-0">
        {LOOP_STEPS.map((step, index) => {
          const Icon = step.icon;
          const position = nodePosition(index, LOOP_STEPS.length);
          const node = (
            <>
              <span
                className={cn(
                  "grid size-11 place-items-center rounded-2xl border shadow-card transition-transform",
                  step.to
                    ? "border-border bg-card text-brand group-hover:-translate-y-0.5 group-hover:border-brand-border"
                    : "border-dashed border-border bg-muted text-muted-foreground",
                )}
              >
                <Icon className="size-4.5" aria-hidden="true" />
              </span>
              <span className="mt-1 block whitespace-nowrap rounded-md bg-card/90 px-1.5 py-0.5 text-center text-[0.6875rem] font-medium text-foreground shadow-[0_0_0_1px_var(--border)]">
                {index + 1}. {step.label}
              </span>
            </>
          );
          return (
            <li
              key={step.label}
              className="absolute -translate-x-1/2 -translate-y-[35%]"
              style={position}
            >
              {step.to ? (
                <Link
                  to={step.to}
                  className="group flex flex-col items-center rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {node}
                </Link>
              ) : (
                <span
                  className="flex flex-col items-center"
                  title="Publishing happens manually in YouTube Studio"
                >
                  {node}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function DashboardHero({ totalRuns }: { totalRuns?: number }) {
  const today = new Date().toLocaleDateString("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <section className="relative overflow-hidden rounded-3xl border border-border hero-wash p-6 shadow-card sm:p-8 lg:p-10">
      <div
        className="pointer-events-none absolute inset-0 bg-dots [mask-image:radial-gradient(ellipse_at_top_right,black,transparent_65%)]"
        aria-hidden="true"
      />
      <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-center xl:gap-12">
        <div className="space-y-5">
          <p className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur-sm">
            <span className="size-1.5 rounded-full bg-brand-gradient" aria-hidden="true" />
            {greetingFor()} · {today}
          </p>
          <div className="space-y-3">
            <h1 className="font-display text-4xl font-semibold tracking-tight sm:text-5xl">
              <span className="text-gradient">Dashboard</span>
            </h1>
            <p className="max-w-xl text-[0.9375rem] leading-relaxed text-muted-foreground">
              Your creator studio at a glance. Everything saved locally from your packaging work,
              with each number labelled by where it came from
              {typeof totalRuns === "number" && totalRuns > 0
                ? ` — ${totalRuns.toLocaleString()} ${totalRuns === 1 ? "package" : "packages"} so far.`
                : "."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2.5">
            <Button variant="gradient" size="lg" asChild>
              <Link to="/creator">
                <Sparkles aria-hidden="true" />
                Launch Creator
              </Link>
            </Button>
            <Button variant="outline" size="lg" asChild>
              <Link to="/history">
                <Library aria-hidden="true" />
                Open library
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </div>
        <CreatorLoop />
      </div>
    </section>
  );
}
