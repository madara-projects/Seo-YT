/**
 * The idea backlog (`/api/ideas`). Shapes follow `HistoryStore.content_ideas`
 * and `content_idea`, and the research evidence `build_idea_evidence` saves.
 */
import type { DemandSnapshot } from "./researchTypes";

export type IdeaStatus = "idea" | "scripted" | "package_generated" | "published" | "archived";

export interface IdeaPublicResult {
  video_id?: string | null;
  title?: string | null;
  channel_title?: string | null;
  published_at?: string | null;
  view_count?: number | string | null;
}

export interface IdeaPersonalEvidence {
  status?: string;
  learning_allowed?: boolean;
  sample_size?: number;
  confidence_label?: string;
  snapshot_window?: string;
  message?: string;
}

export interface IdeaEvidence {
  captured_at?: string;
  source?: string;
  opportunity_explanation?: string;
  signals?: {
    relevant_result_count?: number;
    research_query_count?: number;
    possible_outlier_count?: number;
    publication_dates?: string[];
  };
  personal_evidence?: IdeaPersonalEvidence;
  youtube_results?: IdeaPublicResult[];
}

export interface IdeaResearchSnapshot {
  id: number;
  captured_at?: string | null;
  evidence?: IdeaEvidence | null;
}

export interface IdeaDemandResearch {
  id: number;
  classification?: string | null;
  captured_at?: string | null;
  /** The idea's research inputs changed after this snapshot was taken. */
  stale?: boolean;
}

/** One row of `GET /api/ideas`. */
export interface IdeaSummary {
  id: number;
  topic: string;
  status: IdeaStatus | string;
  format?: string | null;
  language?: string | null;
  region?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  analysis_run_id?: number | null;
  published_video_link_id?: number | null;
  last_researched_at?: string | null;
  research_snapshot_count?: number;
  opportunity_explanation?: string | null;
}

/** `GET /api/ideas/{id}`: the full record with its research history. */
export interface Idea {
  id: number;
  topic: string;
  status: IdeaStatus | string;
  notes?: string | null;
  format?: string | null;
  language?: string | null;
  region?: string | null;
  visual_or_background?: string | null;
  on_screen_text?: string | null;
  target_duration_seconds?: number | null;
  emotion_or_intent?: string | null;
  search_angle?: string | null;
  browse_angle?: string | null;
  audience_angle?: string | null;
  analysis_run_id?: number | null;
  published_video_link_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  research_snapshots?: IdeaResearchSnapshot[];
  /** Null when never researched, or when the idea changed after its last research. */
  latest_research?: IdeaResearchSnapshot | null;
  research_is_stale?: boolean;
  latest_demand_research?: IdeaDemandResearch | null;
}

export interface IdeaListResponse {
  ideas?: IdeaSummary[];
  total?: number;
  limit?: number;
  offset?: number;
}

export interface IdeaResponse {
  status?: string;
  idea?: Idea;
}

export interface IdeaGenerateResponse {
  status?: string;
  idea?: Idea;
  analysis?: { history_run_id?: number | null };
}

export interface IdeaDemandResponse {
  status?: string;
  research?: DemandSnapshot;
}

/** Body of `POST /api/ideas`; limits mirror `CreateIdeaRequest`. */
export interface IdeaCreatePayload {
  topic: string;
  notes: string;
  format: string;
  language: string;
  region: string;
  visual_or_background: string;
  on_screen_text: string;
  target_duration_seconds: number | null;
  emotion_or_intent: string;
  search_angle: string;
  browse_angle: string;
  audience_angle: string;
  status: "idea";
}
