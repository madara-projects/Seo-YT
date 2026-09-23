import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChecklistStage } from "./ChecklistStage";
import { CHECKLIST_ITEMS, freshChecklist } from "@/lib/creatorConstants";
import type { PackageOption } from "@/api/types";

const option: PackageOption = {
  id: "package-a",
  label: "Package A",
  primary: true,
  title: "A selected title",
  description: "Description",
  tags: ["one"],
  hashtags: ["#one"],
  language: "english",
  thumbnailText: "",
  thumbnailVisual: "",
  viewerPromise: "",
  whySuggested: "Because",
  approach: "direct",
  packageIntent: "Primary",
  bestFor: "Search",
  misleadingRisk: "low",
  qualityStatus: "pass",
  titleQualityScore: 8,
  source: "AI suggestion",
  mechanism: "direct topic framing",
  reason: "reason",
};

describe("ChecklistStage", () => {
  it("prompts for a selection when none exists", () => {
    render(
      <ChecklistStage
        selected={null}
        checklist={freshChecklist()}
        onToggle={vi.fn()}
        onExport={vi.fn()}
      />,
    );
    expect(screen.getByText("No package selected")).toBeInTheDocument();
  });

  it("reports progress and blocks completion until every item is confirmed", () => {
    const partial = { ...freshChecklist(), title: true, description: true };
    render(
      <ChecklistStage
        selected={option}
        checklist={partial}
        onToggle={vi.fn()}
        onExport={vi.fn()}
      />,
    );

    expect(screen.getByText(`2 / ${CHECKLIST_ITEMS.length} confirmed`)).toBeInTheDocument();
    expect(screen.getByText("Manual review still required")).toBeInTheDocument();
  });

  it("confirms completion only when all items are checked", () => {
    const complete = Object.fromEntries(
      CHECKLIST_ITEMS.map((item) => [item.key, true]),
    ) as ReturnType<typeof freshChecklist>;

    render(
      <ChecklistStage
        selected={option}
        checklist={complete}
        onToggle={vi.fn()}
        onExport={vi.fn()}
      />,
    );
    expect(screen.getByText("Manual review completed")).toBeInTheDocument();
  });

  it("reports the toggled key to the caller", async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();

    render(
      <ChecklistStage
        selected={option}
        checklist={freshChecklist()}
        onToggle={onToggle}
        onExport={vi.fn()}
      />,
    );

    const first = CHECKLIST_ITEMS[0]!;
    await user.click(screen.getByRole("checkbox", { name: first.label }));
    expect(onToggle).toHaveBeenCalledWith(first.key, true);
  });

  it("keeps the manual-publishing disclaimer visible", () => {
    render(
      <ChecklistStage
        selected={option}
        checklist={freshChecklist()}
        onToggle={vi.fn()}
        onExport={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/does not upload, publish, or guarantee views/i),
    ).toBeInTheDocument();
  });
});
