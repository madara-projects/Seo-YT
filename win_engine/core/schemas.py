from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    script: str = Field(..., description="Video script or content to analyze")
    language: str = Field(default="english", description="Selected language (english, tamil, tanglish, etc.)")
    region: str = Field(default="global", description="Target region (Global, India, Tamil Nadu, Sri Lanka, Gulf, etc.)")
    audience_type: str = Field(default="general", description="Target audience type (General, Local, Diaspora)")
    target_audience: str = Field(default="", max_length=200, description="Specific viewer the video is for")
    viewer_promise: str = Field(default="", max_length=300, description="What the viewer will get, learn, feel, or see")
    unique_angle: str = Field(default="", max_length=300, description="What makes this video different")
    proof: str = Field(default="", max_length=300, description="Proof, footage, result, or personal experience")
    video_format: str = Field(default="", max_length=80, description="Vlog, tutorial, Short, review, story, challenge, etc.")
    title_style: str = Field(default="balanced", max_length=80, description="Searchable, curiosity-led, or balanced")
    thumbnail_idea: str = Field(default="", max_length=200, description="Optional thumbnail direction")

    @field_validator("script")
    @classmethod
    def validate_script(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field 'script' cannot be empty")
        return cleaned

    @field_validator(
        "target_audience",
        "viewer_promise",
        "unique_angle",
        "proof",
        "video_format",
        "title_style",
        "thumbnail_idea",
    )
    @classmethod
    def clean_creator_brief_text(cls, value: str) -> str:
        return value.strip()


class AnalyzeResponse(BaseModel):
    title: str
    description: str
    tags: List[str]
    hashtags: List[str]
    intent: str
    content_angle: str
    title_variants: List[str]
    title_optimization: Dict[str, Any]
    content_audit: Dict[str, Any]
    cache_policy: str
    research_warnings: List[str]
    creator_brief: Dict[str, Any] = Field(default_factory=dict)
    research_queries: List[Dict[str, str]] = Field(default_factory=list)
    research_decision: Dict[str, Any] = Field(default_factory=dict)
    multilang: Dict[str, Any] = Field(default_factory=dict)
    youtube_results: List[Dict[str, Any]]
    top_opportunities: List[Dict[str, Any]]
    keyword_signals: List[Dict[str, Any]]
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
