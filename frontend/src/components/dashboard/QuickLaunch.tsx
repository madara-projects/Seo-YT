import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TEMPLATE_TEXT } from "@/lib/creatorConstants";

/**
 * Shortcut from the Dashboard into the Creator workflow.
 *
 * It does not call `/analyze` itself — it hands the draft to the Creator page
 * through router state, so there is exactly one place that spends quota and
 * one place that owns the eight-stage workflow.
 */
export function QuickLaunch() {
  const navigate = useNavigate();
  const [script, setScript] = useState("");
  const [language, setLanguage] = useState("english");
  const [region, setRegion] = useState("global");

  const launch = () =>
    navigate("/creator", { state: { script: script.trim(), language, region } });

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-primary" aria-hidden="true" />
          Start a new SEO package
        </CardTitle>
        <span className="text-[11px] text-muted-foreground">
          Gemini when configured, local fallback otherwise
        </span>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Try an idea
          </span>
          {Object.entries(TEMPLATE_TEXT).map(([key, template]) => (
            <Button
              key={key}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setScript(template.text)}
            >
              {template.label}
            </Button>
          ))}
        </div>

        <Textarea
          value={script}
          onChange={(event) => setScript(event.target.value)}
          rows={3}
          aria-label="Script or video idea"
          placeholder="Paste a script excerpt, raw idea, or quote…"
        />

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-2">
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="w-36" aria-label="Output language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="english">English</SelectItem>
                <SelectItem value="tamil">Tamil</SelectItem>
                <SelectItem value="tanglish">Tanglish</SelectItem>
              </SelectContent>
            </Select>
            <Select value={region} onValueChange={setRegion}>
              <SelectTrigger className="w-36" aria-label="Target region">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="global">Global</SelectItem>
                <SelectItem value="india">India</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button onClick={launch} disabled={!script.trim()}>
            <Zap aria-hidden="true" />
            Open in Creator
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
