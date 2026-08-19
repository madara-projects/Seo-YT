"""Quota-safe, opt-in scheduled collection of named owned-video snapshots."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

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
            "last_counts": {"links": 0, "windows": 0, "captured": 0, "failed": 0},
        }

    def start(self) -> None:
        if not self.settings.snapshot_collector_enabled or self._thread:
            return
        self._thread = threading.Thread(target=self._loop, name="snapshot-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

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
            cooldown = max(0, int(self.settings.snapshot_collector_retry_base_seconds))
            due = store.due_snapshot_links(
                retry_cooldown_seconds=cooldown,
                retry_max_seconds=int(self.settings.snapshot_collector_retry_max_seconds),
            )
            selected = due[: max(1, int(self.settings.snapshot_collector_max_links_per_run))]
            plan = [{"link_id": item["id"], "video_id": item["youtube_video_id"], "windows": item["due_windows"], "age_hours": item["age_hours"]} for item in selected]
            counts = {"links": len(selected), "windows": sum(len(item["due_windows"]) for item in selected), "captured": 0, "failed": 0}
            self._status["last_plan"] = plan
            self._status["last_counts"] = counts
            if self.settings.snapshot_collector_dry_run:
                self._status["state"] = "dry-run"
                return {"state": "dry-run", "planned": plan, "counts": counts}
            from win_engine.integrations.youtube_channel import YouTubeChannelService
            service = YouTubeChannelService(self.settings)
            channel_status = service.status()
            if not channel_status.get("configured") or not channel_status.get("connected"):
                self._status["state"] = "unconfigured"
                return {"state": "unconfigured", "planned": plan, "counts": counts}
            if not selected:
                self._status["state"] = "healthy/idle"
                return {"state": "healthy/idle", "planned": [], "counts": counts}

            for item in selected:
                try:
                    result = service.refresh_linked_video_performance(
                        item, force=False, collect_current=False
                    )
                    counts["captured"] += len(result.get("captured") or [])
                except ValueError as exc:
                    counts["failed"] += 1
                    logger.warning("snapshot collector link=%s failed: %s", item["id"], type(exc).__name__)
                except Exception as exc:
                    counts["failed"] += 1
                    logger.exception("snapshot collector link=%s failed: %s", item["id"], type(exc).__name__)
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

    def _loop(self) -> None:
        if self._stop.wait(max(0, int(self.settings.snapshot_collector_initial_delay_seconds))):
            return
        while not self._stop.is_set():
            self.run_once()
            next_run = time.time() + max(60, int(self.settings.snapshot_collector_interval_seconds))
            self._status["next_run_at"] = datetime.fromtimestamp(next_run, timezone.utc).isoformat()
            if self._stop.wait(max(60, int(self.settings.snapshot_collector_interval_seconds))):
                return
