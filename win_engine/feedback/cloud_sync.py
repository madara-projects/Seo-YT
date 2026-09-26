"""Offline-first synchronization of saved History packages through Aiven MySQL.

Each package travels as one JSON payload under a stable sync UUID. The higher
revision wins, equal revisions go to the greater content hash, and a deletion
wins over any edit, on the cloud and on every device alike.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from win_engine.core.config import Settings
from win_engine.feedback.history_store import DatabaseUnavailable, HistoryStore, comparable_format
from win_engine.feedback.migrations import connect_managed

logger = logging.getLogger(__name__)

# updated_at comes from each device's own clock, and a slow commit can land
# behind rows a pull already read, so an incremental pull starts this far
# before the newest row it has applied.
_PULL_OVERLAP = timedelta(minutes=10)
# A periodic full pull picks up rows from a device whose clock lags by more
# than the overlap.
_FULL_PULL_SECONDS = 3600
# Driver codes for a session that is gone, after which every row would fail.
_CONNECTION_LOST_CODES = frozenset({2003, 2006, 2013, 2055})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _tombstone_hash(sync_uuid: str, revision: int, deleted_at: str) -> str:
    return _hash({"schema": 1, "deleted": True, "sync_uuid": sync_uuid, "revision": int(revision), "deleted_at": deleted_at})


def _connection_lost(exc: BaseException) -> bool:
    """Whether a driver error ended the session rather than failing one row."""
    try:
        from pymysql import err
    except ImportError:
        return False
    if isinstance(exc, err.InterfaceError):
        return True
    return isinstance(exc, err.OperationalError) and bool(exc.args) and exc.args[0] in _CONNECTION_LOST_CODES


@contextmanager
def _savepoint(connection, name: str) -> Iterator[None]:
    """Undo only this block when it fails; the enclosing transaction goes on."""
    connection.execute(f"SAVEPOINT {name}")
    try:
        yield
    except BaseException:
        connection.execute(f"ROLLBACK TO {name}")
        connection.execute(f"RELEASE {name}")
        raise
    connection.execute(f"RELEASE {name}")


class CloudSyncConfigError(RuntimeError):
    """A local configuration problem. Its message names no credentials or
    endpoints, so unlike a driver error it is safe to show in Settings."""


def _validated_ca_path(configured: str | None) -> Path:
    """The CA certificate for the TLS connection, checked before any network use."""
    ca = Path(str(configured or ""))
    if not ca.is_file():
        raise CloudSyncConfigError(
            f"CA certificate not found at {ca} inside the container; "
            "check WIN_ENGINE_CLOUD_SYNC_SSL_CA_PATH against the volume mount."
        )
    try:
        text = ca.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CloudSyncConfigError(f"CA certificate at {ca} could not be read.") from exc
    if "-----BEGIN CERTIFICATE-----" not in text:
        raise CloudSyncConfigError(f"CA certificate at {ca} is empty or is not a PEM certificate.")
    return ca


class CloudSyncService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stop = threading.Event()
        # Cuts the loop's wait short: a requested run, a new schedule or stop().
        self._wake = threading.Event()
        self._run_requested = False
        self._next_run = 0.0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "state": "disabled" if not settings.cloud_sync_enabled else "waiting",
            "enabled": bool(settings.cloud_sync_enabled), "running": False,
            "device_id": settings.cloud_sync_device_id or "unconfigured",
            "last_started_at": None, "last_finished_at": None, "next_run_at": None,
            "last_error": None,
            "last_counts": {"queued": 0, "pushed": 0, "pulled": 0, "failed": 0, "conflicts": 0, "skipped": 0},
            "last_activity_at": None,
            "last_activity_counts": {"queued": 0, "pushed": 0, "pulled": 0},
            "remote_packages": None,
            "consecutive_failures": 0, "retry_delay_seconds": None,
        }
        self._last_push_failures = 0
        self._last_pull_conflicts = 0
        self._last_pull_skipped = 0
        # Runs in a row that could not complete; drives the retry backoff.
        self._consecutive_failures = 0
        # The cloud table is checked once per process, and again after a failed run.
        self._remote_schema_ready = False
        # The newest cloud updated_at applied so far; None until a full pull.
        self._pull_watermark: str | None = None
        self._last_full_pull = 0.0
        self._full_pull_needed = False

    def configured(self) -> bool:
        s = self.settings
        return bool(s.cloud_sync_host and s.cloud_sync_database and s.cloud_sync_user and s.cloud_sync_password and s.cloud_sync_device_id)

    def start(self) -> None:
        if not self.settings.cloud_sync_enabled:
            return
        if self._thread is not None and self._thread.is_alive() and not self._stop.is_set():
            return
        # Each loop has its own stop signal. One told to stop may still be
        # finishing a run, or past its last look at the signal; it ends by
        # itself and this one takes over, so a restart always leaves a loop.
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, args=(self._stop,), name="cloud-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3)
        # A run in progress cannot be interrupted; the loop ends after it. Runs
        # never overlap, even with a new loop started meanwhile: each holds _lock.
        if thread is not None and not thread.is_alive():
            self._thread = None

    def request_run(self) -> dict[str, Any]:
        """Ask the background thread to run soon and return the status at once.

        Request handlers use this instead of run_once(), so a push and pull to
        the cloud never holds up their response. Without a running thread
        nothing is scheduled and only the status comes back.
        """
        requested = self._loop_alive()
        if requested:
            self._run_requested = True
            self._wake.set()
        result = self.status()
        result["run_requested"] = requested
        return result

    def status(self) -> dict[str, Any]:
        result = dict(self._status)
        try:
            with connect_managed(self.settings.database_path) as connection:
                pending_packages = int(connection.execute("SELECT COUNT(*) FROM cloud_sync_outbox").fetchone()[0])
                pending_deletions = int(connection.execute("SELECT COUNT(*) FROM cloud_sync_tombstones WHERE pending = 1").fetchone()[0])
                result["pending_uploads"] = pending_packages + pending_deletions
                result["pending_deletions"] = pending_deletions
                result["local_packages"] = int(connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0])
                result["mapped_packages"] = int(connection.execute("SELECT COUNT(*) FROM cloud_sync_packages").fetchone()[0])
                result["synced_packages"] = int(connection.execute("SELECT COUNT(*) FROM cloud_sync_packages WHERE last_synced_hash IS NOT NULL").fetchone()[0])
                result["conflicts_detected"] = int(connection.execute("SELECT COUNT(*) FROM cloud_sync_conflicts").fetchone()[0])
        except Exception as exc:
            logger.warning("Cloud sync status could not read the local database: %s", type(exc).__name__)
            result["pending_uploads"] = None
            result["pending_deletions"] = None
            result["local_packages"] = None
            result["mapped_packages"] = None
            result["synced_packages"] = None
            result["conflicts_detected"] = None
        result["configured"] = self.configured()
        return result

    def run_once(self) -> dict[str, Any]:
        result = self._run(blocking=False)
        if result["state"] != "running" and self._loop_alive():
            # The next scheduled run counts from this one, so a manual run that
            # reaches the cloud also ends a long backoff wait.
            self._schedule()
        return result

    def _run(self, *, blocking: bool) -> dict[str, Any]:
        if not self.settings.cloud_sync_enabled:
            return {"state": "disabled", "counts": self._status["last_counts"]}
        if not self.configured():
            self._status["state"] = "unconfigured"
            return {"state": "unconfigured", "counts": self._status["last_counts"]}
        if not self._lock.acquire(blocking=blocking):
            return {"state": "running", "counts": self._status["last_counts"]}
        counts = {"queued": 0, "pushed": 0, "pulled": 0, "failed": 0, "conflicts": 0, "skipped": 0}
        self._status.update({"state": "running", "running": True, "last_started_at": _now(), "last_error": None})
        try:
            # The database is prepared (migrated) before this thread touches it;
            # until it can be, the run fails like an outage and backs off.
            HistoryStore(self.settings.database_path)
            counts["queued"] = self._stage_local_packages()
            remote = self._remote_connection()
            try:
                if not self._remote_schema_ready:
                    self._ensure_remote_schema(remote)
                    self._remote_schema_ready = True
                counts["pushed"] = self._push(remote)
                counts["failed"] += self._last_push_failures
                counts["pulled"] = self._pull(remote, since=self._pull_since())
                counts["conflicts"] = self._last_pull_conflicts
                counts["skipped"] = self._last_pull_skipped
                with remote.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM seo_yt_synced_packages WHERE deleted_at IS NULL")
                    self._status["remote_packages"] = int(cursor.fetchone()[0])
            finally:
                remote.close()
            # The run reached the cloud, so any outage is over even if a
            # single package still failed; that one retries on the normal cycle.
            self._consecutive_failures = 0
            if counts["failed"]:
                self._status.update({"state": "offline/pending", "last_error": "One or more sync operations remain pending."})
            else:
                self._status["state"] = "healthy/idle"
        except Exception as exc:
            counts["failed"] += 1
            self._consecutive_failures += 1
            self._remote_schema_ready = False
            # Error details from database drivers can contain endpoint or
            # account information, so for those only the class name is kept. A
            # local configuration problem describes itself in a safe message.
            reason = str(exc) if isinstance(exc, CloudSyncConfigError) else type(exc).__name__
            self._status.update({"state": "offline/pending", "last_error": reason})
            logger.warning("Cloud package sync remains pending: %s", reason)
            try:
                if not isinstance(exc, DatabaseUnavailable):
                    self._mark_all_pending_failures(type(exc).__name__)
            except Exception as mark_exc:
                # A locked or failing local database must not also end the sync thread.
                logger.warning("Cloud sync could not record the failed attempt locally: %s", type(mark_exc).__name__)
        finally:
            if counts["queued"] or counts["pushed"] or counts["pulled"]:
                self._status["last_activity_at"] = _now()
                self._status["last_activity_counts"] = {
                    "queued": counts["queued"], "pushed": counts["pushed"], "pulled": counts["pulled"]
                }
            self._status.update({"running": False, "last_finished_at": _now(), "last_counts": counts,
                                 "consecutive_failures": self._consecutive_failures})
            self._lock.release()
        return {"state": self._status["state"], "counts": counts}

    def _package_payload(self, connection, run_id: int) -> dict[str, Any] | None:
        row = connection.execute(
            """SELECT query, created_at, intent, content_angle, title, title_score,
                      retention_risk, opportunity_label, opportunity_score, payload_json
               FROM analysis_runs WHERE id = ?""", (run_id,),
        ).fetchone()
        if row is None:
            return None
        selection = connection.execute(
            """SELECT generated_package_id, package_json, quality_gate_json, selection_source,
                      selected_at, updated_at FROM analysis_package_selections WHERE analysis_run_id = ?""",
            (run_id,),
        ).fetchone()
        link = connection.execute(
            """SELECT id,youtube_video_id,published_at,selected_title,selected_thumbnail_package,
                      selected_description,selected_tags_json,selected_hashtags_json,format,language,
                      region,notes,linked_at,updated_at,youtube_metadata_json,metadata_synced_at,
                      ownership_state,ownership_verified,verified_channel_id,ownership_verified_at
               FROM published_video_links WHERE analysis_run_id = ?""", (run_id,),
        ).fetchone()
        linked_video = None
        if link:
            comparable = connection.execute(
                """SELECT language,format,duration_bucket,topic_category,language_source,format_source,
                          duration_bucket_source,topic_category_source,updated_at
                   FROM published_video_comparable_metadata WHERE published_video_link_id = ?""", (link[0],),
            ).fetchone()
            snapshot_rows = connection.execute(
                """SELECT age_hours,views,watch_time_minutes,avg_view_duration_seconds,avg_view_percentage,
                          likes,comments,shares,subscribers_gained,impressions,impressions_ctr,snapshot_window,
                          snapshot_status,attempt_count,last_failure_reason,last_attempted_at,completed_at,
                          source_start_date,source_end_date,captured_at
                   FROM video_performance_snapshots WHERE youtube_video_id = ? ORDER BY captured_at,id""", (link[1],),
            ).fetchall()
            keys = ("age_hours", "views", "watch_time_minutes", "avg_view_duration_seconds", "avg_view_percentage",
                    "likes", "comments", "shares", "subscribers_gained", "impressions", "impressions_ctr",
                    "snapshot_window", "snapshot_status", "attempt_count", "last_failure_reason", "last_attempted_at",
                    "completed_at", "source_start_date", "source_end_date", "captured_at")
            linked_video = {
                "youtube_video_id": link[1], "published_at": link[2], "selected_title": link[3],
                "selected_thumbnail_package": link[4], "selected_description": link[5],
                "selected_tags": json.loads(link[6]) if link[6] else [],
                "selected_hashtags": json.loads(link[7]) if link[7] else [], "format": link[8],
                "language": link[9], "region": link[10], "notes": link[11], "linked_at": link[12],
                "updated_at": link[13], "youtube_metadata": json.loads(link[14]) if link[14] else None,
                "metadata_synced_at": link[15], "ownership_state": link[16],
                "ownership_verified": bool(link[17]), "verified_channel_id": link[18],
                "ownership_verified_at": link[19],
                "comparable_metadata": ({"language": comparable[0], "format": comparable[1],
                    "duration_bucket": comparable[2], "topic_category": comparable[3],
                    "sources": {"language": comparable[4], "format": comparable[5],
                                "duration_bucket": comparable[6], "topic_category": comparable[7]},
                    "updated_at": comparable[8]} if comparable else None),
                "snapshots": [dict(zip(keys, row)) for row in snapshot_rows],
            }
        return {
            "schema": 2,
            "analysis": {"query": row[0], "created_at": row[1], "intent": row[2], "content_angle": row[3],
                         "title": row[4], "title_score": row[5], "retention_risk": row[6],
                         "opportunity_label": row[7], "opportunity_score": row[8],
                         "package": json.loads(row[9]) if row[9] else None},
            "selection": ({"generated_package_id": selection[0], "package": json.loads(selection[1]),
                          "quality_gate": json.loads(selection[2]) if selection[2] else {},
                           "selection_source": selection[3], "selected_at": selection[4], "updated_at": selection[5]}
                          if selection else None),
            "linked_video": linked_video,
        }

    def _stage_local_packages(self) -> int:
        queued = 0
        device = str(self.settings.cloud_sync_device_id)
        with connect_managed(self.settings.database_path) as connection:
            run_ids = [int(row[0]) for row in connection.execute("SELECT id FROM analysis_runs ORDER BY id").fetchall()]
            for run_id in run_ids:
                mapping = connection.execute(
                    """SELECT p.sync_uuid, p.revision, p.content_hash, p.last_synced_hash, o.sync_uuid IS NOT NULL
                       FROM cloud_sync_packages p LEFT JOIN cloud_sync_outbox o ON o.sync_uuid = p.sync_uuid
                       WHERE p.analysis_run_id = ?""", (run_id,)
                ).fetchone()
                payload = self._package_payload(connection, run_id)
                if payload is None:
                    continue  # deleted after the ids were listed
                content_hash = _hash(payload)
                # A pulled package can keep observations its cloud version lacks
                # (a completed window, a newer display snapshot), so it is also
                # compared with what the pull stored, not only with the version.
                if mapping and (content_hash == str(mapping[2]) or (not mapping[4] and content_hash == mapping[3])):
                    continue
                now = _now()
                sync_uuid = str(mapping[0]) if mapping else str(uuid.uuid4())
                revision = (int(mapping[1]) + 1) if mapping else 1
                try:
                    if mapping:
                        connection.execute("UPDATE cloud_sync_packages SET revision=?, content_hash=?, updated_at=? WHERE sync_uuid=?", (revision, content_hash, now, sync_uuid))
                    else:
                        connection.execute(
                            "INSERT INTO cloud_sync_packages(sync_uuid,analysis_run_id,origin_device_id,revision,content_hash,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                            (sync_uuid, run_id, device, revision, content_hash, now, now),
                        )
                    connection.execute(
                        """INSERT INTO cloud_sync_outbox(sync_uuid,revision,payload_json,content_hash,queued_at)
                           VALUES(?,?,?,?,?) ON CONFLICT(sync_uuid) DO UPDATE SET revision=excluded.revision,
                           payload_json=excluded.payload_json,content_hash=excluded.content_hash,queued_at=excluded.queued_at,last_error=NULL""",
                        (sync_uuid, revision, json.dumps(payload, ensure_ascii=False), content_hash, now),
                    )
                    # One package at a time keeps SQLite's write lock short.
                    connection.commit()
                except sqlite3.IntegrityError:
                    # The package was deleted while it was being staged.
                    connection.rollback()
                    continue
                queued += 1
        return queued

    def _remote_connection(self):
        import pymysql
        ca = _validated_ca_path(self.settings.cloud_sync_ssl_ca_path)
        return pymysql.connect(host=self.settings.cloud_sync_host, port=self.settings.cloud_sync_port,
            user=self.settings.cloud_sync_user, password=self.settings.cloud_sync_password,
            database=self.settings.cloud_sync_database, charset="utf8mb4", autocommit=False,
            connect_timeout=10, read_timeout=20, write_timeout=20,
            ssl={"ca": str(ca), "check_hostname": True})

    def _mark_all_pending_failures(self, error_type: str) -> None:
        """Persist a retry marker without storing cloud connection details."""
        now = _now()
        with connect_managed(self.settings.database_path) as local:
            local.execute(
                """UPDATE cloud_sync_outbox
                   SET attempt_count = attempt_count + 1, last_attempted_at = ?, last_error = ?""",
                (now, error_type),
            )
            local.execute(
                """UPDATE cloud_sync_tombstones
                   SET attempt_count = attempt_count + 1, last_attempted_at = ?, last_error = ?
                   WHERE pending = 1""",
                (now, error_type),
            )

    @staticmethod
    def _record_conflict(local, *, sync_uuid: str, local_revision: int, local_hash: str,
                         remote_revision: int, remote_hash: str, winner: str) -> None:
        # An edit made here that loses is kept with the record, so it can be recovered.
        queued = None if winner == "local" else local.execute(
            "SELECT payload_json FROM cloud_sync_outbox WHERE sync_uuid = ?", (sync_uuid,)
        ).fetchone()
        local.execute(
            """INSERT OR IGNORE INTO cloud_sync_conflicts
                   (sync_uuid,local_revision,local_content_hash,remote_revision,remote_content_hash,winner,detected_at,
                    local_payload_json)
               VALUES(?,?,?,?,?,?,?,?)""",
            (sync_uuid, local_revision, local_hash, remote_revision, remote_hash, winner, _now(),
             queued[0] if queued else None),
        )

    @staticmethod
    def _remote_active_wins(*, local_hash: str, remote_hash: str) -> bool:
        """Resolve two different versions with the same revision.

        A higher revision always wins, before this is asked. Equal revisions
        go to the lexicographically greater SHA-256 payload hash, the same rule
        the cloud upsert applies, so every device converges without wall-clock
        dependence. Deletions are handled separately and win over any active
        version.
        """
        return remote_hash > local_hash

    @staticmethod
    def _ensure_remote_schema(connection) -> None:
        with connection.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS seo_yt_synced_packages (
                sync_uuid CHAR(36) PRIMARY KEY, origin_device_id VARCHAR(120) NOT NULL,
                revision INT NOT NULL, content_hash CHAR(64) NOT NULL, payload_json LONGTEXT NOT NULL,
                created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL, deleted_at VARCHAR(40) NULL,
                INDEX idx_synced_updated(updated_at)) CHARACTER SET utf8mb4""")
            cursor.execute("SHOW COLUMNS FROM seo_yt_synced_packages LIKE 'deleted_at'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE seo_yt_synced_packages ADD COLUMN deleted_at VARCHAR(40) NULL AFTER updated_at")
        connection.commit()

    @staticmethod
    def _abandon_row(remote, exc: Exception, sync_uuid: str) -> None:
        """Roll back one failed row, or re-raise when the session itself is gone."""
        if _connection_lost(exc):
            raise exc
        try:
            remote.rollback()
        except Exception as rollback_error:
            # Every later row would fail on the same broken session.
            raise exc from rollback_error
        logger.warning("Cloud sync could not push package %s: %s", sync_uuid[:8], type(exc).__name__)

    @staticmethod
    def _remote_holds(cursor, sync_uuid: str, content_hash: str) -> bool:
        """Whether the cloud row is this active version, e.g. from an earlier push."""
        cursor.execute("SELECT content_hash,deleted_at FROM seo_yt_synced_packages WHERE sync_uuid=%s", (sync_uuid,))
        row = cursor.fetchone()
        return bool(row) and row[1] is None and str(row[0]) == content_hash

    def _push(self, remote) -> int:
        """Push each durable operation independently so one failure does not block peers.

        Each row's local bookkeeping is committed straight after its cloud
        write, so SQLite's write lock is never held while waiting on the network.
        """
        self._last_push_failures = 0
        pushed = 0
        device = str(self.settings.cloud_sync_device_id)
        with connect_managed(self.settings.database_path) as local:
            deletion_rows = local.execute(
                """SELECT sync_uuid,revision,deleted_at FROM cloud_sync_tombstones
                   WHERE pending = 1 ORDER BY deleted_at LIMIT 100"""
            ).fetchall()
            # A video moved between packages leaves one package without its link
            # and gives it to another, which may then be deleted. Packages that
            # carry a link go first and deletions last, so a device pulling
            # between these rows moves the link instead of deleting it together
            # with the evidence collected for it.
            package_rows = local.execute(
                """SELECT sync_uuid,revision,payload_json,content_hash,last_error FROM cloud_sync_outbox
                   ORDER BY (CASE WHEN json_valid(payload_json) THEN json_type(payload_json,'$.linked_video') END IS 'object') DESC,
                            queued_at
                   LIMIT 100"""
            ).fetchall()
            for sync_uuid, revision, payload_json, content_hash, last_error in package_rows:
                now = _now()
                try:
                    with remote.cursor() as cursor:
                        affected = cursor.execute("""INSERT INTO seo_yt_synced_packages
                            (sync_uuid,origin_device_id,revision,content_hash,payload_json,created_at,updated_at,deleted_at)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,NULL) ON DUPLICATE KEY UPDATE
                            payload_json=IF(deleted_at IS NULL AND (VALUES(revision)>revision OR
                                (VALUES(revision)=revision AND VALUES(content_hash)>content_hash)),VALUES(payload_json),payload_json),
                            updated_at=IF(deleted_at IS NULL AND (VALUES(revision)>revision OR
                                (VALUES(revision)=revision AND VALUES(content_hash)>content_hash)),VALUES(updated_at),updated_at),
                            origin_device_id=IF(deleted_at IS NULL AND (VALUES(revision)>revision OR
                                (VALUES(revision)=revision AND VALUES(content_hash)>content_hash)),VALUES(origin_device_id),origin_device_id),
                            content_hash=IF(deleted_at IS NULL AND (VALUES(revision)>revision OR
                                (VALUES(revision)=revision AND VALUES(content_hash)>content_hash)),VALUES(content_hash),content_hash),
                            revision=IF(deleted_at IS NULL,GREATEST(revision,VALUES(revision)),revision)""",
                            (sync_uuid, device, revision, content_hash, payload_json, now, now))
                        # MySQL reports 1 for an insert, 2 for an update and 0 when
                        # the row kept its values: either this exact version was
                        # already there, or the cloud kept another one.
                        landed = affected != 0 or self._remote_holds(cursor, sync_uuid, content_hash)
                    remote.commit()
                except Exception as exc:
                    self._abandon_row(remote, exc, sync_uuid)
                    local.execute(
                        """UPDATE cloud_sync_outbox SET attempt_count = attempt_count + 1,
                                      last_attempted_at = ?, last_error = ? WHERE sync_uuid = ?""",
                        (now, type(exc).__name__, sync_uuid),
                    )
                    local.commit()
                    self._last_push_failures += 1
                    continue
                if not landed:
                    # A later edit or a deletion from another device won in the
                    # cloud. The row stays queued until the pull applies the
                    # winner and records the conflict; a full pull makes sure
                    # it sees that row the first time this happens.
                    if last_error != "superseded":
                        self._full_pull_needed = True
                    local.execute(
                        """UPDATE cloud_sync_outbox SET attempt_count = attempt_count + 1,
                                      last_attempted_at = ?, last_error = 'superseded' WHERE sync_uuid = ?""",
                        (now, sync_uuid),
                    )
                    local.commit()
                    continue
                local.execute("UPDATE cloud_sync_packages SET last_synced_hash=?,remote_updated_at=? WHERE sync_uuid=?", (content_hash, now, sync_uuid))
                local.execute("DELETE FROM cloud_sync_outbox WHERE sync_uuid=? AND content_hash=?", (sync_uuid, content_hash))
                local.commit()
                pushed += 1
            for sync_uuid, revision, deleted_at in deletion_rows:
                now = _now()
                try:
                    with remote.cursor() as cursor:
                        # A deletion wins over any active version, as it does on
                        # every device; a row that is already deleted stays as it is.
                        cursor.execute("""INSERT INTO seo_yt_synced_packages
                            (sync_uuid,origin_device_id,revision,content_hash,payload_json,created_at,updated_at,deleted_at)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE
                            payload_json=IF(deleted_at IS NULL,VALUES(payload_json),payload_json),
                            updated_at=IF(deleted_at IS NULL,VALUES(updated_at),updated_at),
                            origin_device_id=IF(deleted_at IS NULL,VALUES(origin_device_id),origin_device_id),
                            content_hash=IF(deleted_at IS NULL,VALUES(content_hash),content_hash),
                            revision=IF(deleted_at IS NULL,GREATEST(revision,VALUES(revision)),revision),
                            deleted_at=COALESCE(deleted_at,VALUES(deleted_at))""",
                            (sync_uuid, device, revision, _tombstone_hash(sync_uuid, revision, deleted_at),
                             "{}", now, now, deleted_at))
                    remote.commit()
                except Exception as exc:
                    self._abandon_row(remote, exc, sync_uuid)
                    local.execute(
                        """UPDATE cloud_sync_tombstones SET last_attempted_at = ?,
                                      attempt_count = attempt_count + 1, last_error = ?
                           WHERE sync_uuid = ?""",
                        (now, type(exc).__name__, sync_uuid),
                    )
                    local.commit()
                    self._last_push_failures += 1
                    continue
                # The pushing device is the one that deleted the package.
                local.execute(
                    """UPDATE cloud_sync_tombstones SET pending = 0, origin_device_id = ?, last_attempted_at = ?,
                                  attempt_count = attempt_count + 1, last_error = NULL
                       WHERE sync_uuid = ?""",
                    (device, now, sync_uuid),
                )
                local.commit()
                pushed += 1
        return pushed

    @staticmethod
    def _apply_linked_video(local, run_id: int, linked_video: Any, fallback_time: str) -> None:
        """Restore the link and observations belonging to a synced package revision.

        A link row keeps its id when its video moves to another package, as in
        local linking: audits, experiment assignments and metadata edits kept
        only on this device hang off that id and would cascade with a delete.
        A link this package gives up is parked on no package rather than
        deleted, because a later row of the same pull may hand the video to
        another package; _pull deletes the parked links nobody claimed.
        """
        if linked_video is not None and not isinstance(linked_video, dict):
            return
        video_id = str((linked_video or {}).get("youtube_video_id") or "").strip()
        current = local.execute(
            "SELECT id,youtube_video_id FROM published_video_links WHERE analysis_run_id = ?", (run_id,)
        ).fetchone()
        if current and str(current[1]) != video_id:
            local.execute("UPDATE published_video_links SET analysis_run_id = -id WHERE id = ?", (int(current[0]),))
        if not video_id:
            return
        now = _now()
        ownership = (linked_video.get("ownership_state") or "unverified", 1 if linked_video.get("ownership_verified") else 0,
                     linked_video.get("verified_channel_id"), linked_video.get("ownership_verified_at"))
        # A device connected to another channel cannot see this video as its
        # owner (older versions marked it failed). An ownership verified for
        # the channel connected here stays; this device checks it itself.
        kept = local.execute(
            """SELECT p.ownership_state, p.ownership_verified, p.verified_channel_id, p.ownership_verified_at
               FROM published_video_links p JOIN youtube_channel_connection c ON c.id = 1
               WHERE p.youtube_video_id = ? AND p.ownership_verified = 1
                 AND c.channel_id != '' AND p.verified_channel_id = c.channel_id""",
            (video_id,),
        ).fetchone()
        if kept and not ownership[1]:
            ownership = tuple(kept)
        local.execute(
            """INSERT INTO published_video_links(
                   analysis_run_id,youtube_video_id,published_at,selected_title,selected_thumbnail_package,
                   selected_description,selected_tags_json,selected_hashtags_json,format,language,region,notes,
                   linked_at,updated_at,youtube_metadata_json,metadata_synced_at,ownership_state,ownership_verified,
                   verified_channel_id,ownership_verified_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(youtube_video_id) DO UPDATE SET
                   analysis_run_id=excluded.analysis_run_id,published_at=excluded.published_at,
                   selected_title=excluded.selected_title,selected_thumbnail_package=excluded.selected_thumbnail_package,
                   selected_description=excluded.selected_description,selected_tags_json=excluded.selected_tags_json,
                   selected_hashtags_json=excluded.selected_hashtags_json,format=excluded.format,
                   language=excluded.language,region=excluded.region,notes=excluded.notes,linked_at=excluded.linked_at,
                   updated_at=excluded.updated_at,youtube_metadata_json=excluded.youtube_metadata_json,
                   metadata_synced_at=excluded.metadata_synced_at,ownership_state=excluded.ownership_state,
                   ownership_verified=excluded.ownership_verified,verified_channel_id=excluded.verified_channel_id,
                   ownership_verified_at=excluded.ownership_verified_at""",
            (run_id, video_id, linked_video.get("published_at") or fallback_time,
             linked_video.get("selected_title"), linked_video.get("selected_thumbnail_package"),
             linked_video.get("selected_description"), json.dumps(linked_video.get("selected_tags") or [], ensure_ascii=False),
             json.dumps(linked_video.get("selected_hashtags") or [], ensure_ascii=False), linked_video.get("format"),
             linked_video.get("language"), linked_video.get("region"), linked_video.get("notes"),
             linked_video.get("linked_at") or fallback_time, linked_video.get("updated_at") or fallback_time,
             json.dumps(linked_video.get("youtube_metadata"), ensure_ascii=False) if linked_video.get("youtube_metadata") is not None else None,
             linked_video.get("metadata_synced_at"), *ownership),
        )
        link_id = int(local.execute("SELECT id FROM published_video_links WHERE youtube_video_id = ?", (video_id,)).fetchone()[0])
        # As in local linking, ideas of another package stop pointing at a link that moved away from it.
        local.execute(
            """UPDATE content_ideas SET published_video_link_id = NULL,
                      status = CASE WHEN status = 'published' THEN 'package_generated' ELSE status END,
                      updated_at = ?
               WHERE published_video_link_id = ? AND analysis_run_id != ?""",
            (now, link_id, run_id),
        )
        # Cohorts only see links that have a metadata row, and a payload may
        # carry none; local linking starts every link with the same row.
        language = str(linked_video.get("language") or "").strip()
        # Stored in the cohort spelling, as local linking stores it.
        package_format = comparable_format(linked_video.get("format"))
        local.execute(
            """INSERT OR IGNORE INTO published_video_comparable_metadata
                   (published_video_link_id,language,format,duration_bucket,topic_category,language_source,
                    format_source,duration_bucket_source,topic_category_source,created_at,updated_at)
               VALUES(?,?,?,'unknown','unknown',?,?,'unknown','unknown',?,?)""",
            (link_id, language or "unknown", package_format or "unknown",
             "package" if language else "unknown", "package" if package_format else "unknown", now, now),
        )
        metadata = linked_video.get("comparable_metadata")
        if isinstance(metadata, dict):
            sources = metadata.get("sources") if isinstance(metadata.get("sources"), dict) else {}
            # An older version may have stored another spelling ("short").
            metadata_format = comparable_format(metadata.get("format"))
            try:
                with _savepoint(local, "cloud_item"):
                    local.execute(
                        """INSERT INTO published_video_comparable_metadata(
                               published_video_link_id,language,format,duration_bucket,topic_category,language_source,
                               format_source,duration_bucket_source,topic_category_source,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(published_video_link_id) DO UPDATE SET
                               language=excluded.language,format=excluded.format,duration_bucket=excluded.duration_bucket,
                               topic_category=excluded.topic_category,language_source=excluded.language_source,
                               format_source=excluded.format_source,duration_bucket_source=excluded.duration_bucket_source,
                               topic_category_source=excluded.topic_category_source,updated_at=excluded.updated_at""",
                        (link_id, metadata.get("language") or "unknown", metadata_format or "unknown",
                         metadata.get("duration_bucket") or "unknown", metadata.get("topic_category") or "unknown",
                         sources.get("language") or "unknown", (sources.get("format") or "unknown") if metadata_format else "unknown",
                         sources.get("duration_bucket") or "unknown", sources.get("topic_category") or "unknown",
                         fallback_time, metadata.get("updated_at") or fallback_time),
                    )
            except sqlite3.IntegrityError:
                pass  # a source value this version does not know; the row above stays
        for snapshot in linked_video.get("snapshots") or []:
            if not isinstance(snapshot, dict):
                continue
            window = str(snapshot.get("snapshot_window") or "")
            incoming_status = str(snapshot.get("snapshot_status") or "legacy_unverified")
            captured_at = snapshot.get("captured_at") or fallback_time
            existing = local.execute(
                """SELECT id,snapshot_status,captured_at FROM video_performance_snapshots
                   WHERE youtube_video_id = ? AND snapshot_window = ?
                   ORDER BY captured_at DESC,id DESC LIMIT 1""",
                (video_id, window),
            ).fetchone()
            # Completed learning windows are immutable local evidence. A cloud
            # mirror may fill a missing/unfinished window on a restored device,
            # but it never replaces a completed local observation. A display
            # snapshot gives way only to a newer one, so devices agree on it.
            if existing:
                newer_display = window == "current" and str(captured_at) > str(existing[2] or "")
                if str(existing[1]) == "complete" or not (incoming_status == "complete" or newer_display):
                    continue
            values = (
                link_id, video_id, snapshot.get("age_hours") or 0, snapshot.get("views"),
                snapshot.get("watch_time_minutes"), snapshot.get("avg_view_duration_seconds"),
                snapshot.get("avg_view_percentage"), snapshot.get("likes"), snapshot.get("comments"),
                snapshot.get("shares"), snapshot.get("subscribers_gained"), snapshot.get("impressions"),
                snapshot.get("impressions_ctr"), window, incoming_status,
                snapshot.get("attempt_count") or 0, snapshot.get("last_failure_reason"),
                snapshot.get("last_attempted_at"), snapshot.get("completed_at"),
                snapshot.get("source_start_date"), snapshot.get("source_end_date"), captured_at,
            )
            try:
                with _savepoint(local, "cloud_item"):
                    if existing:
                        local.execute(
                            """UPDATE video_performance_snapshots SET published_video_link_id=?,age_hours=?,views=?,
                               watch_time_minutes=?,avg_view_duration_seconds=?,avg_view_percentage=?,likes=?,comments=?,
                               shares=?,subscribers_gained=?,impressions=?,impressions_ctr=?,snapshot_status=?,attempt_count=?,
                               last_failure_reason=?,last_attempted_at=?,completed_at=?,source_start_date=?,source_end_date=?,captured_at=?
                               WHERE id=?""",
                            (values[0], *values[2:13], values[14], *values[15:], int(existing[0])),
                        )
                    else:
                        local.execute(
                            """INSERT INTO video_performance_snapshots(
                                   published_video_link_id,youtube_video_id,age_hours,views,watch_time_minutes,
                                   avg_view_duration_seconds,avg_view_percentage,likes,comments,shares,subscribers_gained,
                                   impressions,impressions_ctr,snapshot_window,snapshot_status,attempt_count,last_failure_reason,
                                   last_attempted_at,completed_at,source_start_date,source_end_date,captured_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            values,
                        )
            except sqlite3.IntegrityError:
                # A status this version does not know, or a second completed copy
                # of one window; the rest of the package still applies.
                continue

    @staticmethod
    def _remote_payload(payload_json: Any, content_hash: str) -> dict[str, Any]:
        """The decoded package, or ValueError when it cannot be trusted or applied."""
        payload = json.loads(payload_json)
        if not isinstance(payload, dict) or int(payload.get("schema") or 0) not in {1, 2}:
            raise ValueError("unsupported_payload_schema")
        if _hash(payload) != content_hash:
            raise ValueError("payload_hash_mismatch")
        analysis = payload.get("analysis")
        if not isinstance(analysis, dict) or not str(analysis.get("query") or "").strip():
            raise ValueError("invalid_analysis_payload")
        selection = payload.get("selection")
        if selection and (not isinstance(selection, dict) or not str(selection.get("generated_package_id") or "").strip()):
            raise ValueError("invalid_selection_payload")
        return payload

    def _apply_remote_row(self, local, row) -> tuple[int, bool]:
        """Apply one cloud row: (1 when local data changed, whether a conflict was recorded)."""
        sync_uuid, origin, revision, content_hash, payload_json, updated_at, deleted_at = row
        sync_uuid, revision, content_hash, updated_at = str(sync_uuid), int(revision), str(content_hash), str(updated_at)
        tombstone = local.execute(
            "SELECT revision,pending,deleted_at FROM cloud_sync_tombstones WHERE sync_uuid = ?", (sync_uuid,)
        ).fetchone()
        # A queued outbox row is an edit made here that the cloud has not accepted yet.
        mapping = local.execute(
            """SELECT p.analysis_run_id,p.revision,p.content_hash,o.sync_uuid IS NOT NULL
               FROM cloud_sync_packages p LEFT JOIN cloud_sync_outbox o ON o.sync_uuid = p.sync_uuid
               WHERE p.sync_uuid = ?""", (sync_uuid,)
        ).fetchone()
        if deleted_at:
            if tombstone and int(tombstone[0]) >= revision:
                return 0, False
            conflict = False
            if mapping:
                if mapping[3]:
                    self._record_conflict(
                        local, sync_uuid=sync_uuid, local_revision=int(mapping[1]), local_hash=str(mapping[2]),
                        remote_revision=revision, remote_hash=content_hash, winner="tombstone",
                    )
                    conflict = True
                now = _now()
                local.execute(
                    """UPDATE content_ideas SET analysis_run_id = NULL,
                              published_video_link_id = NULL,
                              status = CASE WHEN status IN ('package_generated', 'published')
                                            THEN 'scripted' ELSE status END,
                              updated_at = ? WHERE analysis_run_id = ?""",
                    (now, int(mapping[0])),
                )
                # The package's link is parked, not deleted with it: a later row
                # may hand its video to another package, which then takes the
                # link and its evidence. _pull deletes the links nobody claimed.
                local.execute("UPDATE published_video_links SET analysis_run_id = -id WHERE analysis_run_id = ?",
                              (int(mapping[0]),))
                local.execute("DELETE FROM analysis_runs WHERE id = ?", (int(mapping[0]),))
            local.execute(
                """INSERT INTO cloud_sync_tombstones
                       (sync_uuid,origin_device_id,revision,deleted_at,pending,
                        attempt_count,last_attempted_at,last_error)
                   VALUES(?,?,?,?,0,0,NULL,NULL)
                   ON CONFLICT(sync_uuid) DO UPDATE SET
                       origin_device_id=excluded.origin_device_id,
                       revision=excluded.revision,
                       deleted_at=excluded.deleted_at,
                       pending=0,
                       last_error=NULL""",
                (sync_uuid, origin, revision, deleted_at),
            )
            local.execute("DELETE FROM cloud_sync_outbox WHERE sync_uuid = ?", (sync_uuid,))
            return 1, conflict
        if tombstone:
            if int(tombstone[1]):
                return 0, False  # this device's deletion is queued and wins once pushed
            # The deletion was pushed, yet the cloud still has the package:
            # older versions dropped a deletion that trailed a newer revision.
            # Queue it again; the cloud now always applies deletions.
            local.execute(
                """UPDATE cloud_sync_tombstones SET pending = 1, revision = MAX(revision, ?),
                          attempt_count = 0, last_attempted_at = NULL, last_error = NULL
                   WHERE sync_uuid = ?""",
                (revision + 1, sync_uuid),
            )
            self._record_conflict(
                local, sync_uuid=sync_uuid, local_revision=int(tombstone[0]),
                local_hash=_tombstone_hash(sync_uuid, int(tombstone[0]), str(tombstone[2])),
                remote_revision=revision, remote_hash=content_hash, winner="tombstone",
            )
            return 0, True
        run_id = None
        if mapping:
            run_id, local_revision, local_hash = int(mapping[0]), int(mapping[1]), str(mapping[2])
            if content_hash == local_hash:
                if revision > local_revision:
                    # The same content under a later revision; number the next local edit above it.
                    local.execute("UPDATE cloud_sync_packages SET revision=? WHERE sync_uuid=?", (revision, sync_uuid))
                return 0, False
            if revision < local_revision:
                return 0, False
        payload = self._remote_payload(payload_json, content_hash)
        conflict = False
        if mapping:
            if revision == local_revision:
                remote_wins = self._remote_active_wins(local_hash=local_hash, remote_hash=content_hash)
                self._record_conflict(
                    local, sync_uuid=sync_uuid, local_revision=local_revision,
                    local_hash=local_hash, remote_revision=revision,
                    remote_hash=content_hash, winner="remote" if remote_wins else "local",
                )
                if not remote_wins:
                    return 0, True
                conflict = True
            elif mapping[3]:
                # An edit made here that never reached the cloud loses to a
                # later revision from another device; the audit row keeps a trace.
                self._record_conflict(
                    local, sync_uuid=sync_uuid, local_revision=local_revision, local_hash=local_hash,
                    remote_revision=revision, remote_hash=content_hash, winner="remote",
                )
                conflict = True
        analysis = payload["analysis"]
        values = (analysis["query"], analysis.get("created_at") or updated_at, analysis.get("intent"),
                  analysis.get("content_angle"), analysis.get("title"), analysis.get("title_score") or 0,
                  analysis.get("retention_risk"), analysis.get("opportunity_label"), analysis.get("opportunity_score"),
                  json.dumps(analysis.get("package"), ensure_ascii=False) if analysis.get("package") is not None else None)
        if run_id is not None:
            local.execute("""UPDATE analysis_runs SET query=?,created_at=?,intent=?,content_angle=?,title=?,title_score=?,retention_risk=?,opportunity_label=?,opportunity_score=?,payload_json=? WHERE id=?""",
                          (*values, run_id))
        else:
            cursor = local.execute("""INSERT INTO analysis_runs(query,created_at,intent,content_angle,title,title_score,retention_risk,opportunity_label,opportunity_score,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                                   values)
            run_id = int(cursor.lastrowid)
        selection = payload.get("selection")
        if selection:
            local.execute("""INSERT INTO analysis_package_selections(analysis_run_id,generated_package_id,package_json,quality_gate_json,selection_source,selected_at,updated_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(analysis_run_id) DO UPDATE SET generated_package_id=excluded.generated_package_id,package_json=excluded.package_json,quality_gate_json=excluded.quality_gate_json,selection_source=excluded.selection_source,selected_at=excluded.selected_at,updated_at=excluded.updated_at""",
                (run_id,selection["generated_package_id"],json.dumps(selection.get("package") or {},ensure_ascii=False),json.dumps(selection.get("quality_gate") or {},ensure_ascii=False),"creator",selection.get("selected_at") or updated_at,selection.get("updated_at") or updated_at))
        if int(payload.get("schema") or 1) >= 2:
            self._apply_linked_video(local, run_id, payload.get("linked_video"), updated_at)
        # What was stored can differ from the cloud version where local
        # evidence was kept; staging compares with this hash, so it does not
        # mistake that difference for an edit and push the package back.
        stored_hash = _hash(self._package_payload(local, run_id))
        now = _now()
        if mapping:
            local.execute("UPDATE cloud_sync_packages SET revision=?,content_hash=?,last_synced_hash=?,remote_updated_at=?,updated_at=? WHERE sync_uuid=?", (revision,content_hash,stored_hash,updated_at,now,sync_uuid))
        else:
            local.execute("INSERT INTO cloud_sync_packages(sync_uuid,analysis_run_id,origin_device_id,revision,content_hash,last_synced_hash,remote_updated_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (sync_uuid,run_id,origin,revision,content_hash,stored_hash,updated_at,now,now))
        local.execute("DELETE FROM cloud_sync_outbox WHERE sync_uuid=?", (sync_uuid,))
        return 1, conflict

    def _pull_since(self) -> str | None:
        """Where the next pull starts, or None for a full pull."""
        if (self._pull_watermark is None or self._full_pull_needed
                or time.monotonic() - self._last_full_pull >= _FULL_PULL_SECONDS):
            return None
        try:
            return (datetime.fromisoformat(self._pull_watermark) - _PULL_OVERLAP).isoformat()
        except ValueError:
            return None

    def _pull(self, remote, *, since: str | None = None) -> int:
        """Apply cloud rows updated at or after `since`, or every row when it is None.

        Each row applies in its own savepoint. A row this version cannot apply
        (a bad payload, an unknown value, a constraint) is logged and skipped
        instead of rolling back its neighbours and failing every later run.
        """
        self._last_pull_conflicts = 0
        self._last_pull_skipped = 0
        started_at = _now()
        with remote.cursor() as cursor:
            if since is None:
                cursor.execute("""SELECT sync_uuid,origin_device_id,revision,content_hash,payload_json,updated_at,deleted_at
                                  FROM seo_yt_synced_packages ORDER BY updated_at,sync_uuid""")
            else:
                cursor.execute("""SELECT sync_uuid,origin_device_id,revision,content_hash,payload_json,updated_at,deleted_at
                                  FROM seo_yt_synced_packages WHERE updated_at >= %s ORDER BY updated_at,sync_uuid""", (since,))
            rows = cursor.fetchall()
        pulled = 0
        oldest_skipped: str | None = None
        if rows:
            with connect_managed(self.settings.database_path) as local:
                local.execute("BEGIN IMMEDIATE")
                # Parked links belong to no package until the batch ends, so
                # foreign keys are checked at commit instead of per statement.
                local.execute("PRAGMA defer_foreign_keys = ON")
                for row in rows:
                    try:
                        with _savepoint(local, "cloud_row"):
                            applied, conflict = self._apply_remote_row(local, row)
                    except sqlite3.OperationalError:
                        raise  # a locked, full or failing database is an outage, not a bad row
                    except Exception as exc:
                        self._last_pull_skipped += 1
                        oldest_skipped = min(oldest_skipped or str(row[5]), str(row[5]))
                        logger.warning("Skipped cloud package %s that this version cannot apply: %s",
                                       str(row[0])[:8], type(exc).__name__)
                        continue
                    pulled += applied
                    self._last_pull_conflicts += int(conflict)
                # A parked link no package claimed was unlinked on the device that pushed it.
                local.execute("DELETE FROM published_video_links WHERE analysis_run_id < 0")
            # A device whose clock runs ahead must not carry the watermark past
            # rows that other devices are writing now.
            newest = min(max(str(row[5]) for row in rows), started_at)
            if self._pull_watermark is None or newest > self._pull_watermark:
                self._pull_watermark = newest
            # A row that could not be applied is read again by every pull (they
            # read from the watermark on) until it applies, not only hourly.
            if oldest_skipped is not None and oldest_skipped < self._pull_watermark:
                self._pull_watermark = oldest_skipped
        if since is None:
            self._last_full_pull = time.monotonic()
            self._full_pull_needed = False
        return pulled

    def retry_delay(self) -> int:
        """Seconds until the next scheduled run.

        After a run that could not complete (no connection, bad configuration)
        the wait doubles each time, up to the configured ceiling, so an outage
        is retried steadily instead of with a connection attempt and a warning
        every minute.
        """
        base = max(30, self.settings.cloud_sync_interval_seconds)
        if not self._consecutive_failures:
            return base
        ceiling = max(base, self.settings.cloud_sync_retry_max_seconds)
        return min(ceiling, base * 2 ** min(self._consecutive_failures, 16))

    def _loop_alive(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive() and not self._stop.is_set()

    def _schedule(self, delay: float | None = None) -> None:
        """Set when the loop runs next and wake it, so it sleeps until then."""
        if delay is None:
            delay = self.retry_delay()
            self._status["retry_delay_seconds"] = delay
            if self._consecutive_failures:
                # Devices that lost the cloud together should not all retry in the same second.
                delay += random.uniform(0, delay / 10)
        self._next_run = time.monotonic() + delay
        self._status["next_run_at"] = datetime.fromtimestamp(time.time() + delay, timezone.utc).isoformat()
        self._wake.set()

    def _loop(self, stop: threading.Event) -> None:
        self._schedule(max(0, self.settings.cloud_sync_initial_delay_seconds))
        while not stop.is_set():
            remaining = self._next_run - time.monotonic()
            if remaining > 0 and not self._run_requested:
                self._wake.wait(remaining)
                self._wake.clear()
                continue
            self._run_requested = False
            try:
                self._run(blocking=True)
            except Exception as exc:
                # _run handles sync failures itself; this keeps an unexpected
                # error from ending automatic sync until the app restarts.
                logger.error("Cloud package sync run failed unexpectedly: %s", type(exc).__name__)
            self._schedule()
