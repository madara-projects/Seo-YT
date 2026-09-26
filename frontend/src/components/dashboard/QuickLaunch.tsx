import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Wand2, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { OptionSelect } from "@/components/common/OptionSelect";
import { Panel } from "@/components/common/Panel";
import { LANGUAGE_OPTIONS, REGION_OPTIONS, TEMPLATE_TEXT } from "@/lib/creatorConstants";

/**
 * Shortcut from the Dashboard into the Creator workflow.
 *
 * It does not call `/analyze` itself — it hands the draft to the Creator page
 * through router state, so there is exactly one place that spends quota and
 * one place that owns the eight-stage workflow.
 */
export function QuickLaunch({ className }: { className?: string }) {
  const navigate = useNavigate();
  const [script, setScript] = useState("");
  const [language, setLanguage] = useState("english");
  const [region, setRegion] = useState("global");

  const launch = () =>
    navigate("/creator", { state: { script: script.trim(), language, region } });

  return (
    <Panel
      className={className}
      icon={Zap}
      title="Start a new SEO package"
      description="Draft here, then review and generate in Creator. Nothing runs until you press Generate there."
    >
      <div className="space-y-4">
        <div className="relative">
          <Textarea
            value={script}
            onChange={(event) => setScript(event.target.value)}
            rows={4}
            aria-label="Script or video idea"
            placeholder="Paste a script excerpt, a raw idea, or a quote…"
            className="resize-none bg-elevated pb-10 text-[0.9375rem]"
          />
          <span className="numeric pointer-events-none absolute bottom-2.5 right-3 text-[0.6875rem] text-muted-foreground">
            {script.length.toLocaleString()} chars
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Wand2 className="size-3.5" aria-hidden="true" />
            Try an idea
          </span>
          {Object.entries(TEMPLATE_TEXT).map(([key, template]) => (
            <Button
              key={key}
              type="button"
              variant="outline"
              size="xs"
              className="rounded-full"
              onClick={() => setScript(template.text)}
            >
              {template.label}
            </Button>
          ))}
        </div>

        <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          {/* The Creator's own lists, so every choice made here exists there too. */}
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <OptionSelect
              ariaLabel="Output language"
              value={language}
              onValueChange={setLanguage}
              options={LANGUAGE_OPTIONS}
              className="sm:w-44"
            />
            <OptionSelect
              ariaLabel="Target region"
              value={region}
              onValueChange={setRegion}
              options={REGION_OPTIONS}
              className="sm:w-40"
            />
          </div>

          <Button variant="gradient" onClick={launch} disabled={!script.trim()}>
            Open in Creator
            <ArrowRight aria-hidden="true" />
          </Button>
        </div>
      </div>
    </Panel>
  );
}
