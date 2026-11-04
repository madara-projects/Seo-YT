import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PublishedVideo } from "./HistoryDetailParts";
import { uploadedMetadataView } from "@/lib/linkedVideoFormat";
import type { LinkedVideoReport } from "@/api/historyTypes";

// A public (oEmbed) lookup read the title only: the server nulls every tag and
// description comparison and says which fields it holds (contract C3).
const PUBLIC_LOOKUP: LinkedVideoReport = {
  linked: true,
  link_id: 9,
  video_id: "publicOnly1",
  ownership_verified: false,
  youtube: { title: "Sleep better tonight", tags: null, description: null },
  package_usage: {
    attribution_status: "creator_selected",
    uploaded_title: "Sleep better tonight",
    title_match: true,
    generated_tags: ["sleep", "rest", "night routine"],
    uploaded_tags: null,
    matching_tags: null,
    missing_generated_tags: null,
    description_match_percent: null,
    uploaded_metadata_known: { title: true, tags: false, description: false },
  },
};

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

function renderReport(report: LinkedVideoReport, packageTitle = "Sleep better tonight") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PublishedVideo report={report} packageTitle={packageTitle} />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.stubGlobal("fetch", vi.fn(async () => json({}))));
afterEach(() => vi.unstubAllGlobals());

describe("uploaded metadata the lookup could not read", () => {
  it("says the tags and description were not read instead of 0 of N tags on the video", () => {
    renderReport(PUBLIC_LOOKUP);
    const usage = screen.getByTestId("package-usage");
    expect(usage).toHaveTextContent(
      "YouTube's lookup could not read the video's tags, so the package's 3 tags are not compared.",
    );
    expect(usage).toHaveTextContent(
      "YouTube's lookup could not read the video's description, so the descriptions are not compared.",
    );
    expect(usage).not.toHaveTextContent(/0 of 3/);
    // The title was read, so it is shown and compared as before.
    expect(screen.getByText("Sleep better tonight")).toBeInTheDocument();
    expect(screen.getByText("Same title as your selection")).toBeInTheDocument();
  });

  it("shows an unread title as unknown, never as matching", () => {
    renderReport({
      ...PUBLIC_LOOKUP,
      youtube: null,
      package_usage: {
        ...PUBLIC_LOOKUP.package_usage,
        uploaded_title: null,
        title_match: null,
        uploaded_metadata_known: { title: false, tags: false, description: false },
      },
    });
    expect(screen.getByTestId("uploaded-title-unknown")).toHaveTextContent("Title unknown");
    expect(screen.getByText(/could not read the video's title/)).toHaveTextContent(
      "so it is not compared with the package title “Sleep better tonight”.",
    );
    expect(screen.queryByText("Same title as your selection")).not.toBeInTheDocument();
    expect(screen.queryByText("Title changed before publishing")).not.toBeInTheDocument();
  });

  it("quotes no title when the package has none", () => {
    const unread = {
      ...PUBLIC_LOOKUP,
      youtube: null,
      package_usage: {
        ...PUBLIC_LOOKUP.package_usage,
        uploaded_title: null,
        title_match: null,
        uploaded_metadata_known: { title: false, tags: false, description: false },
      },
    };
    renderReport(unread, "");
    expect(screen.getByText(/could not read the video's title/)).toHaveTextContent(
      "YouTube's lookup could not read the video's title, so it is not compared with the package.",
    );
  });

  it("does not trust a title_match the server sent with an unknown title", () => {
    // Defensive: a known.title of false wins over a stray title and match.
    renderReport({
      ...PUBLIC_LOOKUP,
      package_usage: { ...PUBLIC_LOOKUP.package_usage, uploaded_metadata_known: { title: false, tags: true, description: true } },
    });
    expect(screen.getByTestId("uploaded-title-unknown")).toBeInTheDocument();
    expect(screen.queryByText("Same title as your selection")).not.toBeInTheDocument();
  });

  it("compares the tags once the lookup read them, an empty list included", () => {
    renderReport({
      ...PUBLIC_LOOKUP,
      youtube: { title: "Sleep better tonight", tags: [], description: "Rest well." },
      package_usage: {
        ...PUBLIC_LOOKUP.package_usage,
        uploaded_tags: [],
        matching_tags: [],
        missing_generated_tags: ["sleep", "rest", "night routine"],
        description_match_percent: 0,
        uploaded_metadata_known: { title: true, tags: true, description: true },
      },
    });
    const usage = screen.getByTestId("package-usage");
    // Read and empty is a real 0, unlike unread.
    expect(usage).toHaveTextContent("0 of 3 generated tags are on the video.");
    expect(usage).not.toHaveTextContent("could not read");
  });
});

describe("uploadedMetadataView", () => {
  it("reads an older server's report by what is stored under youtube", () => {
    // Older servers filled uploaded_title from the selected title and the tag lists with [].
    const older: LinkedVideoReport = {
      youtube: { title: null },
      package_usage: { uploaded_title: "Selected title", title_match: true, matching_tags: [], description_match_percent: 0 },
    };
    expect(uploadedMetadataView(older)).toEqual({
      title: null,
      titleMatch: null,
      tagsKnown: false,
      descriptionKnown: false,
    });
    const owned: LinkedVideoReport = {
      youtube: { title: "Owned title", tags: ["a"], description: "Text" },
      package_usage: { uploaded_title: "Owned title", title_match: false, matching_tags: [], description_match_percent: 40 },
    };
    expect(uploadedMetadataView(owned)).toEqual({
      title: "Owned title",
      titleMatch: false,
      tagsKnown: true,
      descriptionKnown: true,
    });
  });

  it("treats null comparisons as unknown even when the field is flagged as read", () => {
    const view = uploadedMetadataView({
      package_usage: {
        uploaded_title: "Read",
        title_match: null,
        matching_tags: null,
        description_match_percent: null,
        uploaded_metadata_known: { title: true, tags: true, description: true },
      },
    });
    expect(view).toEqual({ title: "Read", titleMatch: null, tagsKnown: false, descriptionKnown: false });
  });
});
