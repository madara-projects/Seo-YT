import { describe, expect, it } from "vitest";
import {
  durationLabel,
  ideaActions,
  ideaFormatLabel,
  ideaLanguageLabel,
  ideaLifecycle,
  ideaRegionLabel,
  ideaStatusLabel,
} from "./ideaFormat";

describe("ideaStatusLabel", () => {
  it("names every status the backend stores", () => {
    expect(ideaStatusLabel("idea").label).toBe("Idea");
    expect(ideaStatusLabel("package_generated").label).toBe("Package generated");
    expect(ideaStatusLabel("published")).toEqual({ label: "Published", tone: "ok" });
  });

  it("never invents a status", () => {
    expect(ideaStatusLabel("on_hold")).toEqual({ label: "On hold", tone: "neutral" });
    expect(ideaStatusLabel(undefined).label).toBe("Unknown");
  });
});

describe("idea labels", () => {
  it("reads the legacy form's spellings", () => {
    expect(ideaRegionLabel("in")).toBe("India");
    expect(ideaRegionLabel("global")).toBe("Global");
    expect(ideaRegionLabel("")).toBe("Global");
    expect(ideaRegionLabel("Tamil Nadu")).toBe("Tamil Nadu");
    expect(ideaFormatLabel("unknown")).toBe("Not specified");
    expect(ideaFormatLabel("youtube_shorts")).toBe("YouTube Short");
    expect(ideaLanguageLabel("tanglish")).toBe("Tanglish");
  });

  it("words a target duration", () => {
    expect(durationLabel(45)).toBe("45 sec");
    expect(durationLabel(90)).toBe("1 min 30 sec");
    expect(durationLabel(120)).toBe("2 min");
    expect(durationLabel(3900)).toBe("1 hr 5 min");
    expect(durationLabel(3600)).toBe("1 hr");
    expect(durationLabel(null)).toBe("Not specified");
    expect(durationLabel(0)).toBe("Not specified");
  });
});

describe("ideaLifecycle", () => {
  const states = (idea: Parameters<typeof ideaLifecycle>[0]) => ideaLifecycle(idea).map((step) => step.state);

  it("marks the next step as current", () => {
    expect(states({ status: "idea" })).toEqual(["done", "current", "pending", "pending"]);
    expect(states({ status: "scripted" })).toEqual(["done", "done", "current", "pending"]);
  });

  it("counts a generated package as scripted and names its run", () => {
    const steps = ideaLifecycle({ status: "package_generated", analysis_run_id: 42 });
    expect(steps.map((step) => step.state)).toEqual(["done", "done", "done", "current"]);
    expect(steps[2]?.value).toBe("Run #42");
  });

  it("finishes once published", () => {
    expect(states({ status: "published", analysis_run_id: 42, published_video_link_id: 5 })).toEqual([
      "done",
      "done",
      "done",
      "done",
    ]);
    expect(ideaLifecycle({ status: "package_generated", analysis_run_id: 42, published_video_link_id: 5 })[3]?.value).toBe(
      "Linked to YouTube",
    );
  });

  it("has no current step while archived", () => {
    expect(states({ status: "archived" })).not.toContain("current");
  });
});

describe("ideaActions", () => {
  it("only offers what the backend allows", () => {
    expect(ideaActions({ status: "archived" })).toMatchObject({
      canResearch: false,
      canGenerate: false,
      showMarkPublished: false,
      isArchived: true,
    });
    expect(ideaActions({ status: "published", published_video_link_id: 3 })).toMatchObject({
      canGenerate: false,
      showMarkPublished: false,
    });
    expect(ideaActions({ status: "scripted" }).canMarkScripted).toBe(false);
    expect(ideaActions({ status: "idea" }).canMarkScripted).toBe(true);
  });

  it("unlocks Mark published only once a video is linked", () => {
    expect(ideaActions({ status: "package_generated", analysis_run_id: 42 })).toMatchObject({
      showMarkPublished: true,
      canMarkPublished: false,
    });
    expect(ideaActions({ status: "package_generated", analysis_run_id: 42, published_video_link_id: 5 }).canMarkPublished).toBe(
      true,
    );
  });

  it("restores to the furthest status the record still proves", () => {
    expect(ideaActions({ status: "archived", analysis_run_id: 42 }).restoreTo).toBe("package_generated");
    expect(ideaActions({ status: "archived" }).restoreTo).toBe("idea");
  });
});
