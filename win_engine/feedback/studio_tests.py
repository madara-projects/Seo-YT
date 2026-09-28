"""YouTube Studio's own title and thumbnail test, prepared and recorded here.

YouTube runs the test ("Test & Compare"): up to three title/thumbnail variants
on one long-form video, shown to viewers at the same time, with the winner
picked by watch-time share. It is not available for Shorts. This app never runs
it and never changes a video. It keeps the variants the creator chose from a
saved package, the published video they were tested on, and the result the
creator read in Studio.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from win_engine.analysis.generation_quality import title_similarity
from win_engine.analysis.source_cues import is_short_video
from win_engine.feedback.history_store import HistoryStore, comparable_format

MIN_VARIANTS = 2
MAX_VARIANTS = 3
VARIANT_LABELS = ("A", "B", "C")
# Generation drops a new title this similar to one it already kept; two
# variants this close tell a test little.
SIMILAR_TITLE_THRESHOLD = 0.82
OUTCOMES = ("winner", "no_clear_winner")
# Studio shows rounded percentages, so a complete set may miss 100 slightly.
_SHARE_TOLERANCE = 1.5
_SHORT_FORMATS = frozenset({"youtube_shorts", "quote"})
SHORTS_NOTE = "YouTube's Test & Compare is not available for Shorts, so no test can be prepared for this package."
NATIVE_TEST_NOTE = (
    "YouTube Studio runs this test: it shows each variant to viewers over the same period and picks the "
    "winner by watch-time share. This app never runs it and never changes your video; it keeps what you "
    "prepared and the result you read in Studio. The app's own before/after comparisons (experiments and "
    "snapshots) compare different periods, so they are not equivalent to YouTube's test."
)


class StudioTestError(ValueError):
    """A request the test cannot accept; the message says what to change."""


class CreateStudioTestRequest(BaseModel):
    """The saved packages to test. Their titles and thumbnail texts are read from the saved run."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    package_ids: list[str] = Field(..., min_length=1, max_length=10)
    notes: str = Field(default="", max_length=2000)


class UpdateStudioTestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    # Attach the package's current published-video link.
    link_video: bool | None = None
    outcome: Literal["winner", "no_clear_winner"] | None = None
    winner_variant: str | None = Field(default=None, max_length=1)
    # Percent of watch time per variant label, as Studio shows it.
    watch_time_share: dict[str, float] | None = None
    notes: str | None = Field(default=None, max_length=2000)


def run_is_short(run: dict[str, Any], link: dict[str, Any] | None = None) -> bool:
    """Whether the video published from a saved package, or else the package itself, is a Short."""
    published_format = comparable_format((link or {}).get("format"))
    if published_format and published_format != "unknown":
        return published_format in _SHORT_FORMATS
    payload = run.get("package") if isinstance(run.get("package"), dict) else {}
    brief = payload.get("creator_brief") if isinstance(payload.get("creator_brief"), dict) else {}
    return is_short_video(brief.get("content") or run.get("query") or "", brief)


def candidate_packages(run: dict[str, Any]) -> list[dict[str, str]]:
    """The saved run's title/thumbnail packages, with the IDs the selection uses."""
    payload = run.get("package") if isinstance(run.get("package"), dict) else {}
    candidates = []
    for index, item in enumerate(payload.get("title_thumbnail_packages") or []):
        if not isinstance(item, dict) or not str(item.get("title") or "").strip():
            continue
        candidates.append({
            "package_id": str(item.get("package_id") or f"package-{chr(97 + index)}"),
            "title": str(item.get("title")).strip(),
            "thumbnail_text": str(item.get("thumbnail_text") or "").strip(),
        })
    return candidates


def similar_pairs(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Pairs of titles too alike to tell a test much, named by `key`."""
    pairs = []
    for first, second in combinations(items, 2):
        score = title_similarity(first["title"], second["title"])
        if score >= SIMILAR_TITLE_THRESHOLD:
            pairs.append({
                "first": first[key], "second": second[key], "similarity": score,
                "message": f"{first[key]} and {second[key]} have titles too similar to tell apart in a test.",
            })
    return pairs


class StudioTestStore:
    def __init__(self, history: HistoryStore):
        self.history = history

    def overview(self, run_id: int) -> dict[str, Any] | None:
        """What can be prepared for a saved package, and the tests prepared for it."""
        run = self.history.history_run(run_id)
        if not run:
            return None
        link = self._published_link(run_id)
        short = run_is_short(run, link)
        candidates = candidate_packages(run)
        return {
            "analysis_run_id": run_id,
            "eligible": not short,
            "video_format": "short" if short else "long_form",
            "reason": SHORTS_NOTE if short else None,
            "min_variants": MIN_VARIANTS,
            "max_variants": MAX_VARIANTS,
            "candidates": candidates,
            "similar_pairs": similar_pairs(candidates, "package_id"),
            "linked_video": {"link_id": link["id"], "youtube_video_id": link["youtube_video_id"]} if link else None,
            "tests": self.tests(run_id),
            "note": NATIVE_TEST_NOTE,
        }

    def create(self, run_id: int, package_ids: list[str], notes: str = "") -> dict[str, Any] | None:
        run = self.history.history_run(run_id)
        if not run:
            return None
        if run_is_short(run, self._published_link(run_id)):
            raise StudioTestError(SHORTS_NOTE)
        if len(package_ids) > MAX_VARIANTS:
            raise StudioTestError("YouTube's Test & Compare runs up to three variants. Choose two or three packages.")
        if len(package_ids) < MIN_VARIANTS:
            raise StudioTestError("A test needs at least two variants. Choose two or three packages.")
        if len(set(package_ids)) != len(package_ids):
            raise StudioTestError("Each package can be a variant only once; one was chosen twice.")
        candidates = {item["package_id"]: item for item in candidate_packages(run)}
        missing = [package_id for package_id in package_ids if package_id not in candidates]
        if missing:
            raise StudioTestError(f"{', '.join(missing)} is not part of this saved package.")
        variants = [{"label": label, **candidates[package_id]} for label, package_id in zip(VARIANT_LABELS, package_ids)]
        now = datetime.now(timezone.utc).isoformat()
        with self.history._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO youtube_studio_tests (analysis_run_id, variants_json, status, notes, created_at, updated_at)
                   VALUES (?, ?, 'prepared', ?, ?, ?)""",
                (run_id, json.dumps(variants), notes or "", now, now),
            )
            test_id = int(cursor.lastrowid or 0)
        return self.test(test_id)

    def tests(self, run_id: int) -> list[dict[str, Any]]:
        return self._tests("t.analysis_run_id = ?", (run_id,))

    def test(self, test_id: int) -> dict[str, Any] | None:
        found = self._tests("t.id = ?", (test_id,))
        return found[0] if found else None

    def update(self, test_id: int, changes: dict[str, Any]) -> dict[str, Any] | None:
        test = self.test(test_id)
        if not test:
            return None
        link_id = test["linked_video"]["link_id"] if test["linked_video"] else None
        status = test["status"]
        winner, result = test["winner_variant"], test["result"]
        if changes.get("link_video"):
            if test["result"] and not link_id:
                raise StudioTestError(
                    "This test's result was recorded for a video that is no longer linked to this package. "
                    "Prepare a new test for the new video."
                )
            run = self.history.history_run(test["analysis_run_id"]) or {}
            link = self._published_link(test["analysis_run_id"])
            if not link:
                raise StudioTestError("Link the published video to this package in History first.")
            if run_is_short(run, link):
                raise StudioTestError(SHORTS_NOTE)
            link_id = int(link["id"])
            status = "linked" if status == "prepared" else status
        if changes.get("outcome") or changes.get("winner_variant") or changes.get("watch_time_share"):
            if not link_id:
                raise StudioTestError("Link the published video before recording Studio's result.")
            winner, result = _result(test, changes)
            status = "completed"
        notes = test["notes"] if changes.get("notes") is None else str(changes["notes"])
        with self.history._connect() as connection:
            connection.execute(
                """UPDATE youtube_studio_tests
                   SET published_video_link_id = ?, status = ?, winner_variant = ?, result_json = ?,
                       notes = ?, updated_at = ?
                   WHERE id = ?""",
                (link_id, status, winner, json.dumps(result) if result else None, notes,
                 datetime.now(timezone.utc).isoformat(), test_id),
            )
        return self.test(test_id)

    def _published_link(self, run_id: int) -> dict[str, Any] | None:
        """The package's published video, with the format the creator confirmed for it when known."""
        link = self.history.published_video_link_by_run(run_id)
        if link:
            comparable = self.history.comparable_metadata(int(link["id"])) or {}
            if str(comparable.get("format") or "unknown") != "unknown":
                link = {**link, "format": comparable["format"]}
        return link

    def _tests(self, where: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        with self.history._connect() as connection:
            rows = connection.execute(
                f"""SELECT t.id, t.analysis_run_id, t.published_video_link_id, t.variants_json, t.status,
                           t.winner_variant, t.result_json, t.notes, t.created_at, t.updated_at,
                           p.youtube_video_id, p.analysis_run_id
                    FROM youtube_studio_tests t
                    LEFT JOIN published_video_links p ON p.id = t.published_video_link_id
                    WHERE {where} ORDER BY t.created_at DESC, t.id DESC""",
                params,
            ).fetchall()
        tests = []
        for row in rows:
            variants = _json(row[3]) or []
            # A video relinked to another package took its link along; it is not this test's video any more.
            linked = row[2] is not None and row[11] == row[1]
            tests.append({
                "id": row[0],
                "analysis_run_id": row[1],
                "linked_video": {"link_id": row[2], "youtube_video_id": row[10]} if linked else None,
                "variants": variants,
                "status": row[4],
                "winner_variant": row[5],
                "result": _json(row[6]),
                "notes": row[7] or "",
                "created_at": row[8],
                "updated_at": row[9],
                "similar_pairs": similar_pairs(variants, "label"),
            })
        return tests


def _result(test: dict[str, Any], changes: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """The winner and result as the creator read them in Studio, checked against the test's variants."""
    labels = [variant["label"] for variant in test["variants"]]
    outcome = changes.get("outcome")
    winner = str(changes.get("winner_variant") or "").strip().upper() or None
    if outcome not in OUTCOMES:
        raise StudioTestError("Choose the outcome Studio shows: a winner, or no clear winner.")
    if outcome == "winner" and not winner:
        raise StudioTestError("Choose the winning variant Studio shows.")
    if outcome == "no_clear_winner" and winner:
        raise StudioTestError("A result with no clear winner has no winner variant.")
    if winner and winner not in labels:
        raise StudioTestError(f"{winner} is not a variant of this test.")
    shares: dict[str, float] = {}
    for label, value in (changes.get("watch_time_share") or {}).items():
        key = str(label).strip().upper()
        if key not in labels:
            raise StudioTestError(f"{key} is not a variant of this test.")
        share = float(value)
        if not 0 <= share <= 100:
            raise StudioTestError("Each watch-time share is a percentage between 0 and 100.")
        shares[key] = round(share, 1)
    total = sum(shares.values())
    if total > 100 + _SHARE_TOLERANCE or (len(shares) == len(labels) and total < 100 - _SHARE_TOLERANCE):
        raise StudioTestError("Studio's watch-time shares add up to 100%. Check the numbers you entered.")
    return winner, {
        "outcome": outcome,
        "watch_time_share": shares,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source": "creator_read_youtube_studio",
    }


def _json(value: str | None) -> Any:
    try:
        return json.loads(value) if value else None
    except (TypeError, ValueError):
        return None
