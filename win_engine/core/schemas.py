from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from win_engine.analysis.text_tokens import unicode_words
from win_engine.core.regions import REGION_ALIASES


def normalize_region(value: str) -> str:
    key = value.strip().casefold()
    return REGION_ALIASES.get(key, key)


def _require_words(value: str) -> str:
    # Emoji or punctuation alone gives research nothing to search for, and the
    # search would spend its quota before generation could say so.
    if not unicode_words(value, min_length=1):
        raise ValueError("Enter at least one word.")
    return value


class _Request(BaseModel):
    # Whitespace is stripped before length checks, so "   " cannot pass min_length=1.
    model_config = ConfigDict(str_strip_whitespace=True)


class AnalyzeRequest(_Request):
    script: str = Field(..., min_length=1, max_length=12000, description="Video script or content to analyze")
    video_language: str = Field(default="english", max_length=40, description="Spoken language in the video (english, tamil)")
    language: str = Field(default="english", max_length=40, description="Selected SEO output language (english, tamil, tanglish, etc.)")
    region: str = Field(default="global", max_length=40, description="Target region (global, india, us, etc.)")
    audience_type: str = Field(default="general", max_length=40, description="Target audience type (General, Local, Diaspora)")
    target_audience: str = Field(default="", max_length=200, description="Specific viewer the video is for")
    viewer_promise: str = Field(default="", max_length=300, description="What the viewer will get, learn, feel, or see")
    unique_angle: str = Field(default="", max_length=300, description="What makes this video different")
    proof: str = Field(default="", max_length=300, description="Proof, footage, result, or personal experience")
    video_format: str = Field(default="", max_length=80, description="Vlog, tutorial, Short, review, story, challenge, etc.")
    title_style: str = Field(default="balanced", max_length=80, description="Searchable, curiosity-led, or balanced")
    thumbnail_idea: str = Field(default="", max_length=200, description="Optional thumbnail direction")
    duration_seconds: float | None = Field(default=None, ge=1, le=86400)
    exact_quote: str = Field(default="", max_length=2000)
    on_screen_text: str = Field(default="", max_length=2000)
    voice_over: str = Field(default="", max_length=20, description="present, none, or unknown")
    visual_requirements: str = Field(default="", max_length=500)
    factual_claims: str = Field(default="", max_length=1000)
    claim_restrictions: str = Field(default="", max_length=1000)
    creator_intent: str = Field(default="", max_length=500)
    content_constraints: str = Field(default="", max_length=1000)

    @field_validator("region")
    @classmethod
    def normalize_analyze_region(cls, value: str) -> str:
        return normalize_region(value) or "global"

    @field_validator("script")
    @classmethod
    def script_has_words(cls, value: str) -> str:
        return _require_words(value)


class AnalyzeResponse(BaseModel):
    title: str
    description: str
    tags: List[str]
    hashtags: List[str]
    intent: str
    content_angle: str
    title_variants: List[str]
    title_optimization: Dict[str, Any]
    title_thumbnail_packages: List[Dict[str, Any]] = Field(default_factory=list)
    content_audit: Dict[str, Any]
    cache_policy: str
    research_warnings: List[str]
    generation_source: str = "fallback"
    creator_brief: Dict[str, Any] = Field(default_factory=dict)
    research_queries: List[Dict[str, str]] = Field(default_factory=list)
    research_decision: Dict[str, Any] = Field(default_factory=dict)
    multilang: Dict[str, Any] = Field(default_factory=dict)
    youtube_results: List[Dict[str, Any]]
    top_opportunities: List[Dict[str, Any]]
    keyword_signals: List[Dict[str, Any]]
    keyword_research: Dict[str, Any] = Field(default_factory=dict)
    entity_signals: List[Dict[str, Any]]
    upload_timing: Dict[str, Any]
    thumbnail_intelligence: Dict[str, Any]
    opportunity_gap_analysis: Dict[str, Any]
    competitor_shadow: Dict[str, Any]
    language_strategy: Dict[str, Any]
    pacing_analysis: Dict[str, Any]
    channel_intelligence: Dict[str, Any]
    content_graph_strategy: Dict[str, Any]
    thumbnail_strategy: Dict[str, Any]
    chapters: List[Dict[str, str]]
    session_expansion: Dict[str, Any]
    binge_bridge: str
    automation_workflow: Dict[str, Any]
    performance_sync: Dict[str, Any]
    learning_engine: Dict[str, Any]
    winning_patterns: Dict[str, Any]
    ctr_prediction: Dict[str, Any]
    ab_test_pack: Dict[str, str]
    internal_scorecard: Dict[str, Any]
    historical_comparison: Dict[str, Any]
    history_run_id: int | None = None
    generation_quality: Dict[str, Any] = Field(default_factory=dict)
    personalization: Dict[str, Any] = Field(default_factory=dict)
    generation_trace: Dict[str, Any] = Field(default_factory=dict)
    retention_assistant: Dict[str, Any] = Field(default_factory=dict)


class DeleteHistoryRunsRequest(_Request):
    run_ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("run_ids")
    @classmethod
    def validate_run_ids(cls, values: List[int]) -> List[int]:
        unique = list(dict.fromkeys(values))
        if any(value <= 0 for value in unique):
            raise ValueError("Every history run ID must be a positive integer.")
        return unique


def _utc_timestamp(value: str | None) -> str | None:
    """An ISO-8601 time with a zone, stored in UTC so times compare correctly."""
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Use an ISO-8601 date and time, for example 2026-09-01T18:30:00+05:30.") from exc
    if parsed.tzinfo is None:
        raise ValueError("Include a time zone, for example 2026-09-01T18:30:00+05:30 or ...Z for UTC.")
    return parsed.astimezone(timezone.utc).isoformat()


class LinkVideoRequest(_Request):
    youtube_video_id: str = Field(..., min_length=11, max_length=200)
    published_at: str | None = Field(default=None, max_length=40)
    selected_title: str | None = Field(default=None, max_length=100)
    selected_thumbnail_package: str | None = Field(default=None, max_length=100)
    selected_description: str | None = Field(default=None, max_length=5000)
    selected_tags: List[str] = Field(default_factory=list, max_length=12)
    selected_hashtags: List[str] = Field(default_factory=list, max_length=3)
    format: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    # Relinking deletes the evidence collected for the package's current video.
    replace_existing_evidence: bool = False

    @field_validator("published_at")
    @classmethod
    def parse_published_at(cls, value: str | None) -> str | None:
        return _utc_timestamp(value)

    @field_validator("selected_tags", "selected_hashtags")
    @classmethod
    def bound_tags(cls, values: List[str]) -> List[str]:
        if any(len(value) > 100 for value in values):
            raise ValueError("Each tag must be at most 100 characters.")
        return values

    @field_validator("region")
    @classmethod
    def normalize_link_region(cls, value: str | None) -> str | None:
        return normalize_region(value) if value else value


class UpdatePublishedVideoRequest(_Request):
    selected_title: str | None = Field(default=None, max_length=100)
    selected_thumbnail_package: str | None = Field(default=None, max_length=100)
    selected_description: str | None = Field(default=None, max_length=5000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_a_change(self):
        if not any(getattr(self, field) is not None for field in self.model_fields_set):
            raise ValueError("Provide at least one field to update.")
        return self


class ComparableMetadataRequest(_Request):
    language: str | None = Field(default=None, max_length=40)
    format: str | None = Field(default=None, max_length=40)
    duration_bucket: str | None = Field(default=None, max_length=30)
    topic_category: str | None = Field(default=None, max_length=80)


class SelectPackageRequest(_Request):
    package_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


IdeaStatus = Literal["idea", "scripted", "package_generated", "published", "archived"]


class CreateIdeaRequest(_Request):
    topic: str = Field(..., min_length=1, max_length=300)
    notes: str = Field(default="", max_length=5000)
    format: str = Field(default="unknown", max_length=40)
    language: str = Field(default="english", max_length=40)
    region: str = Field(default="global", max_length=40)
    visual_or_background: str = Field(default="", max_length=1000)
    on_screen_text: str = Field(default="", max_length=2000)
    target_duration_seconds: float | None = Field(default=None, ge=1, le=86400)
    emotion_or_intent: str = Field(default="", max_length=300)
    search_angle: str = Field(default="", max_length=500)
    browse_angle: str = Field(default="", max_length=500)
    audience_angle: str = Field(default="", max_length=500)
    status: IdeaStatus = "idea"

    @field_validator("region")
    @classmethod
    def normalize_idea_region(cls, value: str) -> str:
        return normalize_region(value) or "global"

    @field_validator("topic")
    @classmethod
    def topic_has_words(cls, value: str) -> str:
        return _require_words(value)


class UpdateIdeaRequest(_Request):
    topic: str | None = Field(default=None, min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=5000)
    format: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=40)
    visual_or_background: str | None = Field(default=None, max_length=1000)
    on_screen_text: str | None = Field(default=None, max_length=2000)
    target_duration_seconds: float | None = Field(default=None, ge=1, le=86400)
    emotion_or_intent: str | None = Field(default=None, max_length=300)
    search_angle: str | None = Field(default=None, max_length=500)
    browse_angle: str | None = Field(default=None, max_length=500)
    audience_angle: str | None = Field(default=None, max_length=500)
    status: IdeaStatus | None = None

    @field_validator("region")
    @classmethod
    def normalize_idea_region(cls, value: str | None) -> str | None:
        return (normalize_region(value) or "global") if isinstance(value, str) else value

    @field_validator("topic")
    @classmethod
    def topic_has_words(cls, value: str | None) -> str | None:
        return _require_words(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_an_update(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one idea field to update.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Idea fields cannot be set to null.")
        return self


class GenerateIdeaRequest(_Request):
    script: str = Field(default="", max_length=12000)


class CreateWatchChannelRequest(_Request):
    channel_id: str = Field(..., min_length=3, max_length=100)
    notes: str = Field(default="", max_length=2000)


class CreateWatchVideoRequest(_Request):
    video_id: str = Field(..., min_length=11, max_length=200)
    notes: str = Field(default="", max_length=2000)


class UpdateWatchRequest(_Request):
    notes: str | None = Field(default=None, max_length=2000)
    state: Literal["active", "archived"] | None = None

    @model_validator(mode="after")
    def valid_watch_update(self):
        if not self.model_fields_set:
            raise ValueError("Provide a watchlist update.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Watchlist fields cannot be null.")
        return self


class DemandResearchRequest(_Request):
    topic: str = Field(..., min_length=1, max_length=300)
    language: str = Field(default="", max_length=40)
    format: str = Field(default="", max_length=40)
    region: str = Field(default="", max_length=40)
    audience_context: str = Field(default="", max_length=500)

    @field_validator("region")
    @classmethod
    def normalize_demand_region(cls, value: str) -> str:
        return normalize_region(value)

    @field_validator("topic")
    @classmethod
    def topic_has_words(cls, value: str) -> str:
        return _require_words(value)


class RecordExperimentRequest(_Request):
    youtube_video_id: str = Field(..., min_length=11, max_length=11)
    old_title: str | None = Field(default=None, max_length=100)
    new_title: str | None = Field(default=None, max_length=100)
    old_thumbnail: str | None = Field(default=None, max_length=1000)
    new_thumbnail: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=1000)
    performance_before: Dict[str, Any] = Field(default_factory=dict, max_length=40)


ExperimentStatus = Literal["draft", "planned", "active", "paused", "completed", "cancelled", "inconclusive"]
ExperimentMode = Literal["controlled", "observational"]
ExperimentRole = Literal["control", "variant", "observational_reference"]
ExperimentMetric = Literal["views", "average_view_percentage", "likes", "comments", "engagement_rate"]
# Fewer videos per group than this never supports a comparison (see audit_experiment).
MINIMUM_GROUP_SAMPLE = 5


def _iso_date(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10]).isoformat()
    except ValueError as exc:
        raise ValueError("Use an ISO date, for example 2026-09-01.") from exc


class CreateStructuredExperimentRequest(_Request):
    name: str = Field(..., min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    hypothesis: str = Field(..., min_length=1, max_length=1000)
    mode: ExperimentMode = "controlled"
    status: ExperimentStatus = "draft"
    variable: str = Field(..., min_length=1, max_length=100)
    variable_category: str = Field(default="", max_length=100)
    control_definition: str = Field(..., min_length=1, max_length=1000)
    variant_definition: str = Field(..., min_length=1, max_length=1000)
    success_metric: ExperimentMetric = "views"
    secondary_metrics: list[ExperimentMetric] = Field(default_factory=list, max_length=4)
    target_sample_size: int | None = Field(default=None, ge=2 * MINIMUM_GROUP_SAMPLE, le=1000)
    minimum_sample_size: int = Field(default=MINIMUM_GROUP_SAMPLE, ge=MINIMUM_GROUP_SAMPLE, le=100)
    observation_window: Literal["24h", "7d", "28d"] = "24h"
    start_date: str | None = Field(default=None, max_length=40)
    end_date: str | None = Field(default=None, max_length=40)
    notes: str = Field(default="", max_length=3000)

    @field_validator("start_date", "end_date")
    @classmethod
    def parse_dates(cls, value: str | None) -> str | None:
        return _iso_date(value)

    @model_validator(mode="after")
    def validate_experiment(self):
        self.secondary_metrics = list(dict.fromkeys(metric for metric in self.secondary_metrics if metric != self.success_metric))
        if self.target_sample_size is not None and self.target_sample_size < self.minimum_sample_size * 2:
            raise ValueError("Target sample size must cover the minimum control and variant samples.")
        if self.status not in {"draft", "planned"}:
            raise ValueError("New experiments must start as draft or planned.")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("The end date cannot be before the start date.")
        return self


class UpdateStructuredExperimentRequest(_Request):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    hypothesis: str | None = Field(default=None, min_length=1, max_length=1000)
    status: ExperimentStatus | None = None
    target_sample_size: int | None = Field(default=None, ge=2 * MINIMUM_GROUP_SAMPLE, le=1000)
    start_date: str | None = Field(default=None, max_length=40)
    end_date: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=3000)

    @field_validator("start_date", "end_date")
    @classmethod
    def parse_dates(cls, value: str | None) -> str | None:
        return _iso_date(value)

    @model_validator(mode="after")
    def require_experiment_update(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one experiment update.")
        # A blank or null date clears it, as a new experiment may have none;
        # every other field keeps a value.
        if any(getattr(self, field) is None for field in self.model_fields_set - {"start_date", "end_date"}):
            raise ValueError("Experiment fields cannot be set to null.")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("The end date cannot be before the start date.")
        return self


class AssignExperimentVideoRequest(_Request):
    published_video_link_id: int = Field(..., ge=1)
    role: ExperimentRole
    notes: str = Field(default="", max_length=1000)
