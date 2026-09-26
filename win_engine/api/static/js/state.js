/**
 * Explicit frontend state shared by the extracted modules.
 * Transient workflow values stay in memory; explicit package selection is
 * persisted by the Phase 4 History endpoint.
 */
export const frontendState = {
  historySummaryCache: null,
  historySummaryFetchedAt: 0,
  historySummaryRequest: null,
  // Bumped by every invalidation; a request started before one is stale.
  historySummaryGeneration: 0,
  // Kept across cache invalidation so channel cards never flash empty.
  latestOwnedPerformance: null,
  latestChannelStatus: null,
  channelStatusFailed: false,
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
    researchStatus: "no-research",
    researchError: null,
    requestSequence: 0,
  },
};

export const creatorState = frontendState.creator;

export function invalidateHistorySummary() {
  frontendState.historySummaryGeneration += 1;
  frontendState.historySummaryCache = null;
  frontendState.historySummaryFetchedAt = 0;
  frontendState.historySummaryRequest = null;
}
