import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { ScoreCalibration } from "@/api/opportunityTypes";
import { historyKeys } from "./queryKeys";

/**
 * Whether past Opportunity Scores went with more views in comparable
 * published videos. Kept under the History keys, so linking a video or
 * deleting a package (invalidatePackageViews) refreshes it too.
 */
export function useScoreCalibration() {
  return useQuery({
    queryKey: [...historyKeys.all, "score-calibration"] as const,
    queryFn: ({ signal }) => apiRequest<ScoreCalibration>("/api/opportunity-score/calibration", { signal }),
  });
}
