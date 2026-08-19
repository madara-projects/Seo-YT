/**
 * Explicit frontend state shared by the extracted modules.
 * Values are intentionally in-memory only; the backend remains the source of
 * truth and no browser persistence is introduced by Phase 3C.
 */
export const frontendState = {
  historySummaryCache: null,
  historySummaryFetchedAt: 0,
  historySummaryRequest: null,
  latestChannelStatus: null,
  analyticsRefreshRequest: null,
  analyticsAutoRefreshAttempted: false,
  oauthRedirectHandled: false,
  lastRoutedHash: "",
  lastRoutedAt: 0,
  creator: {
    stage: "idea",
    formValues: {},
    submittedFormValues: null,
    inferredBrief: null,
    analysis: null,
    generatedPackage: null,
    packageOptions: [],
    selectedPackageId: null,
    checklist: {
      title: false,
      description: false,
      tags: false,
      hashtags: false,
      thumbnail: false,
      promise: false,
      claims: false,
      manualPublish: false,
    },
    generationStatus: "idle",
    researchStatus: "no-research",
    researchError: null,
    error: null,
    requestSequence: 0,
    activeRequestSequence: 0,
    initialized: false,
  },
};

export const creatorState = frontendState.creator;

export function invalidateHistorySummary() {
  frontendState.historySummaryCache = null;
  frontendState.historySummaryFetchedAt = 0;
  frontendState.historySummaryRequest = null;
}
