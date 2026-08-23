/**
 * Explicit frontend state shared by the extracted modules.
 * Transient workflow values stay in memory; explicit package selection is
 * persisted by the Phase 4 History endpoint.
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
    selectionStatus: "unrecorded",
    selectionError: null,
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
