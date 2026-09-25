import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type StepState = "done" | "current" | "pending";

export interface Step {
  label: string;
  value: React.ReactNode;
  /** Omit for a plain sequence with no progress, such as how a result was derived. */
  state?: StepState;
}

const STATE_STYLES: Record<StepState, string> = {
  done: "border-tone-ok-border bg-tone-ok-bg/50",
  current: "border-brand-border bg-brand-soft/50",
  pending: "border-dashed border-border bg-card/60",
};

const STATE_WORDS: Record<StepState, string> = {
  done: "done",
  current: "current step",
  pending: "not yet",
};

/** A short numbered sequence: how a result was reached, or how far a record has come. */
export function StepFlow({ steps, label }: { steps: Step[]; label: string }) {
  return (
    <ol
      className={cn(
        "grid gap-2",
        steps.length === 4 ? "grid-cols-2 md:grid-cols-4" : "sm:grid-cols-3",
      )}
      aria-label={label}
    >
      {steps.map((step, index) => (
        <li
          key={step.label}
          aria-current={step.state === "current" ? "step" : undefined}
          className={cn("rounded-xl border p-3", step.state ? STATE_STYLES[step.state] : "border-border bg-card")}
        >
          <p className="flex items-center gap-1.5 text-[0.6875rem] font-medium uppercase tracking-[0.12em] text-muted-foreground">
            {step.state === "done" ? <Check className="size-3 shrink-0 text-tone-ok" aria-hidden="true" /> : null}
            {index + 1}. {step.label}
            {step.state ? <span className="sr-only">, {STATE_WORDS[step.state]}</span> : null}
          </p>
          <p
            className={cn(
              "mt-1 line-clamp-2 text-sm font-semibold",
              step.state === "pending" ? "text-muted-foreground" : "text-foreground",
            )}
          >
            {step.value}
          </p>
        </li>
      ))}
    </ol>
  );
}
