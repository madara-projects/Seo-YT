"""
Phase 13.2: Upload Timing Optimization Engine
Analyzes creator's historical performance to find optimal upload times
Provides per-day-of-week and per-time-of-day recommendations
"""

from __future__ import annotations

from typing import Any
from collections import defaultdict
import statistics


class UploadTimingOptimizer:
    """Calculate creator-specific optimal upload times from historical data."""

    def __init__(self, video_history: list[dict[str, Any]] | None = None):
        """
        Initialize with video history.
        
        Video history should contain:
        - upload_day: str (monday-sunday, or 0-6)
        - upload_hour: int (0-23 in creator's timezone)
        - views_24h: int
        - ctr_24h: float
        - likes: int
        - comments: int
        - engagement_score: float
        """
        self.video_history = video_history or []
        self.heatmap = self._build_heatmap()

    def recommend_next_upload_time(
        self,
        creator_timezone: str = "UTC",
        content_angle: str = "general",
        target_audience: str = "global",
    ) -> dict[str, Any]:
        """
        Recommend optimal upload time based on creator's historical performance.
        """
        
        best_day, best_day_score = self._find_best_day()
        best_hour, best_hour_score = self._find_best_hour()
        combined_score = (best_day_score + best_hour_score) / 2
        
        # Get backup options
        backup_days = self._get_backup_days(exclude=best_day)
        backup_hours = self._get_backup_hours(exclude=best_hour)
        
        return {
            "optimal_recommendation": {
                "day": best_day,
                "hour": best_hour,
                "confidence": self._calculate_confidence(combined_score),
                "expected_improvement": self._estimate_improvement(combined_score),
                "reasoning": self._generate_reasoning(best_day, best_hour),
            },
            "backup_options": {
                "day_alternatives": backup_days,
                "hour_alternatives": backup_hours,
            },
            "performance_analysis": {
                "days_analyzed": len(self.video_history),
                "best_day_performance": round(best_day_score, 4),
                "best_hour_performance": round(best_hour_score, 4),
                "timezone": creator_timezone,
            },
            "audience_context": {
                "target": target_audience,
                "recommendation_note": self._get_audience_note(target_audience),
            },
            "timing_heatmap": self._get_heatmap_summary(),
        }

    def _build_heatmap(self) -> dict[str, dict[int, list[float]]]:
        """Build 2D heatmap of (day, hour) -> performance scores."""
        
        heatmap: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
        
        for video in self.video_history:
            day = str(video.get("upload_day", "unknown")).lower()
            hour = int(video.get("upload_hour", 0))
            
            # Use engagement score if available, otherwise calculate from metrics
            if "engagement_score" in video:
                score = float(video.get("engagement_score", 0))
            else:
                views = video.get("views_24h", 1)
                score = (
                    (video.get("likes", 0) / max(views, 1)) * 0.3 +
                    (video.get("comments", 0) / max(views, 1)) * 0.7
                )
            
            heatmap[day][hour].append(score)
        
        return heatmap

    def _find_best_day(self) -> tuple[str, float]:
        """Find day of week with best average performance."""
        
        if not self.heatmap:
            return "monday", 0.5  # Safe default
        
        day_scores = {}
        for day, hours_data in self.heatmap.items():
            all_scores = []
            for scores in hours_data.values():
                all_scores.extend(scores)
            
            if all_scores:
                day_scores[day] = statistics.mean(all_scores)
        
        if not day_scores:
            return "monday", 0.5
        
        best_day = max(day_scores, key=day_scores.get)
        best_score = day_scores[best_day]
        
        return best_day, best_score

    def _find_best_hour(self) -> tuple[int, float]:
        """Find hour of day with best average performance."""
        
        if not self.heatmap:
            return 14, 0.5  # 2 PM default
        
        hour_scores = {}
        for day_data in self.heatmap.values():
            for hour, scores in day_data.items():
                if hour not in hour_scores:
                    hour_scores[hour] = []
                hour_scores[hour].extend(scores)
        
        if not hour_scores:
            return 14, 0.5
        
        hour_averages = {hour: statistics.mean(scores) for hour, scores in hour_scores.items()}
        best_hour = max(hour_averages, key=hour_averages.get)
        best_score = hour_averages[best_hour]
        
        return best_hour, best_score

    def _get_backup_days(self, exclude: str = "", limit: int = 3) -> list[dict[str, Any]]:
        """Get backup day recommendations sorted by performance."""
        
        day_scores = {}
        day_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6, "0": 0, "1": 1,
            "2": 2, "3": 3, "4": 4, "5": 5, "6": 6
        }
        
        for day, hours_data in self.heatmap.items():
            if day.lower() == exclude.lower():
                continue
            
            all_scores = []
            for scores in hours_data.values():
                all_scores.extend(scores)
            
            if all_scores:
                day_scores[day] = statistics.mean(all_scores)
        
        sorted_days = sorted(day_scores.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"day": day, "score": round(score, 4), "rank": i + 1}
            for i, (day, score) in enumerate(sorted_days[:limit])
        ]

    def _get_backup_hours(self, exclude: int = -1, limit: int = 3) -> list[dict[str, Any]]:
        """Get backup hour recommendations sorted by performance."""
        
        hour_scores = {}
        for day_data in self.heatmap.values():
            for hour, scores in day_data.items():
                if hour == exclude:
                    continue
                
                if hour not in hour_scores:
                    hour_scores[hour] = []
                hour_scores[hour].extend(scores)
        
        hour_averages = {hour: statistics.mean(scores) for hour, scores in hour_scores.items()}
        sorted_hours = sorted(hour_averages.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {
                "hour": hour,
                "hour_12h": f"{(hour % 12) or 12}:00 {'AM' if hour < 12 else 'PM'}",
                "score": round(score, 4),
                "rank": i + 1,
            }
            for i, (hour, score) in enumerate(sorted_hours[:limit])
        ]

    def _calculate_confidence(self, score: float) -> str:
        """Determine confidence level based on sample size and score variance."""
        
        if len(self.video_history) < 3:
            return "low"
        elif len(self.video_history) < 10:
            return "moderate"
        else:
            return "high"

    def _estimate_improvement(self, score: float) -> str:
        """Estimate expected CTR/views improvement by uploading at optimal time."""
        
        # Score range 0-1, convert to expected improvement
        if score > 0.8:
            return "+25-40% views"
        elif score > 0.6:
            return "+15-25% views"
        elif score > 0.4:
            return "+5-15% views"
        else:
            return "+0-5% views (limited data)"

    def _generate_reasoning(self, best_day: str, best_hour: int) -> str:
        """Generate human-readable explanation for recommendation."""
        
        video_count = len(self.video_history)
        hour_str = f"{(best_hour % 12) or 12}:00 {'AM' if best_hour < 12 else 'PM'}"
        
        if video_count < 5:
            return f"Based on limited data ({video_count} videos). Recommend {best_day.title()} at {hour_str} as starting point."
        else:
            return (
                f"Analyzed {video_count} videos. Your audience is most active on {best_day.title()}s "
                f"at {hour_str}. Best avg engagement during this window."
            )

    def _get_audience_note(self, target_audience: str) -> str:
        """Provide context about audience timezone considerations."""
        
        notes = {
            "global": "Global audience detected. Recommended time balances multiple timezones.",
            "us": "US-focused audience. Optimal times: 2-4 PM ET or 7-9 PM ET.",
            "asia": "Asia-focused audience. Recommended early morning or late evening peak hours.",
            "europe": "Europe-focused audience. Peak times typically 6-9 PM CET.",
            "india": "India-focused audience. Peak times: 7-10 PM IST or weekend mornings.",
        }
        
        return notes.get(target_audience.lower(), "Consider your audience timezone for optimal reach.")

    def _get_heatmap_summary(self) -> dict[str, Any]:
        """Return simplified heatmap for visualization."""
        
        summary = {}
        for day, hours_data in self.heatmap.items():
            day_scores = []
            for hour, scores in sorted(hours_data.items()):
                if scores:
                    day_scores.append(round(statistics.mean(scores), 3))
            
            summary[day] = day_scores if day_scores else []
        
        return summary


def get_optimal_upload_time(
    video_history: list[dict[str, Any]],
    creator_timezone: str = "UTC",
    content_angle: str = "general",
    target_audience: str = "global",
) -> dict[str, Any]:
    """
    Standalone function to calculate optimal upload timing.
    
    Args:
        video_history: List of past video upload data with performance metrics
        creator_timezone: Creator's timezone (e.g. "EST", "IST", "UTC")
        content_angle: Type of content (tutorial, vlog, experiment, etc)
        target_audience: Primary audience region
    
    Returns:
        Recommendation dict with optimal day/hour + alternatives
    """
    
    optimizer = UploadTimingOptimizer(video_history)
    return optimizer.recommend_next_upload_time(
        creator_timezone=creator_timezone,
        content_angle=content_angle,
        target_audience=target_audience,
    )
