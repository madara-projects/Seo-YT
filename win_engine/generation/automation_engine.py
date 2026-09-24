from __future__ import annotations

from typing import Any


def build_automation_workflow(
    title: str,
    hashtags: list[str],
    chapters: list[dict[str, str]],
    content_graph_strategy: dict[str, Any],
    *,
    short_form: bool = False,
) -> dict[str, Any]:
    """Create a practical publishing workflow checklist.

    A Short has no first 30 seconds to review and no timestamps to add, so it
    gets its own checklist.
    """

    supporting_topics = content_graph_strategy.get("supporting_topics", [])
    series_step = (
        f"Plan companion {'Shorts' if short_form else 'videos'} around: {', '.join(supporting_topics[:3])}"
        if supporting_topics
        else f"Plan the next {'Short' if short_form else 'video'} in the same topic cluster."
    )
    if short_form:
        return {
            "pre_publish_checklist": [
                f"Finalize title: {title}",
                "Check the on-screen text stays readable on a phone for the whole clip.",
                "Choose a cover frame where the text is fully legible over the background.",
                f"Confirm hashtags: {' '.join(hashtags[:5])}",
            ],
            "publish_workflow": [
                "Upload as a vertical Short and paste the optimized description.",
                "Pin a comment that links the next Short in the series.",
                "Check views and average percentage viewed after 24 hours.",
            ],
            "next_actions": [series_step, "Save the result export for comparison after publish."],
        }

    chapter_ready = bool(chapters)
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
        "next_actions": [series_step, "Save the result export for comparison after publish."],
    }
