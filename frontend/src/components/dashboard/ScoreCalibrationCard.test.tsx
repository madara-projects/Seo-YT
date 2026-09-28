import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ScoreCalibrationCard } from "./ScoreCalibrationCard";
import {
  INSUFFICIENT_CALIBRATION,
  NEGATIVE_CALIBRATION,
  NO_RELATIONSHIP_CALIBRATION,
  POSITIVE_CALIBRATION,
} from "@/test/fixtures/opportunity";

const PREDICTION_CLAIM = /(?<!not a )predict(s|ed|ion)? (of )?(views|reach|ctr)|expected views|will get \d|guarantee/i;

let body: unknown;
let status: number;

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ScoreCalibrationCard />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  status = 200;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url) !== "/api/opportunity-score/calibration") throw new Error(`Unexpected request ${url}`);
      return { ok: status < 400, status, text: async () => JSON.stringify(body) };
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("ScoreCalibrationCard", () => {
  it("says honestly when there is not enough evidence, and what is needed", async () => {
    body = INSUFFICIENT_CALIBRATION;
    const { container } = renderCard();

    expect(screen.getByRole("heading", { name: "Does the Opportunity Score track your results?" })).toBeInTheDocument();
    expect(await screen.findByText("Not enough evidence yet")).toBeInTheDocument();
    expect(screen.getByText(/no association is claimed/)).toBeInTheDocument();
    expect(screen.getByText(/Needs at least 5 published videos/)).toBeInTheDocument();
    expect(screen.getByText("3 of 5 comparable videos in the largest group")).toBeInTheDocument();
    expect(screen.getByText(/24-hour window: 3 · 7-day window: 0 · 28-day window: 0/)).toBeInTheDocument();
    expect(screen.getByText(/1 not ownership-verified · 2 without a completed snapshot/)).toBeInTheDocument();
    expect(screen.queryByTestId("calibration-recommendation")).not.toBeInTheDocument();
    expect(container.textContent).toMatch(/not causation/);
    expect(container.textContent).not.toMatch(PREDICTION_CLAIM);
  });

  it("reports an association and a keep recommendation when higher scores did better", async () => {
    body = POSITIVE_CALIBRATION;
    const { container } = renderCard();

    expect(await screen.findByText("Higher scores did better")).toBeInTheDocument();
    expect(screen.getByTestId("calibration-recommendation")).toHaveTextContent("Keep");
    expect(screen.getByText(/rank correlation \+0\.82/)).toBeInTheDocument();
    const group = screen.getByTestId("calibration-group");
    expect(group).toHaveTextContent("YouTube Short · English");
    expect(group).toHaveTextContent("Higher-scoring: median 610 views (5)");
    expect(group).toHaveTextContent("Lower-scoring: median 180 views (5)");
    expect(container.textContent).toMatch(/association/);
    expect(container.textContent).not.toMatch(PREDICTION_CLAIM);
  });

  it("recommends recalibrating when there is no clear relationship", async () => {
    body = NO_RELATIONSHIP_CALIBRATION;
    renderCard();

    expect(await screen.findByText("No clear relationship")).toBeInTheDocument();
    expect(screen.getByTestId("calibration-recommendation")).toHaveTextContent("Recalibrate");
  });

  it("recommends retiring the score when lower scores did better", async () => {
    body = NEGATIVE_CALIBRATION;
    renderCard();

    expect(await screen.findByText("Lower scores did better")).toBeInTheDocument();
    expect(screen.getByTestId("calibration-recommendation")).toHaveTextContent("Retire");
  });

  it("shows a failed or empty response as unavailable, not as a verdict", async () => {
    body = {};
    renderCard();
    expect(await screen.findByText(/calibration is unavailable right now/i)).toBeInTheDocument();
    expect(screen.queryByText("Not enough evidence yet")).not.toBeInTheDocument();
  });
});
