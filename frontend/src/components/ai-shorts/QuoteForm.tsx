import { Loader2, Quote, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { OptionSelect } from "@/components/common/OptionSelect";
import { Panel } from "@/components/common/Panel";
import { cn } from "@/lib/utils";
import {
  AI_SHORTS_LANGUAGE_OPTIONS,
  MOOD_MAX,
  PART_OPTIONS,
  QUOTE_MAX,
  QUOTE_MIN,
  SECONDS_PER_PART,
  partsLabel,
  quoteBlocker,
  type AiShortsFormValues,
} from "@/lib/aiShortsFormat";

/** Keyboard focus on the hidden radio shows on the card that holds it. */
const FOCUS_RING = "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring";

/**
 * The only input the page asks for: the quote, with an optional mood, the
 * number of 8-second parts and the package language. The button is disabled
 * with its reason until the quote is valid, so nothing fails on the server
 * that the field could have said.
 */
export function QuoteForm({
  values,
  onChange,
  onSubmit,
  isPending,
}: {
  values: AiShortsFormValues;
  onChange: (patch: Partial<AiShortsFormValues>) => void;
  onSubmit: () => void;
  isPending: boolean;
}) {
  const blocker = quoteBlocker(values);
  const quoteLength = values.quote.trim().length;
  const over = quoteLength > QUOTE_MAX;

  return (
    <Panel
      icon={Quote}
      title="Your quote"
      description="The only thing to type. Gemini writes one Veo 3.1 prompt per 8-second part, and the package to upload with."
    >
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          if (!blocker && !isPending) onSubmit();
        }}
      >
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <Label htmlFor="ai-shorts-quote">Quote</Label>
            <span
              className={cn("numeric text-[0.6875rem]", over ? "font-semibold text-tone-bad" : "text-muted-foreground")}
              aria-live="polite"
            >
              {quoteLength} / {QUOTE_MAX}
            </span>
          </div>
          <Textarea
            id="ai-shorts-quote"
            rows={5}
            value={values.quote}
            onChange={(event) => onChange({ quote: event.target.value })}
            placeholder="Type the quote exactly as it should appear on screen…"
            aria-invalid={over}
            aria-describedby="ai-shorts-quote-help"
            className="min-h-32 resize-y bg-elevated text-[0.9375rem]"
          />
          <p id="ai-shorts-quote-help" className="text-xs leading-relaxed text-muted-foreground">
            {QUOTE_MIN}–{QUOTE_MAX} characters. Kept word for word; the prompts and package are written around it.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="ai-shorts-mood" className="flex items-baseline gap-1.5">
            Mood or scene wish
            <span className="text-xs font-normal text-muted-foreground">Optional</span>
          </Label>
          <Input
            id="ai-shorts-mood"
            value={values.moodHint}
            onChange={(event) => onChange({ moodHint: event.target.value })}
            placeholder="rain on a window at night, no people"
            maxLength={MOOD_MAX}
            autoComplete="off"
          />
        </div>

        <fieldset className="space-y-2">
          <legend className="text-[0.8125rem] font-medium leading-none text-foreground">Length</legend>
          <div className="grid grid-cols-3 gap-2 pt-2">
            {PART_OPTIONS.map((parts) => {
              const checked = values.parts === parts;
              return (
                <label
                  key={parts}
                  className={cn(
                    "flex min-w-0 cursor-pointer flex-col items-center gap-0.5 rounded-xl border px-2 py-2.5 text-center transition-[border-color,background-color,box-shadow] duration-150",
                    FOCUS_RING,
                    checked
                      ? "border-brand-border bg-brand-soft/60 shadow-card"
                      : "border-border bg-card hover:border-foreground/25 hover:bg-accent/40",
                  )}
                >
                  <input
                    type="radio"
                    name="ai-shorts-parts"
                    value={parts}
                    checked={checked}
                    onChange={() => onChange({ parts })}
                    className="sr-only"
                    aria-label={partsLabel(parts)}
                  />
                  <span className="font-display text-base font-semibold text-foreground">
                    {parts} {parts === 1 ? "part" : "parts"}
                  </span>
                  <span className="numeric text-xs text-muted-foreground">{parts * SECONDS_PER_PART} s</span>
                </label>
              );
            })}
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Flow makes 8-second clips; the parts chain with Extend into one Short.
          </p>
        </fieldset>

        <div className="space-y-2">
          <Label htmlFor="ai-shorts-language">Package language</Label>
          <OptionSelect
            id="ai-shorts-language"
            ariaLabel="Package language"
            value={values.language}
            onValueChange={(language) => onChange({ language })}
            options={AI_SHORTS_LANGUAGE_OPTIONS}
          />
          <p className="text-xs text-muted-foreground">For the title, description and tags.</p>
        </div>

        <div className="space-y-2 border-t border-border pt-4">
          <Button
            type="submit"
            variant="gradient"
            size="lg"
            className="w-full"
            disabled={Boolean(blocker) || isPending}
            aria-describedby="ai-shorts-reason"
          >
            {isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Wand2 aria-hidden="true" />}
            {isPending ? "Writing…" : "Write Flow prompts"}
          </Button>
          <p id="ai-shorts-reason" className="text-xs leading-relaxed text-muted-foreground" aria-live="polite">
            {blocker ?? "Uses 2–4 Gemini calls. No YouTube quota."}
          </p>
        </div>
      </form>
    </Panel>
  );
}
