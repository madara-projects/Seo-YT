"""Quota-safe, opt-in scheduled collection of named owned-video snapshots."""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any

from google.auth.exceptions import RefreshError

from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore

logger = logging.getLogger(__name__)


class SnapshotCollector:
    """Single-process collector. Disabled by default and safe to call in tests."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stop = threading.Event()
        self._run_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "state": "disabled" if not settings.snapshot_collector_enabled else "waiting",
            "enabled": bool(settings.snapshot_collector_enabled),
            "dry_run": bool(settings.snapshot_collector_dry_run),
            "running": False,
            "last_started_at": None,
            "last_finished_at": None,
            "next_run_at": None,
            "last_error": None,
            "last_plan": [],
            "last_counts": {
                "links": 0, "windows": 0, "captured": 0, "traffic_sources": 0, "failed": 0,
                "traffic_backfill": 0, "traffic_failed": 0,
            },
        }

    def start(self) -> None:
        if not self.settings.snapshot_collector_enabled:
            return
        if self._thread and self._thread.is_alive() and not self._stop.is_set():
            return
        # Each loop has its own stop signal. One told to stop may still be
        # finishing a run; it ends after that, and this one takes over.
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, args=(self._stop,), name="snapshot-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            # A run in progress finishes its current YouTube call first.
            thread.join(timeout=15)
            if thread.is_alive():
                logger.warning("snapshot collector is still finishing a run at shutdown")

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def run_once(self) -> dict[str, Any]:
        if not self.settings.snapshot_collector_enabled:
            self._status["state"] = "disabled"
            return {"state": "disabled", "planned": [], "counts": self._status["last_counts"]}
        if not self._run_lock.acquire(blocking=False):
            return {"state": "running", "planned": [], "counts": self._status["last_counts"]}
        started = datetime.now(timezone.utc).isoformat()
        self._status.update({"state": "running", "running": True, "last_started_at": started, "last_error": None})
        try:
            store = HistoryStore(self.settings.database_path)
            from win_engine.integrations.youtube_channel import LinkUnavailable, YouTubeChannelService, YouTubeUnavailable
            service = YouTubeChannelService(self.settings)
            channel_status = service.status()
            channel_id = str((channel_status.get("channel") or {}).get("id") or "")
            cooldown = max(0, int(self.settings.snapshot_collector_retry_base_seconds))
            # Only the connected channel's videos: another channel's, verified
            # on another device, cannot be collected through this connection.
            due = store.due_snapshot_links(
                retry_cooldown_seconds=cooldown,
                retry_max_seconds=int(self.settings.snapshot_collector_retry_max_seconds),
                channel_id=channel_id or None,
            )
            selected = due[: max(1, int(self.settings.snapshot_collector_max_links_per_run))]
            plan = [{"link_id": item["id"], "video_id": item["youtube_video_id"], "windows": item["due_windows"], "age_hours": item["age_hours"]} for item in selected]
            # Each captured window also asks for its traffic sources, after its
            # metrics are saved; `traffic_sources` counts the windows that got a
            # breakdown in this run, `traffic_backfill` the completed windows
            # asked again, and `traffic_failed` the requests refused or failed.
            counts = {
                "links": len(selected), "windows": sum(len(item["due_windows"]) for item in selected),
                "captured": 0, "traffic_sources": 0, "failed": 0, "traffic_backfill": 0, "traffic_failed": 0,
            }
            self._status["last_plan"] = plan
            self._status["last_counts"] = counts
            if self.settings.snapshot_collector_dry_run:
                self._status["state"] = "dry-run"
                return {"state": "dry-run", "planned": plan, "counts": counts}
            # Ownership is checked against the channel id, so a connection whose
            # channel is not identified yet cannot collect anything.
            if not channel_status.get("configured") or not channel_id:
                self._status["state"] = "unconfigured"
                return {"state": "unconfigured", "planned": plan, "counts": counts}
            traffic_errors: list[str] = []
            stopped = False
            for item in selected:
                try:
                    result = service.refresh_linked_video_performance(
                        item, force=False, collect_current=False, windows=item["due_windows"]
                    )
                    captured = result.get("captured") or []
                    # The link's own completed windows that the refresh asked again.
                    self._add_traffic_backfill(counts, result.get("traffic_backfill") or {}, traffic_errors)
                    counts["captured"] += len(captured)
                    counts["traffic_sources"] += sum(1 for snapshot in captured if snapshot.get("traffic_sources"))
                    counts["traffic_failed"] += sum(
                        1 for snapshot in captured if snapshot.get("traffic_status") in {"refused", "failed"}
                    )
                    traffic_errors += [
                        "traffic_sources_unexpected_error" for snapshot in captured
                        if snapshot.get("traffic_last_failure_reason") == "unexpected_error"
                    ]
                except LinkUnavailable:
                    # The link is marked failed and leaves the plan; the others go on.
                    counts["failed"] += 1
                    logger.warning("snapshot collector link=%s is no longer collectable", item["id"])
                except YouTubeUnavailable as exc:
                    # An outage or an exhausted quota is not this video's fault
                    # and every remaining link would fail the same way: the run
                    # stops, and the next one tries again without an attempt spent.
                    counts["failed"] += 1
                    self._postpone(store, item, "youtube_unavailable")
                    self._status["last_error"] = "quota_exhausted" if exc.status_code == 429 else "youtube_unavailable"
                    logger.warning("snapshot collector stopped: YouTube unavailable (HTTP %s)", exc.status_code)
                    stopped = True
                    break
                except (ValueError, RefreshError) as exc:
                    # Not about this link (a revoked grant, an unreadable token):
                    # the rest would fail too, so stop until it is fixed.
                    counts["failed"] += 1
                    self._status["last_error"] = type(exc).__name__
                    logger.warning("snapshot collector stopped: %s", type(exc).__name__)
                    stopped = True
                    break
                except Exception as exc:
                    # A bug is not the video's fault either. Its link goes behind
                    # the others, so one broken link cannot stop every run.
                    counts["failed"] += 1
                    self._postpone(store, item, "unexpected_error")
                    self._status["last_error"] = type(exc).__name__
                    logger.exception("snapshot collector stopped at link=%s: %s", item["id"], type(exc).__name__)
                    stopped = True
                    break
            if not stopped:
                self._backfill_traffic(service, counts, traffic_errors)
            # A bug in a breakdown request leaves the windows' metrics alone,
            # but it is reported here as well as logged, never passed over.
            if traffic_errors and not self._status.get("last_error"):
                self._status["last_error"] = traffic_errors[0]
            self._status["last_counts"] = counts
            self._status["state"] = "cooldown" if counts["failed"] else "healthy/idle"
            return {"state": self._status["state"], "planned": plan, "counts": counts}
        except Exception as exc:
            self._status.update({"state": "error", "last_error": type(exc).__name__})
            logger.exception("snapshot collector run failed: %s", type(exc).__name__)
            return {"state": "error", "planned": self._status.get("last_plan", []), "counts": self._status["last_counts"]}
        finally:
            self._status.update({"running": False, "last_finished_at": datetime.now(timezone.utc).isoformat()})
            self._run_lock.release()

    def _backfill_traffic(self, service: Any, counts: dict[str, Any], errors: list[str]) -> None:
        """Ask again for the traffic sources of completed windows that lack them.

        Windows captured before traffic outcomes were recorded, and those whose
        request failed, are taken a few per run, each within its attempts and
        backoff; a refused one waits for the channel to be connected again. A
        failure here never touches a window's metrics; it is logged and noted.
        """
        from win_engine.integrations.youtube_channel import YouTubeUnavailable
        # As many windows as the run's links could have captured.
        limit = max(1, int(self.settings.snapshot_collector_max_links_per_run)) * 3
        try:
            done = service.backfill_traffic_sources(limit=limit)
        except YouTubeUnavailable as exc:
            errors.append("traffic_sources_youtube_unavailable")
            logger.warning("snapshot collector traffic-source pass stopped: YouTube unavailable (HTTP %s)", exc.status_code)
            return
        except (ValueError, RefreshError) as exc:
            errors.append(f"traffic_sources_{type(exc).__name__}")
            logger.warning("snapshot collector traffic-source pass stopped: %s", type(exc).__name__)
            return
        except Exception as exc:
            errors.append("traffic_sources_unexpected_error")
            logger.exception("snapshot collector traffic-source pass failed: %s", type(exc).__name__)
            return
        self._add_traffic_backfill(counts, done, errors)

    @staticmethod
    def _add_traffic_backfill(counts: dict[str, Any], done: dict[str, Any], errors: list[str]) -> None:
        """Add one backfill pass's outcomes (YouTubeChannelService counts) to the run's counts."""
        counts["traffic_backfill"] += int(done.get("windows") or 0)
        counts["traffic_sources"] += int(done.get("ok") or 0)
        counts["traffic_failed"] += int(done.get("refused") or 0) + int(done.get("failed") or 0)
        if done.get("unexpected"):
            errors.append("traffic_sources_unexpected_error")

    @staticmethod
    def _postpone(store: HistoryStore, item: dict[str, Any], reason: str) -> None:
        """Note the try without spending an attempt, so the link cools down and goes last."""
        for window in item["due_windows"]:
            try:
                store.postpone_snapshot_window(
                    item["youtube_video_id"], window, failure_reason=reason, age_hours=float(item.get("age_hours") or 0),
                )
            except Exception as exc:
                logger.warning("snapshot collector could not record a failed try: %s", type(exc).__name__)

    def _loop(self, stop: threading.Event) -> None:
        if stop.wait(max(0, int(self.settings.snapshot_collector_initial_delay_seconds))):
            return
        while not stop.is_set():
            self.run_once()
            # A little jitter keeps runs from lining up with other periodic work.
            delay = max(60, int(self.settings.snapshot_collector_interval_seconds)) * random.uniform(0.9, 1.1)
            self._status["next_run_at"] = datetime.fromtimestamp(time.time() + delay, timezone.utc).isoformat()
            if stop.wait(delay):
                return
