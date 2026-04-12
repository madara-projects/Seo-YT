"""
Phase 11: Analytics Dashboard & Control Panel
Comprehensive insights and creator performance analytics.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

class AnalyticsDashboard:
    """Creator analytics and performance insights dashboard."""

    def __init__(self, history_store: Any) -> None:
        self.history_store = history_store

    def get_channel_overview(self) -> dict[str, Any]:
        """Get comprehensive channel performance overview."""

        connection = self.history_store._connect()

        # Overall statistics
        overall = connection.execute(
            """
            SELECT
                COUNT(DISTINCT video_id) as total_videos,
                SUM(view_count) as total_views,
                SUM(like_count) as total_likes,
                SUM(comment_count) as total_comments,
                AVG(click_through_rate) as avg_ctr,
                AVG(average_view_duration_percent) as avg_retention
            FROM performance_metrics
            """
        ).fetchone()

        if not overall or not overall[0]:
            return {
                "status": "INSUFFICIENT_DATA",
                "message": "Channel has no video performance data yet",
            }

        total_videos, total_views, total_likes, total_comments, avg_ctr, avg_retention = overall

        return {
            "total_videos": int(total_videos or 0),
            "total_views": int(total_views or 0),
            "total_likes": int(total_likes or 0),
            "total_comments": int(total_comments or 0),
            "average_ctr": round(float(avg_ctr or 0), 4),
            "average_retention_percent": round(float(avg_retention or 0), 2),
            "avg_views_per_video": int((total_views or 0) / max(total_videos or 1, 1)),
            "engagement_rate": round(
                ((total_likes or 0) + (total_comments or 0)) / max(total_views or 1, 1), 4
            ),
        }

    def get_performance_trends(self, days: int = 30) -> dict[str, Any]:
        """Get historical performance trends."""

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        connection = self.history_store._connect()

        daily_trends = connection.execute(
            """
            SELECT
                DATE(recorded_at) as date,
                COUNT(*) as videos_tracked,
                AVG(view_count) as avg_daily_views,
                AVG(click_through_rate) as avg_daily_ctr,
                SUM(like_count) as daily_likes
            FROM performance_metrics
            WHERE recorded_at > ?
            GROUP BY DATE(recorded_at)
            ORDER BY date DESC
            """,
            (cutoff,),
        ).fetchall()

        trend_data = [
            {
                "date": row[0],
                "videos_tracked": row[1],
                "avg_views": int(row[2] or 0),
                "avg_ctr": round(float(row[3] or 0), 4),
                "total_likes": int(row[4] or 0),
            }
            for row in daily_trends
        ]

        return {
            "period_days": days,
            "data_points": len(trend_data),
            "trends": trend_data,
        }

    def get_top_performing_videos(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get top performing videos by view count."""

        connection = self.history_store._connect()

        top_videos = connection.execute(
            """
            SELECT
                u.video_id,
                u.title,
                p.view_count,
                p.like_count,
                p.comment_count,
                p.click_through_rate,
                p.average_view_duration_percent,
                u.published_at
            FROM performance_metrics p
            JOIN video_uploads u ON p.video_id = u.video_id
            ORDER BY p.view_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            {
                "video_id": row[0],
                "title": row[1],
                "views": int(row[2] or 0),
                "likes": int(row[3] or 0),
                "comments": int(row[4] or 0),
                "ctr": round(float(row[5] or 0), 4),
                "retention": round(float(row[6] or 0), 2),
                "published": row[7],
            }
            for row in top_videos
        ]

    def get_custom_strategy_builder(self) -> dict[str, Any]:
        """Build custom strategy based on creator's historical data."""

        # Get analysis patterns
        learning_data = self.history_store.learning_summary()
        baseline = self.history_store.creator_baseline()

        # Get winning patterns
        formulas = self.history_store.success_formula_recognition()

        strategy_components = {
            "best_content_angles": [f["angle"] for f in formulas.get("strongest_angles", [])],
            "baseline_metrics": {
                "avg_title_score": baseline.get("baseline_title_score", 0),
                "avg_opportunity_score": baseline.get("baseline_opportunity_score", 0),
            },
            "improvement_areas": _identify_improvement_areas(baseline, learning_data),
            "recommended_actions": _generate_strategy_actions(formulas, baseline),
        }

        return {
            "strategy_id": f"strategy_{datetime.now(timezone.utc).timestamp()}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "components": strategy_components,
        }

    def get_creator_insights_report(self) -> dict[str, Any]:
        """Generate comprehensive creator insights and recommendations."""

        channel_overview = self.get_channel_overview()
        top_videos = self.get_top_performing_videos(5)
        trends = self.get_performance_trends(30)
        strategy = self.get_custom_strategy_builder()

        insights = []

        if channel_overview.get("total_videos", 0) < 5:
            insights.append(
                {
                    "type": "INFO",
                    "title": "Build Sample Size",
                    "message": "Upload 5+ videos to generate confident patterns",
                }
            )
        else:
            avg_views = channel_overview.get("avg_views_per_video", 0)
            if avg_views < 1000:
                insights.append(
                    {
                        "type": "WARNING",
                        "title": "Views Below Target",
                        "message": f"Average views per video ({avg_views}) are low. Focus on title CTR and thumbnail optimization.",
                    }
                )
            elif avg_views > 10000:
                insights.append(
                    {
                        "type": "SUCCESS",
                        "title": "Strong Performance",
                        "message": f"Average views per video ({avg_views}) show strong audience engagement!",
                    }
                )

        engagement = channel_overview.get("engagement_rate", 0)
        if engagement > 0.05:
            insights.append(
                {
                    "type": "SUCCESS",
                    "title": "High Engagement",
                    "message": f"Your engagement rate ({engagement:.2%}) is excellent!",
                }
            )
        elif engagement < 0.01:
            insights.append(
                {
                    "type": "WARNING",
                    "title": "Engagement Opportunity",
                    "message": "Low engagement. Consider calls-to-action and community interaction.",
                }
            )

        return {
            "report_id": f"report_{datetime.now(timezone.utc).timestamp()}",
            "channel_overview": channel_overview,
            "top_videos": top_videos,
            "recent_trends": trends,
            "custom_strategy": strategy,
            "insights": insights,
        }


class HistoricalVisualization:
    """Historical trend visualization and analysis."""

    def __init__(self, history_store: Any) -> None:
        self.history_store = history_store

    def get_growth_chart_data(self, days: int = 90) -> dict[str, Any]:
        """Get data for growth chart visualization."""

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        connection = self.history_store._connect()

        try:
            daily_data = connection.execute(
                """
                SELECT
                    DATE(recorded_at) as date,
                    SUM(view_count) as total_views,
                    SUM(like_count) as total_likes,
                    COUNT(DISTINCT video_id) as videos_uploaded
                FROM performance_metrics
                WHERE recorded_at > ?
                GROUP BY DATE(recorded_at)
                ORDER BY date
                """,
                (cutoff,),
            ).fetchall()
        except sqlite3.OperationalError:
            daily_data = []

        cumulative_views = 0
        chart_data = []

        for row in daily_data:
            cumulative_views += row[1] or 0
            chart_data.append(
                {
                    "date": row[0],
                    "daily_views": int(row[1] or 0),
                    "cumulative_views": cumulative_views,
                    "daily_likes": int(row[2] or 0),
                    "videos_uploaded": row[3],
                }
            )

        return {
            "period_days": days,
            "chart_data": chart_data,
            "growth_trajectory": "ACCELERATING" if _is_accelerating(chart_data) else "STEADY",
        }

    def get_audience_retention_chart(self) -> dict[str, Any]:
        """Get audience retention data for visualization."""

        connection = self.history_store._connect()

        retention_data = connection.execute(
            """
            SELECT
                ROUND(average_view_duration_percent, 0) as retention_bin,
                COUNT(*) as video_count,
                AVG(view_count) as avg_views
            FROM performance_metrics
            GROUP BY ROUND(average_view_duration_percent, 0)
            ORDER BY retention_bin DESC
            """
        ).fetchall()

        return {
            "retention_distribution": [
                {
                    "retention_percent": int(row[0] or 0),
                    "video_count": row[1],
                    "average_views": int(row[2] or 0),
                }
                for row in retention_data
            ],
            "avg_retention_overall": (
                sum((row[0] or 0) * row[1] for row in retention_data) / sum(row[1] for row in retention_data)
                if retention_data
                else 0
            ),
        }


def _identify_improvement_areas(baseline: dict[str, Any], learning_data: dict[str, Any]) -> list[str]:
    """Identify areas for improvement based on baseline metrics."""

    areas = []

    if baseline.get("baseline_title_score", 0) < 7.0:
        areas.append("Title optimization - scores below optimal range")

    if baseline.get("baseline_opportunity_score", 0) < 60:
        areas.append("Content selection - targeting lower-opportunity topics")

    retention_patterns = learning_data.get("retention_pattern", [])
    if any(r.get("retention_risk") == "HIGH" for r in retention_patterns):
        areas.append("Content pacing - high retention risk detected")

    return areas or ["Continue current strategy - performing well"]


def _generate_strategy_actions(formulas: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Generate actionable strategy recommendations."""

    actions = []

    top_angles = formulas.get("strongest_angles", [])
    if top_angles:
        actions.append(f"Focus on '{top_angles[0]['angle']}' - your strongest performing angle")

    if baseline.get("baseline_title_score", 0) < 8.0:
        actions.append("Improve title composition - target 8.0+ scores")

    actions.append("Upload 2-3x per week to build momentum")
    actions.append("Monitor A/B test results and implement winners")

    return actions


def _is_accelerating(chart_data: list[dict[str, Any]]) -> bool:
    """Determine if growth is accelerating."""

    if len(chart_data) < 3:
        return False

    recent_growth = chart_data[-1].get("cumulative_views", 0) - chart_data[-2].get("cumulative_views", 0)
    previous_growth = chart_data[-2].get("cumulative_views", 0) - chart_data[-3].get("cumulative_views", 0)

    return recent_growth > previous_growth * 1.1
