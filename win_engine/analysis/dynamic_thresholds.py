"""
Dynamic Threshold Calculator v2.0
Replaces hard-coded thresholds with data-driven, niche-specific values
"""

from __future__ import annotations
from typing import Any
import statistics


class DynamicThresholdCalculator:
    """Calculate scoring thresholds dynamically from historical data."""

    def __init__(self, historical_data: list[dict[str, Any]] | None = None):
        """
        Initialize with historical performance data.
        
        Expected fields:
        - outlier_score: float
        - views: int
        - subscribers: int
        - competition_label: str (SATURATED|COMPETITIVE|UNDERSERVED)
        - success: bool (did this video perform well?)
        - niche: str
        """
        self.historical_data = historical_data or []
        self.thresholds = self._calculate_thresholds()

    def get_outlier_score_threshold(self, niche: str = "general", competition: str = "COMPETITIVE") -> float:
        """
        Get dynamic outlier score threshold for go/no-go decision.
        
        Replaces hard-coded: top_score < 500 → KILL
        
        Args:
            niche: Content niche
            competition: SATURATED|COMPETITIVE|UNDERSERVED
            
        Returns:
            Threshold value (varies by niche and competition)
        """
        
        # If we have historical data for this niche, use it
        if niche in self.thresholds["by_niche"]:
            niche_threshold = self.thresholds["by_niche"][niche]["outlier_threshold"]
        else:
            niche_threshold = self.thresholds["global"]["outlier_threshold"]
        
        # Adjust by competition level
        competition_multiplier = {
            "UNDERSERVED": 0.6,   # Lower threshold in underserved (easier to win)
            "COMPETITIVE": 1.0,   # Normal threshold
            "SATURATED": 1.5,     # Higher threshold needed (harder to win)
        }
        
        multiplier = competition_multiplier.get(competition, 1.0)
        return niche_threshold * multiplier

    def get_gap_count_threshold(self, niche: str = "general") -> int:
        """
        Minimum number of high-gap keywords to proceed.
        
        Replaces hard-coded: high_gap_count <= 1 → KILL
        """
        if niche in self.thresholds["by_niche"]:
            return self.thresholds["by_niche"][niche]["min_gaps"]
        return self.thresholds["global"]["min_gaps"]

    def get_competition_saturation_threshold(self, niche: str = "general") -> int:
        """
        Video count that defines SATURATED market.
        
        Replaces hard-coded: len(youtube_results) > 50 → SATURATED
        """
        if niche in self.thresholds["by_niche"]:
            return self.thresholds["by_niche"][niche]["saturation_video_count"]
        return self.thresholds["global"]["saturation_video_count"]

    def get_small_channel_threshold(self, niche: str = "general") -> int:
        """
        Subscriber count that defines "small channel".
        
        Replaces hard-coded: subscribers <= 10000 → SMALL_CHANNEL
        """
        if niche in self.thresholds["by_niche"]:
            return self.thresholds["by_niche"][niche]["small_channel_subs"]
        return self.thresholds["global"]["small_channel_subs"]

    def get_opportunity_score_bands(self, niche: str = "general") -> dict[str, tuple[float, float]]:
        """
        Get scoring bands for opportunity classification.
        
        Replaces hard-coded: score >= 60 → STRONG, score >= 35 → WORKABLE
        """
        if niche in self.thresholds["by_niche"]:
            bands = self.thresholds["by_niche"][niche]["score_bands"]
        else:
            bands = self.thresholds["global"]["score_bands"]
        
        return bands

    def evaluate_idea_kill_switch(
        self,
        top_outlier_score: float,
        competition_label: str,
        small_channel_outliers: int,
        high_gap_count: int,
        niche: str = "general",
    ) -> dict[str, Any]:
        """
        Enhanced kill-switch logic using dynamic thresholds.
        
        This replaces the hard-coded logic in gap_engine.py
        """
        
        # Get dynamic thresholds
        outlier_threshold = self.get_outlier_score_threshold(niche, competition_label)
        gap_threshold = self.get_gap_count_threshold(niche)
        
        # Evaluation logic
        proceed = True
        reason = "Opportunity is strong enough to keep pursuing."
        confidence = "medium"
        recommended_action = "Proceed with a differentiated angle."
        
        # Rule 1: Weak outlier + saturated + no gaps = KILL
        if (top_outlier_score < outlier_threshold and 
            competition_label == "SATURATED" and 
            high_gap_count == 0):
            proceed = False
            reason = "Weak outlier signal plus saturated competition leaves no room."
            confidence = "high"
            recommended_action = "Kill this idea or re-scope into a narrower subtopic."
        
        # Rule 2: Weak outlier + competitive + no outlier channels = KILL
        elif (top_outlier_score < (outlier_threshold * 0.8) and 
              competition_label == "COMPETITIVE" and 
              small_channel_outliers == 0 and 
              high_gap_count <= gap_threshold):
            proceed = False
            reason = "Topic lacks breakout evidence for current competition level."
            confidence = "high"
            recommended_action = "Rework the topic before investing in production."
        
        # Rule 3: Strong gaps or outlier channels present = PROCEED despite challenges
        elif high_gap_count >= gap_threshold or small_channel_outliers >= 2:
            proceed = True
            reason = "Topic has breakout room if you lean into uncovered angles."
            confidence = "high"
            recommended_action = "Proceed, but lock into clearest underused promise."
        
        # Rule 4: Underserved with any signal = STRONG PROCEED
        elif competition_label == "UNDERSERVED":
            proceed = True
            reason = "Underserved market with reasonable opportunity."
            confidence = "very_high"
            recommended_action = "Proceed aggressively - this is a market opportunity."
        
        return {
            "proceed": proceed,
            "reason": reason,
            "confidence": confidence,
            "recommended_action": recommended_action,
            "thresholds_used": {
                "outlier_threshold": outlier_threshold,
                "gap_threshold": gap_threshold,
            },
        }

    def _calculate_thresholds(self) -> dict[str, Any]:
        """Calculate thresholds from historical data."""
        
        # Global defaults
        global_thresholds = {
            "outlier_threshold": 800,         # Instead of hard-coded 500 or 2000
            "min_gaps": 2,                    # Instead of hard-coded 2
            "saturation_video_count": 75,     # Instead of hard-coded 50
            "small_channel_subs": 12000,      # Instead of hard-coded 10000
            "score_bands": {
                "STRONG": (60, 100),
                "WORKABLE": (35, 60),
                "WEAK": (0, 35),
            },
        }
        
        if not self.historical_data:
            return {
                "global": global_thresholds,
                "by_niche": {},
            }
        
        # Calculate per-niche thresholds
        by_niche = {}
        for item in self.historical_data:
            niche = item.get("niche", "general")
            if niche not in by_niche:
                by_niche[niche] = {
                    "outlier_scores": [],
                    "video_counts": [],
                    "successful": [],
                }
            
            by_niche[niche]["outlier_scores"].append(item.get("outlier_score", 0))
            by_niche[niche]["video_counts"].append(item.get("competition_videos", 0))
            by_niche[niche]["successful"].append(item.get("success", False))
        
        # Compute niche-specific thresholds
        niche_thresholds = {}
        for niche, data in by_niche.items():
            if data["outlier_scores"]:
                # Threshold = 60th percentile of successful videos' outlier scores
                successful_outliers = [
                    score for score, success in zip(data["outlier_scores"], data["successful"])
                    if success
                ]
                if successful_outliers:
                    threshold = statistics.median(successful_outliers) * 0.85
                else:
                    threshold = statistics.mean(data["outlier_scores"])
            else:
                threshold = global_thresholds["outlier_threshold"]
            
            niche_thresholds[niche] = {
                "outlier_threshold": max(threshold, 100),  # Floor at 100
                "min_gaps": 1 if niche in {"tech", "gaming"} else 2,  # Tech/gaming need fewer gaps
                "saturation_video_count": int(statistics.mean(data["video_counts"]) * 1.5) if data["video_counts"] else 75,
                "small_channel_subs": 8000 if niche in {"gaming", "tech"} else 15000,  # Lower for creator niches
                "score_bands": {
                    "STRONG": (55, 100),
                    "WORKABLE": (30, 55),
                    "WEAK": (0, 30),
                },
            }
        
        return {
            "global": global_thresholds,
            "by_niche": niche_thresholds,
        }


# ============================================================================
# Integration with gap_engine.py
# ============================================================================

def get_dynamic_kill_switch(
    top_opportunities: list[dict[str, Any]],
    competition: dict[str, Any],
    keyword_gaps: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
    niche: str = "general",
    historical_data: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Enhanced kill-switch replacement using dynamic thresholds.
    
    Drop-in for _idea_kill_switch() function.
    """
    
    calculator = DynamicThresholdCalculator(historical_data)
    
    top_score = float(top_opportunities[0].get("outlier_score") or 0) if top_opportunities else 0.0
    competition_label = competition.get("label", "UNKNOWN")
    small_channel_outliers = sum(1 for item in top_opportunities if item.get("small_channel_outlier"))
    high_gap_count = sum(1 for item in keyword_gaps if item.get("gap_strength") == "high")
    
    return calculator.evaluate_idea_kill_switch(
        top_outlier_score=top_score,
        competition_label=competition_label,
        small_channel_outliers=small_channel_outliers,
        high_gap_count=high_gap_count,
        niche=niche,
    )
