"""
Phase 13.1: Post-Upload Optimization Engine
Real-time performance monitoring and emergency optimization recommendations
Monitors first 24h performance for underperforming videos
"""

from __future__ import annotations

from typing import Any
import statistics


class PostUploadOptimizer:
    """Real-time monitoring and optimization for first 24h performance."""

    def __init__(self, video_history: list[dict[str, Any]] | None = None):
        """
        Initialize with optional video history for baseline comparison.
        
        Video history should contain:
        - video_id: str
        - title: str
        - views_24h: int
        - ctr_24h: float (0-1)
        - likes: int
        - comments: int
        - average_watch_duration: float
        - expected_ctr: float (prediction from Brain v2.0)
        """
        self.video_history = video_history or []
        self.baseline_metrics = self._calculate_baseline_metrics()

    def monitor_24h_performance(
        self,
        video_id: str,
        title: str,
        views_24h: int,
        clicks_24h: int,
        likes: int,
        comments: int,
        avg_watch_duration: float,
        expected_ctr_percent: float,
        content_angle: str = "general",
    ) -> dict[str, Any]:
        """
        Analyze 24h performance and provide emergency recommendations.
        
        Returns optimization recommendations if video is underperforming.
        """
        
        actual_ctr = (clicks_24h / max(views_24h, 1)) * 100 if views_24h > 0 else 0
        expected_ctr = expected_ctr_percent
        
        # Calculate performance delta
        ctr_delta = actual_ctr - expected_ctr
        engagement_score = self._calculate_engagement_score(likes, comments, views_24h, avg_watch_duration)
        retention_health = self._estimate_retention_health(avg_watch_duration)
        
        # Determine alert level
        alert_level = self._determine_alert_level(ctr_delta, engagement_score, views_24h)
        
        # Generate recommendations
        recommendations = []
        if alert_level in {"CRITICAL", "WARNING"}:
            recommendations = self._generate_emergency_recommendations(
                ctr_delta=ctr_delta,
                engagement_score=engagement_score,
                retention_health=retention_health,
                title=title,
                content_angle=content_angle,
                actual_ctr=actual_ctr,
            )
        
        return {
            "video_id": video_id,
            "monitoring_status": {
                "alert_level": alert_level,
                "views_24h": views_24h,
                "actual_ctr_percent": round(actual_ctr, 2),
                "expected_ctr_percent": round(expected_ctr, 2),
                "ctr_delta_percent": round(ctr_delta, 2),
            },
            "engagement_health": {
                "likes": likes,
                "comments": comments,
                "engagement_score": round(engagement_score, 2),
                "status": "healthy" if engagement_score > 0.03 else "needs_boost",
            },
            "retention_health": {
                "average_watch_duration": round(avg_watch_duration, 2),
                "status": retention_health,
                "interpretation": self._retention_interpretation(retention_health, content_angle),
            },
            "emergency_recommendations": recommendations,
            "next_check_hours": 6 if alert_level in {"CRITICAL", "WARNING"} else 12,
        }

    def _calculate_engagement_score(self, likes: int, comments: int, views: int, avg_duration: float) -> float:
        """Calculate overall engagement score (0-1 scale)."""
        if views == 0:
            return 0.0
        
        like_rate = likes / max(views, 1)
        comment_rate = comments / max(views, 1)
        
        # Weighted engagement: comments more valuable than likes
        engagement = (like_rate * 0.3) + (comment_rate * 0.7)
        
        # Duration boost: longer watch = better engagement
        duration_bonus = min(avg_duration / 300, 1) * 0.2  # 5min+ gets full bonus
        
        return min(engagement + duration_bonus, 1.0)

    def _estimate_retention_health(self, avg_watch_duration: float) -> str:
        """Estimate video retention health from average watch duration."""
        if avg_watch_duration > 240:  # >4min
            return "excellent"
        elif avg_watch_duration > 120:  # >2min
            return "good"
        elif avg_watch_duration > 60:  # >1min
            return "moderate"
        elif avg_watch_duration > 30:  # >30sec
            return "needs_improvement"
        else:
            return "critical_drop"

    def _determine_alert_level(self, ctr_delta: float, engagement_score: float, views: int) -> str:
        """Determine if video needs emergency intervention."""
        
        # CRITICAL: Views too low even with good content + CTR significantly underperforming
        if views < 100 and ctr_delta < -3 and engagement_score < 0.01:
            return "CRITICAL"
        
        # WARNING: Underperforming vs expectations
        if ctr_delta < -2 and engagement_score < 0.02:
            return "WARNING"
        
        # MONITOR: Slight underperformance, track it
        if ctr_delta < -1 and views > 50:
            return "MONITOR"
        
        # HEALTHY: Meeting or exceeding expectations
        return "HEALTHY"

    def _generate_emergency_recommendations(
        self,
        ctr_delta: float,
        engagement_score: float,
        retention_health: str,
        title: str,
        content_angle: str,
        actual_ctr: float,
    ) -> list[dict[str, Any]]:
        """Generate actionable recommendations for underperforming videos."""
        
        recommendations = []
        
        # Recommendation 1: Social Media Push
        if actual_ctr < 3.0 and engagement_score < 0.01:
            recommendations.append({
                "priority": 1,
                "action": "Social Media Push",
                "description": "Video CTR is significantly below baseline. Push to social media channels within 2 hours.",
                "tactics": [
                    "Post on YouTube Community tab with hook",
                    "Share on Twitter/X with 3-5 variations",
                    "Post on relevant subreddits (3-4 top communities)",
                    "Share in Discord communities (5+ active groups)",
                ],
                "expected_impact": "+15-30% views in next 3 hours",
            })
        
        # Recommendation 2: Comment Pinning Strategy
        if engagement_score < 0.02 and retention_health not in {"excellent", "good"}:
            recommendations.append({
                "priority": 2,
                "action": "Pin Community Comments",
                "description": "Seed engagement with strategic comment pinning to boost visibility.",
                "tactics": [
                    "Find top 3 comments with questions or strong engagement",
                    "Pin 1 comment asking viewers to comment their biggest takeaway",
                    "Reply to comments within 1 hour (boosts algorithm visibility)",
                ],
                "expected_impact": "+20-40% comments, improved YouTube algorithm signals",
            })
        
        # Recommendation 3: Title/Thumbnail Review
        if ctr_delta < -2.5:
            recommendations.append({
                "priority": 3,
                "action": "Title/Thumbnail Analysis",
                "description": "CTR significantly underperforming. Review if title/thumbnail matches content promise.",
                "tactics": [
                    f"Review if '{title}' accurately reflects video content",
                    "Check if thumbnail visual is clear in YouTube's small preview",
                    "Consider A/B testing thumbnail change if possible",
                ],
                "expected_impact": "+10-25% CTR improvement",
            })
        
        # Recommendation 4: Retention Drop Investigation
        if retention_health in {"critical_drop", "needs_improvement"}:
            recommendations.append({
                "priority": 2,
                "action": "Retention Analysis & Fix",
                "description": "Viewers are dropping off early. Identify and fix retention issues.",
                "tactics": [
                    "Check YouTube Analytics for drop-off point (likely in first 30sec)",
                    "Ensure hook content matches thumbnail promise",
                    "Re-edit intro if first 15 seconds feel slow",
                    "Add pattern breaks every 60 seconds (cut, sound effect, visual change)",
                ],
                "expected_impact": "+30-50% average watch duration",
            })
        
        # Recommendation 5: Playlist & Series Leverage
        if actual_ctr < 2.0 and engagement_score < 0.01:
            recommendations.append({
                "priority": 4,
                "action": "Playlist Strategy",
                "description": "Leverage existing playlists to boost views.",
                "tactics": [
                    "Add to 2-3 most relevant playlists",
                    "Create series playlist with this as new episode",
                    "Set as series in channel (if applicable)",
                ],
                "expected_impact": "+5-15% additional views from playlist discovery",
            })
        
        return recommendations

    def _retention_interpretation(self, retention_health: str, content_angle: str) -> str:
        """Interpret retention health in context of content type."""
        
        interpretations = {
            "excellent": "Viewers are deeply engaged. Strong hook and pacing working.",
            "good": "Audience retention is healthy. Content is holding viewer interest.",
            "moderate": "Retention is acceptable but could be improved with better pacing or more pattern breaks.",
            "needs_improvement": "Viewers are dropping off. Consider re-editing intro or improving hook.",
            "critical_drop": "URGENT: Most viewers are leaving in first 30 seconds. Thumbnail/title mismatch likely.",
        }
        
        return interpretations.get(retention_health, "Unknown retention status")

    def _calculate_baseline_metrics(self) -> dict[str, float]:
        """Calculate baseline metrics from historical video data."""
        
        if not self.video_history:
            return {
                "avg_ctr_24h": 0.05,
                "avg_engagement_rate": 0.02,
                "avg_retention": 120,  # 2 minutes
            }
        
        ctrs = []
        engagement_rates = []
        retentions = []
        
        for video in self.video_history:
            if video.get("views_24h") and video.get("clicks_24h"):
                ctr = (video["clicks_24h"] / video["views_24h"]) * 100
                ctrs.append(ctr)
            
            if video.get("views_24h"):
                eng_rate = (video.get("likes", 0) + video.get("comments", 0)) / video["views_24h"]
                engagement_rates.append(eng_rate)
            
            if video.get("average_watch_duration"):
                retentions.append(video["average_watch_duration"])
        
        return {
            "avg_ctr_24h": statistics.mean(ctrs) if ctrs else 0.05,
            "avg_engagement_rate": statistics.mean(engagement_rates) if engagement_rates else 0.02,
            "avg_retention": statistics.mean(retentions) if retentions else 120,
        }


def get_post_upload_recommendations(
    video_id: str,
    title: str,
    views_24h: int,
    clicks_24h: int,
    likes: int,
    comments: int,
    avg_watch_duration: float,
    expected_ctr_percent: float,
    content_angle: str = "general",
) -> dict[str, Any]:
    """
    Standalone function for post-upload optimization recommendations.
    Can be called directly or via PostUploadOptimizer class.
    """
    
    optimizer = PostUploadOptimizer()
    return optimizer.monitor_24h_performance(
        video_id=video_id,
        title=title,
        views_24h=views_24h,
        clicks_24h=clicks_24h,
        likes=likes,
        comments=comments,
        avg_watch_duration=avg_watch_duration,
        expected_ctr_percent=expected_ctr_percent,
        content_angle=content_angle,
    )
