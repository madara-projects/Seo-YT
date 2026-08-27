"""Offline-first synchronization of immutable History packages through Aiven MySQL."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from win_engine.core.config import Settings
from win_engine.feedback.migrations import connect_managed

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


class CloudSyncService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "state": "disabled" if not settings.cloud_sync_enabled else "waiting",
            "enabled": bool(settings.cloud_sync_enabled), "running": False,
            "device_id": settings.cloud_sync_device_id or "unconfigured",
            "last_started_at": None, "last_finished_at": None, "next_run_at": None,
            "last_error": None, "last_counts": {"queued": 0, "pushed": 0, "pulled": 0, "failed": 0},
            "last_activity_at": None,
            "last_activity_counts": {"queued": 0, "pushed": 0, "pulled": 0},
            "remote_packages": None,
        }

    def configured(self) -> bool:
        s = self.settings
        return bool(s.cloud_sync_host and s.cloud_sync_database and s.cloud_sync_user and s.cloud_sync_password and s.cloud_sync_device_id)

    def start(self) -> None:
        if not self.settings.cloud_sync_enabled or self._thread:
            return
        self._thread = threading.Thread(target=self._loop, name="cloud-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

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
        except Exception:
            result["pending_uploads"] = None
            result["pending_deletions"] = None
            result["local_packages"] = None
            result["mapped_packages"] = None
            result["synced_packages"] = None
        result["configured"] = self.configured()
        return result

    def run_once(self) -> dict[str, Any]:
        if not self.settings.cloud_sync_enabled:
            return {"state": "disabled", "counts": self._status["last_counts"]}
        if not self.configured():
            self._status["state"] = "unconfigured"
            return {"state": "unconfigured", "counts": self._status["last_counts"]}
        if not self._lock.acquire(blocking=False):
            return {"state": "running", "counts": self._status["last_counts"]}
        counts = {"queued": 0, "pushed": 0, "pulled": 0, "failed": 0}
        self._status.update({"state": "running", "running": True, "last_started_at": _now(), "last_error": None})
        try:
            counts["queued"] = self._stage_local_packages()
            remote = self._remote_connection()
            try:
                self._ensure_remote_schema(remote)
                counts["pushed"] = self._push(remote)
                counts["pulled"] = self._pull(remote)
                with remote.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM seo_yt_synced_packages WHERE deleted_at IS NULL")
                    self._status["remote_packages"] = int(cursor.fetchone()[0])
            finally:
                remote.close()
            self._status["state"] = "healthy/idle"
        except Exception as exc:
            counts["failed"] += 1
            self._status.update({"state": "offline/pending", "last_error": f"{type(exc).__name__}: {exc}"})
            logger.warning("Cloud package sync remains pending: %s", type(exc).__name__)
        finally:
            if counts["queued"] or counts["pushed"] or counts["pulled"]:
                self._status["last_activity_at"] = _now()
                self._status["last_activity_counts"] = {
                    "queued": counts["queued"], "pushed": counts["pushed"], "pulled": counts["pulled"]
                }
            self._status.update({"running": False, "last_finished_at": _now(), "last_counts": counts})
            self._lock.release()
        return {"state": self._status["state"], "counts": counts}

    def _package_payload(self, connection, run_id: int) -> dict[str, Any]:
        row = connection.execute(
            """SELECT query, created_at, intent, content_angle, title, title_score,
                      retention_risk, opportunity_label, opportunity_score, payload_json
               FROM analysis_runs WHERE id = ?""", (run_id,),
        ).fetchone()
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
        now = _now()
        device = str(self.settings.cloud_sync_device_id)
        with connect_managed(self.settings.database_path) as connection:
            run_ids = [int(row[0]) for row in connection.execute("SELECT id FROM analysis_runs ORDER BY id").fetchall()]
            for run_id in run_ids:
                mapping = connection.execute(
                    "SELECT sync_uuid, revision, content_hash, last_synced_hash FROM cloud_sync_packages WHERE analysis_run_id = ?", (run_id,)
                ).fetchone()
                sync_uuid = str(mapping[0]) if mapping else str(uuid.uuid4())
                payload = self._package_payload(connection, run_id)
                content_hash = _hash(payload)
                if mapping and content_hash == str(mapping[2]):
                    continue
                revision = (int(mapping[1]) + 1) if mapping else 1
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
                queued += 1
        return queued

    def _remote_connection(self):
        import pymysql
        ca = Path(str(self.settings.cloud_sync_ssl_ca_path or ""))
        if not ca.is_file():
            raise RuntimeError("Cloud sync CA certificate is missing inside the application container.")
        return pymysql.connect(host=self.settings.cloud_sync_host, port=self.settings.cloud_sync_port,
            user=self.settings.cloud_sync_user, password=self.settings.cloud_sync_password,
            database=self.settings.cloud_sync_database, charset="utf8mb4", autocommit=False,
            connect_timeout=10, read_timeout=20, write_timeout=20,
            ssl={"ca": str(ca), "check_hostname": True})

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

    def _push(self, remote) -> int:
        with connect_managed(self.settings.database_path) as local:
            deletion_rows = local.execute(
                """SELECT sync_uuid,revision,deleted_at FROM cloud_sync_tombstones
                   WHERE pending = 1 ORDER BY deleted_at LIMIT 100"""
            ).fetchall()
            for sync_uuid, revision, deleted_at in deletion_rows:
                now = _now()
                tombstone_hash = _hash({
                    "schema": 1, "deleted": True, "sync_uuid": sync_uuid,
                    "revision": int(revision), "deleted_at": deleted_at,
                })
                with remote.cursor() as cursor:
                    cursor.execute("""INSERT INTO seo_yt_synced_packages
                        (sync_uuid,origin_device_id,revision,content_hash,payload_json,created_at,updated_at,deleted_at)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE
                        content_hash=IF(VALUES(revision)>=revision,VALUES(content_hash),content_hash),
                        payload_json=IF(VALUES(revision)>=revision,VALUES(payload_json),payload_json),
                        updated_at=IF(VALUES(revision)>=revision,VALUES(updated_at),updated_at),
                        deleted_at=IF(VALUES(revision)>=revision,VALUES(deleted_at),deleted_at),
                        origin_device_id=IF(VALUES(revision)>=revision,VALUES(origin_device_id),origin_device_id),
                        revision=GREATEST(revision,VALUES(revision))""",
                        (sync_uuid, self.settings.cloud_sync_device_id, revision, tombstone_hash,
                         "{}", now, now, deleted_at))
                remote.commit()
                local.execute(
                    """UPDATE cloud_sync_tombstones SET pending = 0, last_attempted_at = ?,
                              attempt_count = attempt_count + 1, last_error = NULL
                       WHERE sync_uuid = ?""",
                    (now, sync_uuid),
                )
            rows = local.execute("SELECT sync_uuid,revision,payload_json,content_hash FROM cloud_sync_outbox ORDER BY queued_at LIMIT 100").fetchall()
            for sync_uuid, revision, payload_json, content_hash in rows:
                now = _now()
                with remote.cursor() as cursor:
                    cursor.execute("""INSERT INTO seo_yt_synced_packages
                        (sync_uuid,origin_device_id,revision,content_hash,payload_json,created_at,updated_at,deleted_at)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,NULL) ON DUPLICATE KEY UPDATE
                        content_hash=IF(deleted_at IS NULL AND VALUES(revision)>=revision,VALUES(content_hash),content_hash),
                        payload_json=IF(deleted_at IS NULL AND VALUES(revision)>=revision,VALUES(payload_json),payload_json),
                        updated_at=IF(deleted_at IS NULL AND VALUES(revision)>=revision,VALUES(updated_at),updated_at),
                        origin_device_id=IF(deleted_at IS NULL AND VALUES(revision)>=revision,VALUES(origin_device_id),origin_device_id),
                        revision=IF(deleted_at IS NULL,GREATEST(revision,VALUES(revision)),revision)""",
                        (sync_uuid, self.settings.cloud_sync_device_id, revision, content_hash, payload_json, now, now))
                remote.commit()
                local.execute("UPDATE cloud_sync_packages SET last_synced_hash=?,remote_updated_at=? WHERE sync_uuid=?", (content_hash, now, sync_uuid))
                local.execute("DELETE FROM cloud_sync_outbox WHERE sync_uuid=?", (sync_uuid,))
        return len(deletion_rows) + len(rows)

    @staticmethod
    def _apply_linked_video(local, run_id: int, linked_video: Any, fallback_time: str) -> None:
        """Restore the link and observations belonging to a synced package revision."""
        if linked_video is None:
            local.execute("DELETE FROM published_video_links WHERE analysis_run_id = ?", (run_id,))
            return
        if not isinstance(linked_video, dict):
            return
        video_id = str(linked_video.get("youtube_video_id") or "").strip()
        if not video_id:
            local.execute("DELETE FROM published_video_links WHERE analysis_run_id = ?", (run_id,))
            return
        local.execute("DELETE FROM published_video_links WHERE analysis_run_id = ? AND youtube_video_id != ?", (run_id, video_id))
        local.execute(
            """INSERT INTO published_video_links(
                   analysis_run_id,youtube_video_id,published_at,selected_title,selected_thumbnail_package,
                   selected_description,selected_tags_json,selected_hashtags_json,format,language,region,notes,
                   linked_at,updated_at,youtube_metadata_json,metadata_synced_at,ownership_state,ownership_verified,
                   verified_channel_id,ownership_verified_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(analysis_run_id) DO UPDATE SET
                   youtube_video_id=excluded.youtube_video_id,published_at=excluded.published_at,
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
             linked_video.get("metadata_synced_at"), linked_video.get("ownership_state") or "unverified",
             1 if linked_video.get("ownership_verified") else 0, linked_video.get("verified_channel_id"),
             linked_video.get("ownership_verified_at")),
        )
        link_id = int(local.execute("SELECT id FROM published_video_links WHERE analysis_run_id = ?", (run_id,)).fetchone()[0])
        metadata = linked_video.get("comparable_metadata")
        if isinstance(metadata, dict):
            sources = metadata.get("sources") if isinstance(metadata.get("sources"), dict) else {}
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
                (link_id, metadata.get("language") or "unknown", metadata.get("format") or "unknown",
                 metadata.get("duration_bucket") or "unknown", metadata.get("topic_category") or "unknown",
                 sources.get("language") or "unknown", sources.get("format") or "unknown",
                 sources.get("duration_bucket") or "unknown", sources.get("topic_category") or "unknown",
                 fallback_time, metadata.get("updated_at") or fallback_time),
            )
        local.execute("DELETE FROM video_performance_snapshots WHERE youtube_video_id = ?", (video_id,))
        for snapshot in linked_video.get("snapshots") or []:
            if not isinstance(snapshot, dict):
                continue
            local.execute(
                """INSERT INTO video_performance_snapshots(
                       published_video_link_id,youtube_video_id,age_hours,views,watch_time_minutes,
                       avg_view_duration_seconds,avg_view_percentage,likes,comments,shares,subscribers_gained,
                       impressions,impressions_ctr,snapshot_window,snapshot_status,attempt_count,last_failure_reason,
                       last_attempted_at,completed_at,source_start_date,source_end_date,captured_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (link_id, video_id, snapshot.get("age_hours") or 0, snapshot.get("views"),
                 snapshot.get("watch_time_minutes"), snapshot.get("avg_view_duration_seconds"),
                 snapshot.get("avg_view_percentage"), snapshot.get("likes"), snapshot.get("comments"),
                 snapshot.get("shares"), snapshot.get("subscribers_gained"), snapshot.get("impressions"),
                 snapshot.get("impressions_ctr"), snapshot.get("snapshot_window"),
                 snapshot.get("snapshot_status") or "legacy_unverified", snapshot.get("attempt_count") or 0,
                 snapshot.get("last_failure_reason"), snapshot.get("last_attempted_at"), snapshot.get("completed_at"),
                 snapshot.get("source_start_date"), snapshot.get("source_end_date"), snapshot.get("captured_at") or fallback_time),
            )

    def _pull(self, remote) -> int:
        with remote.cursor() as cursor:
            cursor.execute("""SELECT sync_uuid,origin_device_id,revision,content_hash,payload_json,updated_at,deleted_at
                              FROM seo_yt_synced_packages ORDER BY updated_at,sync_uuid""")
            rows = cursor.fetchall()
        pulled = 0
        with connect_managed(self.settings.database_path) as local:
            for sync_uuid, origin, revision, content_hash, payload_json, updated_at, deleted_at in rows:
                seen_tombstone = local.execute(
                    "SELECT revision FROM cloud_sync_tombstones WHERE sync_uuid = ?", (sync_uuid,)
                ).fetchone()
                if deleted_at:
                    if seen_tombstone and int(seen_tombstone[0]) >= int(revision):
                        continue
                    mapping = local.execute(
                        "SELECT analysis_run_id FROM cloud_sync_packages WHERE sync_uuid = ?", (sync_uuid,)
                    ).fetchone()
                    if mapping:
                        now = _now()
                        local.execute(
                            """UPDATE content_ideas SET analysis_run_id = NULL,
                                      published_video_link_id = NULL,
                                      status = CASE WHEN status IN ('package_generated', 'published')
                                                    THEN 'scripted' ELSE status END,
                                      updated_at = ? WHERE analysis_run_id = ?""",
                            (now, int(mapping[0])),
                        )
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
                    pulled += 1
                    continue
                if seen_tombstone:
                    # A locally queued or previously applied deletion always
                    # wins over an older active cloud row.
                    continue
                mapping = local.execute("SELECT analysis_run_id,revision FROM cloud_sync_packages WHERE sync_uuid=?", (sync_uuid,)).fetchone()
                if mapping and int(mapping[1]) >= int(revision):
                    continue
                payload = json.loads(payload_json)
                analysis = payload["analysis"]
                if mapping:
                    run_id = int(mapping[0])
                    local.execute("""UPDATE analysis_runs SET query=?,created_at=?,intent=?,content_angle=?,title=?,title_score=?,retention_risk=?,opportunity_label=?,opportunity_score=?,payload_json=? WHERE id=?""",
                        (analysis["query"],analysis["created_at"],analysis.get("intent"),analysis.get("content_angle"),analysis.get("title"),analysis.get("title_score") or 0,analysis.get("retention_risk"),analysis.get("opportunity_label"),analysis.get("opportunity_score") or 0,json.dumps(analysis.get("package"),ensure_ascii=False) if analysis.get("package") is not None else None,run_id))
                else:
                    cursor = local.execute("""INSERT INTO analysis_runs(query,created_at,intent,content_angle,title,title_score,retention_risk,opportunity_label,opportunity_score,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (analysis["query"],analysis["created_at"],analysis.get("intent"),analysis.get("content_angle"),analysis.get("title"),analysis.get("title_score") or 0,analysis.get("retention_risk"),analysis.get("opportunity_label"),analysis.get("opportunity_score") or 0,json.dumps(analysis.get("package"),ensure_ascii=False) if analysis.get("package") is not None else None))
                    run_id = int(cursor.lastrowid)
                selection = payload.get("selection")
                if selection:
                    local.execute("""INSERT INTO analysis_package_selections(analysis_run_id,generated_package_id,package_json,quality_gate_json,selection_source,selected_at,updated_at)
                        VALUES(?,?,?,?,?,?,?) ON CONFLICT(analysis_run_id) DO UPDATE SET generated_package_id=excluded.generated_package_id,package_json=excluded.package_json,quality_gate_json=excluded.quality_gate_json,selection_source=excluded.selection_source,selected_at=excluded.selected_at,updated_at=excluded.updated_at""",
                        (run_id,selection["generated_package_id"],json.dumps(selection.get("package") or {},ensure_ascii=False),json.dumps(selection.get("quality_gate") or {},ensure_ascii=False),"creator",selection.get("selected_at") or updated_at,selection.get("updated_at") or updated_at))
                if int(payload.get("schema") or 1) >= 2:
                    self._apply_linked_video(local, run_id, payload.get("linked_video"), updated_at)
                if mapping:
                    local.execute("UPDATE cloud_sync_packages SET revision=?,content_hash=?,last_synced_hash=?,remote_updated_at=?,updated_at=? WHERE sync_uuid=?", (revision,content_hash,content_hash,updated_at,_now(),sync_uuid))
                else:
                    local.execute("INSERT INTO cloud_sync_packages(sync_uuid,analysis_run_id,origin_device_id,revision,content_hash,last_synced_hash,remote_updated_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (sync_uuid,run_id,origin,revision,content_hash,content_hash,updated_at,_now(),_now()))
                local.execute("DELETE FROM cloud_sync_outbox WHERE sync_uuid=?", (sync_uuid,))
                pulled += 1
        return pulled

    def _loop(self) -> None:
        if self._stop.wait(max(0, self.settings.cloud_sync_initial_delay_seconds)):
            return
        while not self._stop.is_set():
            self.run_once()
            next_run = time.time() + max(30, self.settings.cloud_sync_interval_seconds)
            self._status["next_run_at"] = datetime.fromtimestamp(next_run, timezone.utc).isoformat()
            if self._stop.wait(max(30, self.settings.cloud_sync_interval_seconds)):
                return
