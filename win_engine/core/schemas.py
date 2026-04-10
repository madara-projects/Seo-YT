from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    script: str = Field(..., description="Video script or content to analyze")
    language: str = Field(default="english", description="Selected language (english, tamil, tanglish, etc.)")
    region: str = Field(default="global", description="Target region (Global, India, Tamil Nadu, Sri Lanka, Gulf, etc.)")
    audience_type: str = Field(default="general", description="Target audience type (General, Local, Diaspora)")

    @field_validator("script")
    @classmethod
    def validate_script(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field 'script' cannot be empty")
        return cleaned


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
