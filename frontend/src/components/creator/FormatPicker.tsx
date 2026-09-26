import type { UseFormReturn } from "react-hook-form";
import { MonitorPlay, Smartphone, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { FORMAT_CHOICES, LONG_TYPES, type FormatChoice } from "@/lib/creatorConstants";
import { isFormatChoice, type CreatorFormValues } from "@/schemas/creator";

const ICONS: Record<FormatChoice, React.ElementType> = {
  short: Smartphone,
  long: MonitorPlay,
  auto: Wand2,
};

/** Keyboard focus on the hidden radio shows on the card that holds it. */
const FOCUS_RING = "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring";

/** What choosing this format changes, in one line, for the summary beside the form. */
export function formatConsequence(choice: FormatChoice): string {
  return FORMAT_CHOICES.find((option) => option.value === choice)?.consequence ?? "";
}

/**
 * What the creator is making, asked first because it changes the whole
 * package. Native radio inputs, so the group is one tab stop and the arrow
 * keys move the choice, as every screen reader expects of a radio group.
 * Compact on purpose: icon beside the words, and a long video's kind on one
 * line below, so the whole setup fits on one screen.
 */
export function FormatPicker({
  form,
  showConsequence = true,
}: {
  form: UseFormReturn<CreatorFormValues>;
  /** Off where a summary panel beside the form already says it. */
  showConsequence?: boolean;
}) {
  const choice = form.watch("format_choice");
  const longType = form.watch("long_type");
  const [short, long, auto] = FORMAT_CHOICES;

  const card = (option: (typeof FORMAT_CHOICES)[number]) => {
    const Icon = ICONS[option.value];
    const checked = choice === option.value;
    return (
      <label
        key={option.value}
        className={cn(
          "relative flex min-w-0 cursor-pointer items-center gap-3 rounded-2xl border bg-card px-3.5 py-3 text-left transition-[border-color,background-color,box-shadow] duration-150",
          FOCUS_RING,
          checked
            ? "border-brand-border bg-brand-soft/60 shadow-card"
            : "border-border hover:border-foreground/25 hover:bg-accent/40",
        )}
      >
        <input type="radio" value={option.value} className="sr-only" {...form.register("format_choice")} />
        <span
          className={cn(
            "grid size-10 shrink-0 place-items-center rounded-xl",
            checked ? "bg-brand-gradient text-white" : "bg-muted text-muted-foreground",
          )}
          aria-hidden="true"
        >
          <Icon className="size-5" />
        </span>
        <span className="min-w-0">
          <span className="block font-display text-base font-semibold text-foreground">{option.label}</span>
          <span className="block text-[0.8125rem] leading-snug text-muted-foreground">{option.detail}</span>
        </span>
      </label>
    );
  };

  return (
    <fieldset className="space-y-3">
      <legend className="mb-3 font-display text-base font-semibold tracking-tight text-foreground">
        What are you making?
      </legend>
      <div className="grid gap-3 sm:grid-cols-2">
        {short ? card(short) : null}
        {long ? card(long) : null}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {auto ? (
          <label
            className={cn(
              "flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-[0.8125rem] font-medium transition-[border-color,background-color,color] duration-150",
              FOCUS_RING,
              choice === "auto"
                ? "border-brand-border bg-brand-soft text-foreground"
                : "border-border bg-card text-muted-foreground hover:text-foreground",
            )}
          >
            <input type="radio" value={auto.value} className="sr-only" {...form.register("format_choice")} />
            <Wand2 className="size-3.5" aria-hidden="true" />
            {auto.label}
          </label>
        ) : null}

        {choice === "long" ? (
          <fieldset className="flex min-w-0 flex-wrap items-center gap-1.5">
            <legend className="sr-only">Kind of long video (optional)</legend>
            <span className="mr-0.5 text-xs font-medium text-muted-foreground" aria-hidden="true">
              Kind:
            </span>
            {LONG_TYPES.map((type) => (
              <label
                key={type.value}
                className={cn(
                  "cursor-pointer rounded-full border px-2.5 py-1 text-xs font-medium transition-[border-color,background-color,color] duration-150",
                  FOCUS_RING,
                  longType === type.value
                    ? "border-brand-border bg-brand-soft text-foreground"
                    : "border-border bg-card text-muted-foreground hover:text-foreground",
                )}
              >
                <input type="radio" value={type.value} className="sr-only" {...form.register("long_type")} />
                {type.label}
              </label>
            ))}
          </fieldset>
        ) : null}
      </div>

      {showConsequence && isFormatChoice(choice) ? (
        <p className="text-[0.8125rem] leading-relaxed text-muted-foreground" aria-live="polite">
          <span className="font-medium text-foreground">{choice === "auto" ? "Detected:" : "What this changes:"}</span>{" "}
          {formatConsequence(choice)}
        </p>
      ) : null}
    </fieldset>
  );
}
