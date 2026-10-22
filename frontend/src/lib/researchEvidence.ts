import { asArray, asObject } from "./utils";

/** Legacy responses may lack retrieval counts; never turn unknown into zero. */
export function researchEvidence(data: unknown) {
  const value = asObject(data);
  const diagnostics = asObject(asObject(value.keyword_research).diagnostics);
  const raw = diagnostics.youtube_results_unique;
  const retrieved = typeof raw === "number" && Number.isFinite(raw) && raw >= 0 ? raw : null;
  const retained = asArray(value.youtube_results).length;
  const summary = retrieved !== null
    ? `${retrieved} unique videos retrieved; ${retained} passed relevance checks.`
    : retained ? `${retained} comparable public results available; retrieval count was not recorded.`
    : "No comparable public results are available; retrieval count was not recorded.";
  return { retrieved, retained, summary };
}
