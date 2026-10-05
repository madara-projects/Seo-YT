"""The AI Shorts path: a quote in, Google Flow (Veo 3.1) prompts and a lean SEO package out.

The creator types only a quote. The Flow planner (``flow_prompts``) reads its
feeling and writes one prompt per eight-second part; this module then writes
the package the Creator page would write for a quote Short, saves it to History
so the published Short can be linked later, and keeps the plan beside that run.

What this path does not do, by design:

* No YouTube Data API call. The package is written from the quote and the
  plan's mood alone, through the same writer, tag selector and quality gate as
  every other package, with the research stage left empty. The Opportunity
  Score needs research, so it is reported as unmeasured, never as 0.
* No more than four Gemini calls per request: at most two for the planner and
  two for the package, each stage under its own ``gemini_client.request_budget``
  with one shared deadline. A nested budget shares the outer allowance, so the
  route must not wrap this in the shared ``_gemini_budget`` decorator, which
  would replace the per-stage caps with the general allowance.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.research_insights import build_research_decision
from win_engine.feedback.ai_shorts_store import AiShortsStore
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.llm import gemini_client

logger = logging.getLogger(__name__)

PLANNER_MAX_CALLS = 2
PACKAGE_MAX_CALLS = 2
MAX_GEMINI_CALLS = PLANNER_MAX_CALLS + PACKAGE_MAX_CALLS
VIDEO_FORMAT = "youtube_shorts"
RESEARCH_SKIPPED_WARNING = (
    "No YouTube research was made on the AI Shorts path: the Opportunity Score is unmeasured, "
    "and tags and hashtags come from the quote alone."
)
# The generator explains an empty research payload as a search that found
# nothing. Here no search was made, so that line is replaced by the one above.
_EMPTY_RESEARCH_WARNING_PREFIX = "Keyword signals are unavailable"


class QuoteRefused(ValueError):
    """The planner refused the quote or the part count: the creator's input, a 422.

    Any other ValueError is the server's own failure and must not be shown as
    a verdict on the quote.
    """


def _check_planner_inputs(quote: str, parts: int) -> None:
    """The planner's own input check, run before it: its ValueError is the only verdict on the quote."""
    from win_engine.generation.flow_prompts import validate_inputs

    try:
        validate_inputs(quote, parts)
    except ValueError as exc:
        raise QuoteRefused(str(exc)) from exc


def _plan_flow_shots(quote: str, *, language: str, parts: int, mood_hint: str) -> dict[str, Any]:
    """The Flow planner, imported on first use so this module loads without it."""
    from win_engine.generation.flow_prompts import plan_flow_shots

    return plan_flow_shots(quote, language=language, parts=parts, mood_hint=mood_hint)


def creator_brief_for_quote(quote: str, plan: dict[str, Any], *, language: str, region: str) -> dict[str, Any]:
    """The brief the Creator page would build for this quote Short, with the plan's scene as its visual.

    The quote is the exact on-screen text (the plan's text overlay shows it), the
    format is a Short, and the length is the plan's total. Voice-over stays
    unknown: the plan's audio is Flow's generated sound, not a decision about
    narration the creator may add in the edit.
    """
    mood = plan.get("mood") if isinstance(plan.get("mood"), dict) else {}
    total_seconds = plan.get("total_seconds")
    duration = float(total_seconds) if isinstance(total_seconds, (int, float)) and total_seconds > 0 else None
    return build_creator_brief(
        script=quote,
        video_format=VIDEO_FORMAT,
        exact_quote=quote,
        on_screen_text=quote,
        visual_requirements=str(mood.get("visual_metaphor") or ""),
        duration_seconds=duration,
        language=language,
        region=region,
    )


def lean_research(history: HistoryStore, creator_brief: dict[str, Any]) -> dict[str, Any]:
    """The research payload of a run that made no research: every field the generator reads, empty.

    With no YouTube results the generator records the Opportunity Score as
    UNMEASURED (score None) and the gap analysis says demand and competition
    could not be measured; nothing here pretends otherwise.
    """
    return {
        "history_store": history,
        "youtube_results": [],
        "top_opportunities": [],
        "keyword_signals": [],
        "entity_signals": [],
        "keyword_research": {},
        "upload_timing": {},
        "thumbnail_intelligence": {},
        "research_queries": [],
        "research_decision": {
            **build_research_decision(creator_brief, []),
            "research_skipped": True,
            "research_skipped_reason": RESEARCH_SKIPPED_WARNING,
        },
        "research_warnings": [RESEARCH_SKIPPED_WARNING],
        "cache_policy": "not_researched",
    }


def _honest_research_warnings(warnings: Any, *, brief_warnings: Any = ()) -> list[str]:
    """The package's warnings without the lines that mean nothing on this path.

    ``brief_warnings`` are the creator brief's own ("who the video is for is
    unknown", "proof ... is unknown", "Voice Over is unknown"): the brief is
    built from a quote and a Flow plan, so those fields are unknown by design.
    """
    noise = {str(item or "").strip() for item in (brief_warnings if isinstance(brief_warnings, list) else [])}
    kept: list[str] = []
    for item in warnings if isinstance(warnings, list) else []:
        text = str(item or "").strip()
        if not text or text.startswith(_EMPTY_RESEARCH_WARNING_PREFIX) or text in noise or text in kept:
            continue
        kept.append(text)
    if RESEARCH_SKIPPED_WARNING not in kept:
        kept.insert(0, RESEARCH_SKIPPED_WARNING)
    return kept


def generate_ai_short(
    history: HistoryStore,
    *,
    quote: str,
    language: str = "english",
    parts: int = 2,
    mood_hint: str = "",
    region: str = "global",
    deadline_seconds: float | None = None,
) -> dict[str, Any]:
    """Plan the Flow shots for a quote, write its lean package, save both, and return the saved plan.

    The result is the saved plan exactly as ``GET /api/ai-shorts/plans/{id}``
    returns it: ``id``, ``analysis_run_id`` and ``created_at``, every key of the
    planner's result, and ``package`` (the History run's payload, which carries
    ``source_page`` and an ``ai_shorts`` block naming the plan).

    ``deadline_seconds`` is one deadline for both Gemini stages; the package
    stage gets whatever the planner left. Without it each stage runs under the
    configured default deadline. Raises QuoteRefused for a quote or part count
    the planner refuses.
    """
    quote = str(quote or "").strip()
    language = str(language or "english").strip().lower() or "english"
    region = str(region or "global").strip().lower() or "global"
    started = time.monotonic()

    def time_left() -> float | None:
        if deadline_seconds is None:
            return None
        return max(0.0, float(deadline_seconds) - (time.monotonic() - started))

    # Checked first, so a ValueError from deeper in the planner (a provider reply
    # it could not read, say) is the server's failure, never "your quote was refused".
    _check_planner_inputs(quote, parts)
    with gemini_client.request_budget(max_calls=PLANNER_MAX_CALLS, deadline_seconds=time_left()):
        plan = dict(_plan_flow_shots(quote, language=language, parts=parts, mood_hint=str(mood_hint or "")))
    plan_parts = int(plan.get("parts") or parts)

    creator_brief = creator_brief_for_quote(quote, plan, language=language, region=region)
    context = {
        "language": language,
        "video_language": language,
        "region": region,
        "audience_type": "general",
        "creator_brief": creator_brief,
    }
    with history.recording_runs() as recorded:
        try:
            with gemini_client.request_budget(max_calls=PACKAGE_MAX_CALLS, deadline_seconds=time_left()):
                package = generate_seo_suggestions(quote, lean_research(history, creator_brief), context=context)
            run_id = package.get("history_run_id")
            if not isinstance(run_id, int):
                raise RuntimeError("The AI Shorts package was not saved to History.")
        except Exception:
            # The stage records its run before it finishes; left behind, that run
            # would sit in History as an ordinary package made from a bare quote.
            if recorded:
                logger.exception("The AI Shorts package stage failed; its History runs %s are removed.", recorded)
                history.delete_analysis_runs(recorded)
            raise
    package["research_warnings"] = _honest_research_warnings(
        package.get("research_warnings"), brief_warnings=creator_brief.get("warnings") or [],
    )

    store = AiShortsStore(history)
    try:
        plan_id = store.save_plan(
            analysis_run_id=run_id, quote=quote, language=language, parts=plan_parts, plan=plan, package=package,
        )
    except Exception:
        # Without its plan the run would sit in History as an ordinary package
        # made from a bare quote; the two are kept together or not at all.
        logger.exception("The AI Shorts plan could not be saved; its History run %s is removed.", run_id)
        history.delete_analysis_runs([run_id])
        raise
    saved = store.plan(plan_id)
    if saved is None:
        raise RuntimeError("The AI Shorts plan was saved but could not be read back.")
    return saved
