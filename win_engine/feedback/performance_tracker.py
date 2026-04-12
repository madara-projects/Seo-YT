"""
Phase 9: Real-Time Performance Tracker
Tracks actual YouTube video performance and feeds insights back into recommendations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class PerformanceTracker:
    """Track video performance and derive actionable feedback."""

    def __init__(self, history_store: Any) -> None:
        self.history_store = history_store

    def record_upload(
        self,
        title: str,
        description: str,
        tags: list[str],
        hashtags: list[str],
        video_id: str,
        published_at: str,
    ) -> None:
        """Record a video upload with its metadata."""
        self.history_store._connect().execute(
            """
            INSERT INTO video_uploads (
                video_id, title, description, tags, hashtags, published_at, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                title,
                description,
                ",".join(tags),
                ",".join(hashtags),
                published_at,
                datetime.now(timezone.utc).isoformat(),
            ),
        ).connection.commit()

    def track_performance_metrics(
        self,
        video_id: str,
        view_count: int,
        like_count: int,
        comment_count: int,
        watch_time_hours: float,
        click_through_rate: float,
        average_view_duration_percent: float,
    ) -> None:
        """Track real performance metrics for a video."""
        connection = self.history_store._connect()
        connection.execute(
            """
            INSERT INTO performance_metrics (
                video_id, view_count, like_count, comment_count, watch_time_hours,
                click_through_rate, average_view_duration_percent, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                view_count,
                like_count,
                comment_count,
                watch_time_hours,
                click_through_rate,
                average_view_duration_percent,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()

    def ab_test_title_variants(
        self,
        video_id: str,
        variant_a: str,
        variant_b: str,
        duration_hours: int = 48,
    ) -> dict[str, Any]:
        """Setup A/B test for title variants."""
        connection = self.history_store._connect()
        test_start = datetime.now(timezone.utc)
        test_end = test_start + timedelta(hours=duration_hours)

        connection.execute(
            """
            INSERT INTO ab_tests (
                video_id, variant_a, variant_b, test_start, test_end, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                variant_a,
                variant_b,
                test_start.isoformat(),
                test_end.isoformat(),
                "RUNNING",
            ),
        )
        connection.commit()

        return {
            "test_id": video_id,
            "variant_a": variant_a,
            "variant_b": variant_b,
            "duration_hours": duration_hours,
            "status": "RUNNING",
        }

    def get_ab_test_results(self, video_id: str) -> dict[str, Any]:
        """Get results of completed A/B tests."""
        connection = self.history_store._connect()
        test_row = connection.execute(
            """
            SELECT variant_a, variant_b, variant_a_views, variant_b_views,
                   variant_a_ctr, variant_b_ctr, test_start, test_end, status
            FROM ab_tests WHERE video_id = ? ORDER BY test_start DESC LIMIT 1
            """,
            (video_id,),
        ).fetchone()

        if not test_row:
            return {"status": "NO_TEST_FOUND"}

        (
            variant_a,
            variant_b,
            variant_a_views,
            variant_b_views,
            variant_a_ctr,
            variant_b_ctr,
            test_start,
            test_end,
            status,
        ) = test_row

        winner = (
            "variant_a"
            if (variant_a_views or 0) > (variant_b_views or 0)
            else (
                "variant_b"
                if (variant_b_views or 0) > (variant_a_views or 0)
                else "tie"
            )
        )

        return {
            "variant_a": variant_a,
            "variant_b": variant_b,
            "variant_a_views": variant_a_views or 0,
            "variant_b_views": variant_b_views or 0,
            "variant_a_ctr": round(float(variant_a_ctr or 0), 4),
            "variant_b_ctr": round(float(variant_b_ctr or 0), 4),
            "winner": winner,
            "confidence": _calculate_confidence(variant_a_views, variant_b_views),
            "test_duration_hours": (
                (datetime.fromisoformat(test_end) - datetime.fromisoformat(test_start)).total_seconds() / 3600
                if test_end and test_start
                else 0
            ),
            "status": status,
        }

    def creator_preference_analysis(self) -> dict[str, Any]:
        """Analyze creator-specific preferences from performance data."""
        connection = self.history_store._connect()

        # Analyze performance by title characteristics
        title_pattern_rows = connection.execute(
            """
            SELECT
                CASE
                    WHEN LENGTH(t.title) < 40 THEN 'SHORT'
                    WHEN LENGTH(t.title) BETWEEN 40 AND 60 THEN 'MEDIUM'
                    ELSE 'LONG'
                END as title_length,
                AVG(p.click_through_rate) as avg_ctr,
                AVG(p.average_view_duration_percent) as avg_retention,
                COUNT(DISTINCT p.video_id) as video_count
            FROM performance_metrics p
            JOIN video_uploads t ON p.video_id = t.video_id
            GROUP BY title_length
            ORDER BY avg_ctr DESC
            """
        ).fetchall()

        # Analyze tag effectiveness
        tag_rows = connection.execute(
            """
            SELECT
                tag,
                COUNT(*) as usage_count,
                AVG(view_count) as avg_views_with_tag
            FROM (
                SELECT video_id, TRIM(tag) as tag, view_count
                FROM video_uploads
                JOIN performance_metrics USING(video_id),
                (
                    WITH RECURSIVE split(tag, rest) AS (
                        SELECT '', tags || ','
                        FROM video_uploads
                        UNION ALL
                        SELECT
                            SUBSTR(rest, 0, INSTR(rest, ',') + 1),
                            SUBSTR(rest, INSTR(rest, ',') + 1)
                        FROM split
                        WHERE rest != ''
                    )
                    SELECT tag FROM split WHERE tag != ''
                )
            )
            GROUP BY tag
            HAVING COUNT(*) >= 2
            ORDER BY avg_views_with_tag DESC
            LIMIT 10
            """
        ).fetchall()

        return {
            "title_preferences": [
                {
                    "length_category": row[0],
                    "avg_ctr": round(float(row[1] or 0), 4),
                    "avg_retention_percent": round(float(row[2] or 0), 2),
                    "video_sample_size": row[3],
                }
                for row in title_pattern_rows
            ],
            "top_performing_tags": [
                {
                    "tag": row[0],
                    "usage_count": row[1],
                    "avg_views": int(row[2] or 0),
                }
                for row in tag_rows
            ],
        }

    def algorithm_refinement_insights(self) -> dict[str, Any]:
        """Generate insights for algorithm refinement based on performance."""
        connection = self.history_store._connect()

        # Find patterns in high-performing videos
        high_performers = connection.execute(
            """
            SELECT
                t.title,
                p.click_through_rate,
                p.average_view_duration_percent,
                p.view_count,
                CASE WHEN p.view_count > 10000 THEN 'HIGH' 
                     WHEN p.view_count > 5000 THEN 'MEDIUM'
                     ELSE 'LOW' END as performance_tier
            FROM performance_metrics p
            JOIN video_uploads t ON p.video_id = t.video_id
            WHERE p.view_count > (
                SELECT AVG(view_count) FROM performance_metrics
            )
            ORDER BY p.view_count DESC
            LIMIT 5
            """
        ).fetchall()

        # Analyze weak performers for improvement areas
        weak_performers = connection.execute(
            """
            SELECT
                t.title,
                p.click_through_rate,
                p.average_view_duration_percent,
                p.view_count
            FROM performance_metrics p
            JOIN video_uploads t ON p.video_id = t.video_id
            WHERE p.view_count < (
                SELECT AVG(view_count) * 0.5 FROM performance_metrics
            )
            ORDER BY p.view_count ASC
            LIMIT 5
            """
        ).fetchall()

        refinements = []
        if high_performers and weak_performers:
            avg_high_ctr = sum(row[1] or 0 for row in high_performers) / len(high_performers)
            avg_weak_ctr = sum(row[1] or 0 for row in weak_performers) / len(weak_performers)

            if avg_high_ctr > avg_weak_ctr * 1.2:
                refinements.append(
                    {
                        "area": "Title CTR Optimization",
                        "insight": f"Top performers have {round(avg_high_ctr * 100, 2)}% CTR vs weak {round(avg_weak_ctr * 100, 2)}%",
                        "recommendation": "Focus on curiosity gaps and power words",
                    }
                )

            avg_high_retention = sum(row[2] or 0 for row in high_performers) / len(high_performers)
            avg_weak_retention = sum(row[2] or 0 for row in weak_performers) / len(weak_performers)

            if avg_high_retention > avg_weak_retention * 1.3:
                refinements.append(
                    {
                        "area": "Content Retention",
                        "insight": f"Top performers retain {round(avg_high_retention, 2)}% vs weak {round(avg_weak_retention, 2)}%",
                        "recommendation": "Analyze pacing and hook patterns in high-retention videos",
                    }
                )

        return {
            "refinements": refinements,
            "high_performer_sample": [
                {
                    "title": row[0],
                    "ctr": round(float(row[1] or 0), 4),
                    "retention": round(float(row[2] or 0), 2),
                    "views": int(row[3] or 0),
                }
                for row in high_performers
            ],
            "weak_performer_sample": [
                {
                    "title": row[0],
                    "ctr": round(float(row[1] or 0), 4),
                    "retention": round(float(row[2] or 0), 2),
                    "views": int(row[3] or 0),
                }
                for row in weak_performers
            ],
        }


def _calculate_confidence(views_a: int | None, views_b: int | None) -> str:
    """Calculate statistical confidence in A/B test results."""
    a = views_a or 0
    b = views_b or 0
    total = a + b

    if total < 100:
        return "LOW"
    elif total < 500:
        return "MODERATE"
    else:
        return "HIGH"
