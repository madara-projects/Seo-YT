from __future__ import annotations

from typing import Any


def build_automation_workflow(
    title: str,
    hashtags: list[str],
    chapters: list[dict[str, str]],
    content_graph_strategy: dict[str, Any],
) -> dict[str, Any]:
    """Create a practical publishing workflow checklist."""

    chapter_ready = bool(chapters)
    supporting_topics = content_graph_strategy.get("supporting_topics", [])

    return {
        "pre_publish_checklist": [
            f"Finalize title: {title}",
            "Check thumbnail against the recommended style.",
            "Review the first 30 seconds for a clear hook and payoff.",
            f"Confirm hashtags: {' '.join(hashtags[:5])}",
            "Run one final competitor scan before publishing.",
        ],
        "publish_workflow": [
            "Upload video and paste the optimized description.",
            "Add chapters before publishing." if chapter_ready else "Add manual timestamps once the cut is final.",
            "Pin a comment that bridges into the next video.",
            "Track the first 24h for CTR and early retention signals.",
        ],
        "next_actions": [
            f"Turn this video into a small series around: {', '.join(supporting_topics[:3])}" if supporting_topics else "Plan the next follow-up video in the same topic cluster.",
            "Save the result export for comparison after publish.",
        ],
    }
