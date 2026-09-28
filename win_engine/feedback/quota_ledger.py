"""What this app spends of its YouTube API quotas, per Pacific quota day.

YouTube does not report how much of a quota is left, so every request the app
sends is counted here and compared with daily limits the owner copies from
Google Cloud Console (WIN_ENGINE_YOUTUBE_SEARCH_CALLS_PER_DAY and
WIN_ENGINE_YOUTUBE_UNITS_PER_DAY, per key's project).

Since 1 June 2026 the Data API has separate buckets: search.list has its own
daily allowance of calls (100 by default), and every other method draws units
from a shared bucket (10,000 a day by default); the read methods this app calls
cost 1 unit each. The YouTube Analytics API has a quota of its own, so its
requests are only counted. Every quota resets at midnight Pacific time.

A source is "key1", "key2"... for the API key in that slot of the key pool (never
the key itself), or "oauth" for the connected channel.
"""

from __future__ import annotations

import atexit
import functools
import logging
import queue
import sqlite3
import threading
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

from win_engine.feedback.migrations import ClosingConnection

if TYPE_CHECKING:
    from win_engine.core.config import Settings

logger = logging.getLogger(__name__)

try:
    QUOTA_ZONE: tzinfo = ZoneInfo("America/Los_Angeles")
except ZoneInfoNotFoundError:  # no tz database: standard time, an hour early in summer
    QUOTA_ZONE = timezone(timedelta(hours=-8))

SEARCH, DEFAULT, ANALYTICS = "search", "default", "analytics"
OAUTH_SOURCE = "oauth"
# A bucket this full puts a warning on research responses. Nothing is blocked:
# the limits are the owner's own estimates.
WARNING_SHARE = 0.9
# How long a reader waits for a busy database, and for counts still queued.
_DATABASE_TIMEOUT_SECONDS = 5.0
_FLUSH_TIMEOUT_SECONDS = 2.0
# The writer has its own thread, so it can wait long for a busy database (a
# cloud-sync pull, a migration); a batch still refused is tried again, with
# whatever arrived meanwhile, before it is given up on.
_WRITER_TIMEOUT_SECONDS = 30.0
_RETRY_DELAY_SECONDS = 1.0
_WRITE_ATTEMPTS = 3
_UPSERT = (
    "INSERT INTO youtube_quota_usage (quota_date, source, bucket, calls, units, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (quota_date, source, bucket) DO UPDATE SET "
    "calls = calls + excluded.calls, units = units + excluded.units, updated_at = excluded.updated_at"
)
# (database path, quota date, source, bucket, units, sent at)
_Count = tuple[str, str, str, str, int, str]


def quota_date(now: datetime | None = None) -> date:
    """The Pacific day whose quota a request sent at ``now`` draws on."""
    return (now or datetime.now(timezone.utc)).astimezone(QUOTA_ZONE).date()


def next_reset(now: datetime | None = None) -> datetime:
    """When the quota day of ``now`` ends: the next Pacific midnight, in UTC."""
    tomorrow = quota_date(now) + timedelta(days=1)
    return datetime.combine(tomorrow, time(0), tzinfo=QUOTA_ZONE).astimezone(timezone.utc)


def api_key_source(slot: int) -> str:
    """The ledger's name for the API key in 1-based ``slot`` of the key pool."""
    return f"key{slot}"


def charge(method: str) -> tuple[str, int]:
    """The bucket a request draws on, and the units it adds to that bucket.

    ``method`` is a discovery method id ("youtube.search.list",
    "youtubeAnalytics.reports.query") or a Data API "resource.method".
    """
    if method.startswith("youtubeAnalytics."):
        return ANALYTICS, 0
    if method.removeprefix("youtube.") == "search.list":
        return SEARCH, 0
    # The app holds read-only scopes, so every other method is a 1-unit read.
    return DEFAULT, 1


def _connect(database_path: str, timeout: float = _DATABASE_TIMEOUT_SECONDS) -> sqlite3.Connection:
    # mode=rw: counting never creates a database where there is none.
    uri = f"{Path(database_path).resolve().as_uri()}?mode=rw"
    connection = sqlite3.connect(uri, uri=True, timeout=timeout, factory=ClosingConnection)
    # As on the app's other connections; in WAL mode it skips an fsync per commit.
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def _write(counts: list[_Count]) -> list[_Count]:
    """Add queued counts to the ledger, summed: one transaction per database.

    Returns the counts a busy database refused, to be tried again. Any other
    error (no database, no table) is logged and its counts are dropped.
    """
    batches: dict[str, list[_Count]] = {}
    for count in counts:
        batches.setdefault(count[0], []).append(count)
    refused: list[_Count] = []
    for database_path, batch in batches.items():
        totals: dict[tuple[str, str, str], list[Any]] = {}
        for _, day, source, bucket, units, sent_at in batch:
            row = totals.setdefault((day, source, bucket), [0, 0, sent_at])
            row[0], row[1], row[2] = row[0] + 1, row[1] + units, max(row[2], sent_at)
        try:
            with _connect(database_path, _WRITER_TIMEOUT_SECONDS) as connection:
                connection.executemany(_UPSERT, [(*key, *values) for key, values in totals.items()])
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc) or "busy" in str(exc):
                refused.extend(batch)
            else:
                logger.warning("YouTube quota usage was not recorded: %s", type(exc).__name__)
        except Exception as exc:  # noqa: BLE001 - a lost count must never stop the writer
            logger.warning("YouTube quota usage was not recorded: %s", type(exc).__name__)
    return refused


class _Writer:
    """Writes counts on one background thread, so no request waits for the database.

    Opening, writing and closing the database for each count took 50-100 ms on
    the Docker volume, added to every YouTube request.
    """

    def __init__(self) -> None:
        self._queue: queue.SimpleQueue[_Count | threading.Event] = queue.SimpleQueue()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def put(self, item: _Count | threading.Event) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="youtube-quota-ledger", daemon=True)
                self._thread.start()
        self._queue.put(item)

    def flush(self, timeout: float = _FLUSH_TIMEOUT_SECONDS) -> bool:
        """Wait until every count queued so far is written or given up on; False on a timeout."""
        if self._thread is None:
            return True
        done = threading.Event()
        self.put(done)
        return done.wait(timeout)

    def _run(self) -> None:
        refused: list[_Count] = []
        waiting: list[threading.Event] = []
        attempts = 0
        while True:
            try:
                # A refused batch is tried again after a pause, with whatever arrived meanwhile.
                items = [self._queue.get(timeout=_RETRY_DELAY_SECONDS if refused else None)]
            except queue.Empty:
                items = []
            while not self._queue.empty():
                items.append(self._queue.get_nowait())
            waiting += [item for item in items if isinstance(item, threading.Event)]
            counts = refused + [item for item in items if not isinstance(item, threading.Event)]
            refused = (_write(counts) or []) if counts else []
            attempts = attempts + 1 if refused else 0
            if refused and attempts >= _WRITE_ATTEMPTS:
                logger.warning("YouTube quota usage was not recorded: the database stayed busy.")
                refused, attempts = [], 0
            # A flush waits until its counts are written or given up on.
            if not refused:
                for event in waiting:
                    event.set()
                waiting = []


_WRITER = _Writer()
# The counts of the last requests before the app stops.
atexit.register(_WRITER.flush)


def flush(timeout: float = _FLUSH_TIMEOUT_SECONDS) -> bool:
    """Write every count queued so far; False when the writer did not finish in time."""
    return _WRITER.flush(timeout)


class QuotaLedger:
    """Calls and units per Pacific day, source and bucket (table youtube_quota_usage)."""

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    def record(self, source: str, method: str, *, now: datetime | None = None) -> None:
        """Count one request sent to YouTube.

        Returns at once and never raises: the count is written in the
        background, where a database error is logged and the count dropped.
        """
        bucket, units = charge(method)
        moment = now or datetime.now(timezone.utc)
        _WRITER.put((self._database_path, quota_date(moment).isoformat(), source, bucket, units, moment.isoformat()))

    def usage(self, day: date) -> dict[tuple[str, str], tuple[int, int]]:
        """(calls, units) by (source, bucket) on one quota day, queued counts included.

        Raises when the ledger cannot be read.
        """
        flush()
        with _connect(self._database_path) as connection:
            rows = connection.execute(
                "SELECT source, bucket, calls, units FROM youtube_quota_usage WHERE quota_date = ?",
                (day.isoformat(),),
            ).fetchall()
        return {(str(source), str(bucket)): (int(calls), int(units)) for source, bucket, calls, units in rows}


class _RecordedRequest(HttpRequest):
    """A googleapiclient request, counted once YouTube has answered it, refusals included.

    A request that timed out was sent and may have been served, so it counts
    too, as youtube_client counts a read timeout; a connection that failed
    never reached YouTube and does not.
    """

    def __init__(self, *args: Any, ledger: QuotaLedger, source: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._ledger, self._source = ledger, source

    def execute(self, http=None, num_retries=0):
        try:
            result = super().execute(http=http, num_retries=num_retries)
        except (HttpError, TimeoutError):
            self._ledger.record(self._source, str(self.methodId))
            raise
        self._ledger.record(self._source, str(self.methodId))
        return result


def recording_request_builder(database_path: str, source: str) -> Callable[..., HttpRequest]:
    """A ``requestBuilder`` for googleapiclient's build() that counts every request it sends."""
    return functools.partial(_RecordedRequest, ledger=QuotaLedger(database_path), source=source)


def _label(source: str) -> str:
    if source == OAUTH_SOURCE:
        return "Connected channel"
    if source.startswith("key") and source[3:].isdigit():
        return f"API key {source[3:]}"
    return source


def _source_usage(source: str, usage: dict[tuple[str, str], tuple[int, int]], search_limit: int,
                  unit_limit: int) -> dict[str, Any]:
    searches = usage.get((source, SEARCH), (0, 0))[0]
    calls, units = usage.get((source, DEFAULT), (0, 0))
    return {
        "source": source,
        "label": _label(source),
        "search": {"used": searches, "limit": search_limit, "remaining": max(0, search_limit - searches)},
        "default": {"calls": calls, "used": units, "limit": unit_limit, "remaining": max(0, unit_limit - units)},
        "analytics": {"calls": usage.get((source, ANALYTICS), (0, 0))[0]},
    }


def _warnings(sources: list[dict[str, Any]]) -> list[str]:
    warnings = []
    for item in sources:
        for bucket, noun in ((SEARCH, "searches"), (DEFAULT, "units")):
            used, limit = item[bucket]["used"], item[bucket]["limit"]
            if used >= WARNING_SHARE * limit:
                warnings.append(
                    f"YouTube quota: {item['label']} has used {used:,} of {limit:,} {noun} today, 90% or more "
                    "of its configured daily limit. Requests may fail until the quota resets at midnight Pacific time."
                )
    return warnings


def quota_status(settings: Settings, *, oauth_connected: bool | None = False,
                 now: datetime | None = None) -> dict[str, Any]:
    """Today's usage per source and bucket, against the configured limits.

    Every API key slot is listed, and the connected channel; a source with no
    requests today reads 0, which is a count, not a guess. When the ledger
    cannot be read, ``available`` is false and no source is listed.
    """
    moment = now or datetime.now(timezone.utc)
    day = quota_date(moment)
    search_limit, unit_limit = settings.youtube_search_calls_per_day, settings.youtube_units_per_day
    status: dict[str, Any] = {
        "available": False,
        "quota_date": day.isoformat(),
        "resets_at": next_reset(moment).isoformat(),
        "limits": {"search_calls_per_day": search_limit, "units_per_day": unit_limit},
        "sources": [],
        "warnings": [],
    }
    try:
        usage = QuotaLedger(settings.database_path).usage(day)
    except Exception as exc:  # noqa: BLE001 - reported as unavailable, never as zero
        logger.warning("YouTube quota usage could not be read: %s", type(exc).__name__)
        return status
    names = [api_key_source(slot) for slot in range(1, len(settings.youtube_api_key_pool) + 1)]
    if oauth_connected:
        names.append(OAUTH_SOURCE)
    # A key removed from the pool today, or a channel since disconnected.
    names += sorted({source for source, _ in usage} - set(names))
    sources = [_source_usage(name, usage, search_limit, unit_limit) for name in names]
    return {**status, "available": True, "sources": sources, "warnings": _warnings(sources)}


def quota_warnings(settings: Settings, *, now: datetime | None = None) -> list[str]:
    """Warnings for the API keys' buckets at 90% or more of their configured daily limit."""
    sources = quota_status(settings, now=now)["sources"]
    return _warnings([item for item in sources if item["source"] != OAUTH_SOURCE])
