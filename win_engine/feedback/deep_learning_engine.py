"""
Deep Learning Engine v2.0
Statistical correlation analysis for creator-specific patterns
Replaces simple averaging with actionable insights
"""

from __future__ import annotations
from typing import Any
import statistics
from collections import defaultdict


class DeepLearningEngine:
    """Extract creative patterns and correlations from performance history."""

    def __init__(self, historical_data: list[dict[str, Any]] | None = None):
        """
        Initialize with historical analysis runs.
        
        Expected fields:
        - title: str
        - title_score: float
        - opportunity_score: float
        - opportunity_label: str
        - ctr_prediction: float
        - actual_ctr: float (if available)
        - content_angle: str
        - title_structure: str (e.g., "for X days", "question format")
        - engagement_rate: float (if available)
        - retention_rate: float (if available)
        - comments_sentiment: str (positive|neutral|negative)
        """
        self.historical_data = historical_data or []

    def get_deep_insights(self) -> dict[str, Any]:
        """
        Get actionable creator-specific insights instead of just averages.
        
        Returns:
        - creator_strengths: What this creator does exceptionally well
        - creator_weaknesses: Where creator typically underperforms
        - content_correlations: Title structure → actual performance
        - angle_effectiveness: Which angles work best
        - growth_trajectory: Is creator improving over time?
        - style_signature: Unique patterns in this creator's content
        """
        
        if len(self.historical_data) < 5:
            return {
                "status": "insufficient_data",
                "message": "Need 5+ historical analyses for reliable patterns",
                "insights": {},
            }
        
        return {
            "creator_strengths": self._find_strengths(),
            "creator_weaknesses": self._find_weaknesses(),
            "content_correlations": self._analyze_correlations(),
            "angle_effectiveness": self._analyze_angle_performance(),
            "growth_trajectory": self._analyze_growth(),
            "style_signature": self._extract_style_signature(),
            "prediction_confidence": self._calculate_confidence(),
        }

    def predict_next_video_performance(
        self,
        proposed_title: str,
        proposed_angle: str,
        proposed_title_score: float,
    ) -> dict[str, Any]:
        """
        Predict performance using creator's personal patterns.
        
        Instead of generic 7% CTR, predict based on:
        "When creator uses angle=X with title_score=Y, they get Z CTR"
        """
        
        if len(self.historical_data) < 3:
            return {
                "confidence": "low",
                "estimated_ctr": 0.04,
                "reasoning": "Insufficient history for personalized prediction",
            }
        
        # Find similar videos in history
        similar_angle_videos = [
            v for v in self.historical_data
            if v.get("content_angle") == proposed_angle
        ]
        
        if similar_angle_videos:
            # Use creator's actual performance with this angle
            actual_ctrs = [v.get("actual_ctr", 0.04) for v in similar_angle_videos]
            avg_ctr_for_angle = statistics.mean(actual_ctrs)
            
            # Adjust based on title score improvement
            avg_title_score = statistics.mean(
                v.get("title_score", 5) for v in similar_angle_videos
            )
            score_improvement_ratio = proposed_title_score / max(avg_title_score, 1)
            
            # More title score improvement = marginal CTR increase (diminishing returns)
            ctr_adjustment = (score_improvement_ratio - 1) * 0.08  # Max 8% improvement
            predicted_ctr = avg_ctr_for_angle * (1 + ctr_adjustment)
            
            return {
                "estimated_ctr": round(min(predicted_ctr, 0.15), 4),
                "confidence": "high" if len(similar_angle_videos) >= 3 else "medium",
                "reasoning": f"Creator achieved {round(avg_ctr_for_angle * 100, 2)}% CTR with {proposed_angle} angle previously. Adjusting for title score improvement.",
                "historical_average_for_angle": round(avg_ctr_for_angle * 100, 2),
                "sample_size": len(similar_angle_videos),
            }
        
        # Fallback: Use overall historical average
        all_ctrs = [v.get("actual_ctr", 0.03) for v in self.historical_data]
        median_ctr = statistics.median(all_ctrs) if all_ctrs else 0.04
        
        return {
            "estimated_ctr": round(median_ctr, 4),
            "confidence": "low_no_angle_history",
            "reasoning": "No prior history with this angle. Using overall baseline.",
            "overall_baseline": round(median_ctr * 100, 2),
        }

    def _find_strengths(self) -> dict[str, Any]:
        """Identify what creator excels at."""
        if not self.historical_data:
            return {}
        
        scores = [v.get("title_score", 5) for v in self.historical_data]
        opportunities = [v.get("opportunity_score", 50) for v in self.historical_data]
        
        avg_title = statistics.mean(scores)
        avg_opp = statistics.mean(opportunities)
        
        # Find above-average performances
        strong_titles = [
            v.get("title", "Untitled")
            for v in self.historical_data
            if v.get("title_score", 0) > avg_title + 1
        ]
        
        strong_angles = defaultdict(int)
        for v in self.historical_data:
            if v.get("opportunity_score", 0) > avg_opp + 10:
                angle = v.get("content_angle", "unknown")
                strong_angles[angle] += 1
        
        return {
            "peak_title_score": round(max(scores, default=0), 2),
            "best_performing_angles": dict(sorted(strong_angles.items(), key=lambda x: x[1], reverse=True)[:3]),
            "best_opportunity_score": round(max(opportunities, default=0), 2),
            "consistency_strength": self._calculate_consistency(),
        }

    def _find_weaknesses(self) -> dict[str, Any]:
        """Identify patterns where creator underperforms."""
        if not self.historical_data:
            return {}
        
        scores = [v.get("title_score", 5) for v in self.historical_data]
        
        weak_titles = [
            v.get("title", "Untitled")
            for v in self.historical_data
            if v.get("title_score", 0) < (statistics.mean(scores) - 2) and statistics.mean(scores) > 0
        ]
        
        weak_angles = defaultdict(int)
        for v in self.historical_data:
            if v.get("opportunity_score", 0) < 30:
                angle = v.get("content_angle", "unknown")
                weak_angles[angle] += 1
        
        return {
            "lowest_title_score": round(min(scores, default=0), 2),
            "problematic_angles": dict(sorted(weak_angles.items(), key=lambda x: x[1], reverse=True)[:2]),
            "avg_opportunity_label_distribution": self._label_distribution(),
        }

    def _analyze_correlations(self) -> dict[str, Any]:
        """Find correlations: "When title includes X, performance is Y%"."""
        correlations = {}
        
        # Correlation 1: Title length vs performance
        lengths = [len(v.get("title", "")) for v in self.historical_data]
        scores = [v.get("title_score", 0) for v in self.historical_data]
        
        if lengths and scores:
            correlation_coefficient = self._pearson_correlation(lengths, scores)
            correlations["title_length_vs_score"] = {
                "correlation": round(correlation_coefficient, 3),
                "interpretation": "strong" if abs(correlation_coefficient) > 0.7 else "moderate" if abs(correlation_coefficient) > 0.4 else "weak",
            }
        
        # Correlation 2: Opportunity score vs title score
        opps = [v.get("opportunity_score", 0) for v in self.historical_data]
        if opps and scores:
            correlation_coefficient = self._pearson_correlation(opps, scores)
            correlations["opportunity_vs_title_score"] = {
                "correlation": round(correlation_coefficient, 3),
                "interpretation": "Creator's titles improve when opportunity is clear" if correlation_coefficient > 0.5 else "Title quality independent of opportunity",
            }
        
        return correlations

    def _analyze_angle_performance(self) -> dict[str, Any]:
        """Analyze which content angles work best for this creator."""
        angle_performance = defaultdict(lambda: {"scores": [], "ctrs": [], "count": 0})
        
        for video in self.historical_data:
            angle = video.get("content_angle", "unknown")
            angle_performance[angle]["scores"].append(video.get("title_score", 0))
            if "actual_ctr" in video:
                angle_performance[angle]["ctrs"].append(video.get("actual_ctr"))
            angle_performance[angle]["count"] += 1
        
        # Rank angles by average score and CTR
        ranked_angles = {}
        for angle, data in angle_performance.items():
            avg_score = statistics.mean(data["scores"]) if data["scores"] else 0
            avg_ctr = statistics.mean(data["ctrs"]) if data["ctrs"] else 0
            ranked_angles[angle] = {
                "avg_title_score": round(avg_score, 2),
                "avg_ctr": round(avg_ctr * 100, 2) if avg_ctr else "N/A",
                "videos_with_angle": data["count"],
                "recommendation": "strong" if avg_score > 7 else "moderate" if avg_score > 5 else "weak",
            }
        
        return ranked_angles

    def _analyze_growth(self) -> dict[str, Any]:
        """Detect if creator's performance is improving over time."""
        if len(self.historical_data) < 5:
            return {"status": "insufficient_data", "trend": "unknown"}
        
        # Sort by timestamp
        sorted_data = sorted(
            self.historical_data,
            key=lambda x: x.get("created_at", ""),
            reverse=False
        )
        
        # Calculate trend (first half vs second half)
        mid = len(sorted_data) // 2
        first_half_scores = [v.get("title_score", 0) for v in sorted_data[:mid]]
        second_half_scores = [v.get("title_score", 0) for v in sorted_data[mid:]]
        
        first_avg = statistics.mean(first_half_scores) if first_half_scores else 0
        second_avg = statistics.mean(second_half_scores) if second_half_scores else 0
        improvement_percent = ((second_avg - first_avg) / max(first_avg, 1)) * 100
        
        return {
            "first_half_avg": round(first_avg, 2),
            "second_half_avg": round(second_avg, 2),
            "improvement_percent": round(improvement_percent, 2),
            "trend": "improving" if improvement_percent > 5 else "declining" if improvement_percent < -5 else "stable",
            "trajectory_insight": f"Creator's titles are {'improving' if improvement_percent > 0 else 'declining'} by {abs(round(improvement_percent, 1))}%",
        }

    def _extract_style_signature(self) -> dict[str, Any]:
        """Discover creator's unique style patterns."""
        titles = [v.get("title", "") for v in self.historical_data]
        
        # Common phrases
        phrase_freq = defaultdict(int)
        for title in titles:
            if "?" in title:
                phrase_freq["uses_questions"] += 1
            if "for" in title.lower() and any(c.isdigit() for c in title):
                phrase_freq["duration_format"] += 1
            if any(word in title.lower() for word in {"i", "my", "me"}):
                phrase_freq["first_person"] += 1
            if any(word in title.lower() for word in {"honest", "truth", "real"}):
                phrase_freq["authenticity_markers"] += 1
        
        # Identify dominant style
        dominant_style = max(phrase_freq, key=phrase_freq.get) if phrase_freq else "standard"
        
        return {
            "dominant_style": dominant_style,
            "style_markers": dict(phrase_freq),
            "average_title_length": round(statistics.mean(len(t) for t in titles), 1),
            "recommendation": f"Creator's signature style: {dominant_style}. Leverage this in future titles.",
        }

    def _calculate_consistency(self) -> str:
        """Measure how consistent creator's quality is."""
        scores = [v.get("title_score", 0) for v in self.historical_data]
        if not scores:
            return "unknown"
        
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
        if std_dev < 1:
            return "very_consistent"
        elif std_dev < 2:
            return "consistent"
        else:
            return "variable"

    def _label_distribution(self) -> dict[str, int]:
        """Distribution of opportunity labels."""
        labels = defaultdict(int)
        for v in self.historical_data:
            label = v.get("opportunity_label", "UNKNOWN")
            labels[label] += 1
        return dict(labels)

    def _calculate_confidence(self) -> str:
        """Overall confidence in our learning model."""
        data_points = len(self.historical_data)
        if data_points < 5:
            return "low"
        elif data_points < 15:
            return "moderate"
        elif data_points < 30:
            return "high"
        else:
            return "very_high"

    def _pearson_correlation(self, x: list[float], y: list[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)
        
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
        denominator = (
            (sum((xi - mean_x) ** 2 for xi in x) ** 0.5) *
            (sum((yi - mean_y) ** 2 for yi in y) ** 0.5)
        )
        
        if denominator == 0:
            return 0.0
        return numerator / denominator
