"""Versioned, backup-first SQLite schema management for personal learning data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


CURRENT_SCHEMA_VERSION = 6
_APPLICATION_TABLES = {
    "analysis_runs",
    "video_snapshots",
    "owned_video_snapshots",
    "youtube_channel_connection",
    "youtube_channel_syncs",
    "published_video_links",
    "video_performance_snapshots",
    "package_experiments",
}


class MigrationError(RuntimeError):
    """Raised when a database cannot be migrated without risking user data."""


class ClosingConnection(sqlite3.Connection):
    """A transaction context that also closes file-backed SQLite handles."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


@dataclass(frozen=True)
class MigrationResult:
    old_version: int
    new_version: int
    migrated: bool
    backup_path: str | None = None


def configure_connection(connection: sqlite3.Connection) -> sqlite3.Connection:
    """Apply required integrity and contention settings to every connection."""

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def connect_managed(database_path: str, *, timeout: float = 10) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=timeout, factory=ClosingConnection)
    return configure_connection(connection)


def online_backup(database_path: str, backup_directory: str | None = None) -> str:
    """Create and verify a consistent backup using SQLite's online backup API."""

    source_path = Path(database_path).resolve()
    if not source_path.exists():
        raise MigrationError(f"Database does not exist: {source_path}")

    destination_dir = Path(backup_directory).resolve() if backup_directory else source_path.parent / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination_path = destination_dir / f"{source_path.stem}.backup-{stamp}.sqlite3"

    source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True, timeout=10)
    destination = sqlite3.connect(destination_path, timeout=10)
    try:
        source.backup(destination)
        destination.commit()
        integrity = destination.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise MigrationError("The SQLite backup failed its integrity check.")
    except Exception:
        destination.close()
        source.close()
        try:
            destination_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    else:
        destination.close()
        source.close()

    # Reopen independently so verification does not rely on the backup handle.
    verification = sqlite3.connect(f"file:{destination_path.as_posix()}?mode=ro", uri=True, timeout=10)
    try:
        if verification.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise MigrationError("The reopened SQLite backup failed verification.")
    finally:
        verification.close()
    return str(destination_path)


def prepare_database(database_path: str, *, backup_before_migration: bool = True) -> MigrationResult:
    """Initialize or migrate a file database to the current schema."""

    path = Path(database_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    configure_connection(connection)
    try:
        tables = _table_names(connection)
        old_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    finally:
        connection.close()

    if old_version > CURRENT_SCHEMA_VERSION:
        raise MigrationError(
            f"Database schema version {old_version} is newer than supported version {CURRENT_SCHEMA_VERSION}."
        )

    # A zero-byte/new SQLite file has no user data to back up or migrate.
    if not (_APPLICATION_TABLES & tables):
        connection = sqlite3.connect(path, timeout=10)
        configure_connection(connection)
        try:
            initialize_current_schema(connection)
        finally:
            connection.close()
        return MigrationResult(old_version=old_version, new_version=CURRENT_SCHEMA_VERSION, migrated=True)

    if old_version == CURRENT_SCHEMA_VERSION:
        connection = sqlite3.connect(path, timeout=10)
        configure_connection(connection)
        try:
            initialize_current_schema(connection)
        finally:
            connection.close()
        return MigrationResult(old_version=old_version, new_version=old_version, migrated=False)

    unknown_tables = _APPLICATION_TABLES - tables
    if unknown_tables:
        raise MigrationError(
            "Legacy database is missing required tables and was not modified: "
            + ", ".join(sorted(unknown_tables))
        )

    backup_path = online_backup(str(path)) if backup_before_migration else None
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA busy_timeout = 10000")
    try:
        if old_version == 0:
            _migrate_v0_to_v1(connection)
            _migrate_v1_to_v2(connection)
            _migrate_v2_to_v3(connection)
            _migrate_v3_to_v4(connection)
            _migrate_v4_to_v5(connection)
            _migrate_v5_to_v6(connection)
        elif old_version == 1:
            _migrate_v1_to_v2(connection)
            _migrate_v2_to_v3(connection)
            _migrate_v3_to_v4(connection)
            _migrate_v4_to_v5(connection)
            _migrate_v5_to_v6(connection)
        elif old_version == 2:
            _migrate_v2_to_v3(connection)
            _migrate_v3_to_v4(connection)
            _migrate_v4_to_v5(connection)
            _migrate_v5_to_v6(connection)
        elif old_version == 3:
            _migrate_v3_to_v4(connection)
            _migrate_v4_to_v5(connection)
            _migrate_v5_to_v6(connection)
        elif old_version == 4:
            _migrate_v4_to_v5(connection)
            _migrate_v5_to_v6(connection)
        elif old_version == 5:
            _migrate_v5_to_v6(connection)
        else:
            raise MigrationError(f"No migration path exists from schema version {old_version}.")
        configure_connection(connection)
        _verify_database(connection)
    except Exception as exc:
        connection.rollback()
        if isinstance(exc, MigrationError):
            raise
        raise MigrationError(f"Database migration failed safely: {type(exc).__name__}: {exc}") from exc
    finally:
        connection.close()

    return MigrationResult(
        old_version=old_version,
        new_version=CURRENT_SCHEMA_VERSION,
        migrated=True,
        backup_path=backup_path,
    )


def initialize_memory_database(connection: sqlite3.Connection) -> None:
    configure_connection(connection)
    initialize_current_schema(connection)


def initialize_current_schema(connection: sqlite3.Connection) -> None:
    """Create the current schema without rewriting existing compatible tables."""

    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    _create_independent_tables(connection)
    _create_relational_tables(connection)
    _create_indexes(connection)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version INTEGER PRIMARY KEY,
               applied_at TEXT NOT NULL,
               description TEXT NOT NULL
           )"""
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
        (
            CURRENT_SCHEMA_VERSION,
            datetime.now(timezone.utc).isoformat(),
            "Phase 8 immutable published audits and structured experiments",
        ),
    )
    connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
    connection.commit()
    _verify_database(connection)


def _migrate_v0_to_v1(connection: sqlite3.Connection) -> None:
    """Selectively rebuild the three relational tables while preserving every row."""

    _preflight_v0(connection)
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute("ALTER TABLE published_video_links RENAME TO published_video_links_legacy")
        _create_published_video_links(connection)
        connection.execute(
            """INSERT INTO published_video_links (
                   id, analysis_run_id, youtube_video_id, published_at,
                   selected_title, selected_thumbnail_package, selected_description,
                   selected_tags_json, selected_hashtags_json, format, language, region,
                   notes, linked_at, updated_at, youtube_metadata_json, metadata_synced_at,
                   ownership_state, ownership_verified, verified_channel_id, ownership_verified_at
               )
               SELECT id, analysis_run_id, youtube_video_id, published_at,
                      selected_title, selected_thumbnail_package, selected_description,
                      selected_tags_json, selected_hashtags_json, format, language, region,
                      notes, linked_at, updated_at, youtube_metadata_json, metadata_synced_at,
                      'unverified', 0, NULL, NULL
               FROM published_video_links_legacy"""
        )

        connection.execute("ALTER TABLE video_performance_snapshots RENAME TO video_performance_snapshots_legacy")
        _create_video_performance_snapshots(connection)
        connection.execute(
            """INSERT INTO video_performance_snapshots (
                   id, published_video_link_id, youtube_video_id, age_hours, views,
                   watch_time_minutes, avg_view_duration_seconds, avg_view_percentage,
                   likes, comments, shares, subscribers_gained, impressions,
                   impressions_ctr, snapshot_window, snapshot_status, attempt_count,
                   last_failure_reason, last_attempted_at, completed_at,
                   source_start_date, source_end_date, captured_at
               )
               SELECT s.id,
                      (SELECT p.id FROM published_video_links p WHERE p.youtube_video_id = s.youtube_video_id),
                      s.youtube_video_id, s.age_hours, s.views, s.watch_time_minutes,
                      s.avg_view_duration_seconds, s.avg_view_percentage, s.likes,
                      s.comments, s.shares, s.subscribers_gained, s.impressions,
                      s.impressions_ctr, s.snapshot_window,
                      CASE WHEN s.snapshot_window = 'current' THEN 'display_only'
                           ELSE 'legacy_unverified' END,
                      0, NULL, NULL, NULL, NULL, NULL, s.captured_at
               FROM video_performance_snapshots_legacy s"""
        )

        connection.execute("ALTER TABLE package_experiments RENAME TO package_experiments_legacy")
        _create_package_experiments(connection)
        connection.execute(
            """INSERT INTO package_experiments (
                   id, published_video_link_id, youtube_video_id, changed_at,
                   old_title, new_title, old_thumbnail, new_thumbnail, reason,
                   performance_before_json, performance_after_json
               )
               SELECT e.id,
                      (SELECT p.id FROM published_video_links p WHERE p.youtube_video_id = e.youtube_video_id),
                      e.youtube_video_id, e.changed_at, e.old_title, e.new_title,
                      e.old_thumbnail, e.new_thumbnail, e.reason,
                      e.performance_before_json, e.performance_after_json
               FROM package_experiments_legacy e"""
        )

        _assert_same_count(connection, "published_video_links_legacy", "published_video_links")
        _assert_same_count(connection, "video_performance_snapshots_legacy", "video_performance_snapshots")
        _assert_same_count(connection, "package_experiments_legacy", "package_experiments")

        connection.execute("DROP TABLE package_experiments_legacy")
        connection.execute("DROP TABLE video_performance_snapshots_legacy")
        connection.execute("DROP TABLE published_video_links_legacy")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version INTEGER PRIMARY KEY,
                   applied_at TEXT NOT NULL,
                   description TEXT NOT NULL
               )"""
        )
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
            (
                1,
                datetime.now(timezone.utc).isoformat(),
            "Phase 1 ownership, snapshot state, and enforceable relationships",
            ),
        )
        _create_indexes(connection)
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def _preflight_v0(connection: sqlite3.Connection) -> None:
    duplicate_runs = connection.execute(
        """SELECT analysis_run_id, COUNT(*)
           FROM published_video_links GROUP BY analysis_run_id HAVING COUNT(*) > 1"""
    ).fetchall()
    if duplicate_runs:
        raise MigrationError(
            "A saved package is linked to more than one video. Migration stopped without deleting either link."
        )
    missing_runs = connection.execute(
        """SELECT COUNT(*) FROM published_video_links p
           LEFT JOIN analysis_runs a ON a.id = p.analysis_run_id
           WHERE a.id IS NULL"""
    ).fetchone()[0]
    if missing_runs:
        raise MigrationError(
            f"Found {missing_runs} linked video record(s) without a saved package. Migration stopped."
        )


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    """Add source-aware comparable metadata without rewriting Phase 1 rows."""

    _create_comparable_metadata_tables(connection)
    connection.execute(
        """INSERT OR IGNORE INTO published_video_comparable_metadata
           (published_video_link_id, language, format, duration_bucket, topic_category,
            language_source, format_source, duration_bucket_source, topic_category_source,
            created_at, updated_at)
           SELECT id, language, format, 'unknown', 'unknown',
                  CASE WHEN NULLIF(TRIM(language), '') IS NULL THEN 'unknown' ELSE 'package' END,
                  CASE WHEN NULLIF(TRIM(format), '') IS NULL THEN 'unknown' ELSE 'package' END,
                  'unknown', 'unknown',
                  COALESCE(linked_at, CURRENT_TIMESTAMP), COALESCE(updated_at, linked_at, CURRENT_TIMESTAMP)
           FROM published_video_links"""
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
        (2, datetime.now(timezone.utc).isoformat(), "Phase 2 comparable metadata and source audit"),
    )
    connection.execute("PRAGMA user_version = 2")
    connection.commit()


def _migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    """Add creator-selected package attribution without rewriting History."""

    connection.execute("BEGIN IMMEDIATE")
    try:
        _create_analysis_package_selections(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
            (3, datetime.now(timezone.utc).isoformat(), "Phase 4 selected package attribution and generation traceability"),
        )
        connection.execute("PRAGMA user_version = 3")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _migrate_v3_to_v4(connection: sqlite3.Connection) -> None:
    """Add the Stage G1 idea workspace without rewriting existing records."""

    connection.execute("BEGIN IMMEDIATE")
    try:
        _create_content_idea_tables(connection)
        _create_indexes(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
            (4, datetime.now(timezone.utc).isoformat(), "Stage G1 idea backlog and immutable research evidence"),
        )
        connection.execute("PRAGMA user_version = 4")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _migrate_v4_to_v5(connection: sqlite3.Connection) -> None:
    """Add normalized G2/G5 observational evidence without rewriting existing data."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        _create_watchlist_demand_tables(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
            (5, datetime.now(timezone.utc).isoformat(), "Phase 7 watchlist, outlier, and honest demand evidence"),
        )
        connection.execute("PRAGMA user_version = 5")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _migrate_v5_to_v6(connection: sqlite3.Connection) -> None:
    """Add immutable G3 audits and explicit G4 experiment comparisons."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        _create_audit_experiment_tables(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
            (6, datetime.now(timezone.utc).isoformat(), "Phase 8 immutable published audits and structured experiments"),
        )
        connection.execute("PRAGMA user_version = 6")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _create_comparable_metadata_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS published_video_comparable_metadata (
               published_video_link_id INTEGER PRIMARY KEY,
               language TEXT NOT NULL DEFAULT 'unknown',
               format TEXT NOT NULL DEFAULT 'unknown',
               duration_bucket TEXT NOT NULL DEFAULT 'unknown',
               topic_category TEXT NOT NULL DEFAULT 'unknown',
               language_source TEXT NOT NULL DEFAULT 'unknown'
                   CHECK (language_source IN ('package', 'creator', 'youtube_verified', 'unknown')),
               format_source TEXT NOT NULL DEFAULT 'unknown'
                   CHECK (format_source IN ('package', 'creator', 'youtube_verified', 'unknown')),
               duration_bucket_source TEXT NOT NULL DEFAULT 'unknown'
                   CHECK (duration_bucket_source IN ('package', 'creator', 'youtube_verified', 'unknown')),
               topic_category_source TEXT NOT NULL DEFAULT 'unknown'
                   CHECK (topic_category_source IN ('package', 'creator', 'youtube_verified', 'unknown')),
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL,
               FOREIGN KEY(published_video_link_id) REFERENCES published_video_links(id) ON DELETE CASCADE
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS published_video_metadata_edits (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               published_video_link_id INTEGER NOT NULL,
               field_name TEXT NOT NULL,
               old_value TEXT NOT NULL,
               new_value TEXT NOT NULL,
               source TEXT NOT NULL CHECK (source = 'creator'),
               changed_at TEXT NOT NULL,
               FOREIGN KEY(published_video_link_id) REFERENCES published_video_links(id) ON DELETE CASCADE
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_comparable_metadata_topic ON published_video_comparable_metadata(topic_category)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_metadata_edits_link ON published_video_metadata_edits(published_video_link_id, changed_at)"
    )


def _create_independent_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS video_snapshots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               video_id TEXT NOT NULL,
               query TEXT NOT NULL,
               captured_at TEXT NOT NULL,
               published_at TEXT,
               view_count INTEGER DEFAULT 0,
               like_count INTEGER DEFAULT 0,
               comment_count INTEGER DEFAULT 0,
               subscriber_count INTEGER DEFAULT 0
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS owned_video_snapshots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               video_id TEXT NOT NULL,
               captured_at TEXT NOT NULL,
               published_at TEXT,
               title TEXT,
               views INTEGER DEFAULT 0,
               watch_minutes REAL DEFAULT 0,
               average_view_duration REAL DEFAULT 0,
               average_view_percentage REAL DEFAULT 0,
               likes INTEGER DEFAULT 0,
               comments INTEGER DEFAULT 0,
               shares INTEGER DEFAULT 0,
               subscribers_gained INTEGER DEFAULT 0
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS youtube_channel_connection (
               id INTEGER PRIMARY KEY CHECK (id = 1),
               encrypted_refresh_token TEXT NOT NULL,
               channel_id TEXT,
               channel_title TEXT,
               connected_at TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS youtube_channel_syncs (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               synced_at TEXT NOT NULL,
               payload_json TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS analysis_runs (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               query TEXT NOT NULL,
               created_at TEXT NOT NULL,
               intent TEXT,
               content_angle TEXT,
               title TEXT,
               title_score REAL DEFAULT 0,
               retention_risk TEXT,
               opportunity_label TEXT,
               opportunity_score REAL DEFAULT 0,
               payload_json TEXT
           )"""
    )


def _create_relational_tables(connection: sqlite3.Connection) -> None:
    _create_published_video_links(connection)
    _create_video_performance_snapshots(connection)
    _create_package_experiments(connection)
    _create_comparable_metadata_tables(connection)
    _create_analysis_package_selections(connection)
    _create_content_idea_tables(connection)
    _create_watchlist_demand_tables(connection)
    _create_audit_experiment_tables(connection)


def _create_audit_experiment_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS published_video_audits (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               published_video_link_id INTEGER NOT NULL,
               analysis_run_id INTEGER NOT NULL,
               captured_at TEXT NOT NULL,
               summary_state TEXT NOT NULL CHECK(summary_state IN (
                   'not_enough_data','collecting_evidence','observable','mature_observation',
                   'inconclusive','actionable_observation')),
               audit_json TEXT NOT NULL,
               provenance_version TEXT NOT NULL,
               FOREIGN KEY(published_video_link_id) REFERENCES published_video_links(id) ON DELETE CASCADE,
               FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS experiments (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               name TEXT NOT NULL,
               description TEXT NOT NULL DEFAULT '',
               hypothesis TEXT NOT NULL,
               mode TEXT NOT NULL CHECK(mode IN ('controlled','observational')),
               status TEXT NOT NULL CHECK(status IN (
                   'draft','planned','active','paused','completed','cancelled','inconclusive')),
               variable TEXT NOT NULL,
               variable_category TEXT NOT NULL,
               control_definition TEXT NOT NULL,
               variant_definition TEXT NOT NULL,
               success_metric TEXT NOT NULL,
               secondary_metrics_json TEXT NOT NULL DEFAULT '[]',
               target_sample_size INTEGER,
               minimum_sample_size INTEGER NOT NULL DEFAULT 5,
               observation_window TEXT NOT NULL DEFAULT '24h'
                   CHECK(observation_window IN ('24h','7d','28d')),
               start_date TEXT,
               end_date TEXT,
               notes TEXT NOT NULL DEFAULT '',
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS experiment_video_assignments (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               experiment_id INTEGER NOT NULL,
               published_video_link_id INTEGER NOT NULL,
               role TEXT NOT NULL CHECK(role IN ('control','variant','observational_reference')),
               assigned_at TEXT NOT NULL,
               notes TEXT NOT NULL DEFAULT '',
               UNIQUE(experiment_id, published_video_link_id),
               FOREIGN KEY(experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
               FOREIGN KEY(published_video_link_id) REFERENCES published_video_links(id) ON DELETE CASCADE
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS experiment_result_snapshots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               experiment_id INTEGER NOT NULL,
               captured_at TEXT NOT NULL,
               result_state TEXT NOT NULL CHECK(result_state IN (
                   'insufficient_evidence','directional_control','directional_variant',
                   'inconclusive','mixed_results','observational_pattern')),
               result_json TEXT NOT NULL,
               provenance_version TEXT NOT NULL,
               FOREIGN KEY(experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
           )"""
    )
    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_audits_link_time ON published_video_audits(published_video_link_id, captured_at)",
        "CREATE INDEX IF NOT EXISTS idx_audits_state_time ON published_video_audits(summary_state, captured_at)",
        "CREATE INDEX IF NOT EXISTS idx_experiments_status_time ON experiments(status, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_experiment_assignments_role ON experiment_video_assignments(experiment_id, role)",
        "CREATE INDEX IF NOT EXISTS idx_experiment_results_time ON experiment_result_snapshots(experiment_id, captured_at)",
    ):
        connection.execute(statement)


def _create_watchlist_demand_tables(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS watchlist_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
        thumbnail_url TEXT, subscriber_count INTEGER, video_count INTEGER, notes TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','archived')),
        source TEXT NOT NULL DEFAULT 'public_observation', last_researched_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS watchlist_channel_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, watchlist_channel_id INTEGER NOT NULL,
        captured_at TEXT NOT NULL, subscriber_count INTEGER, video_count INTEGER, view_count INTEGER,
        metadata_json TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'public_observation',
        FOREIGN KEY(watchlist_channel_id) REFERENCES watchlist_channels(id) ON DELETE CASCADE)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS watchlist_videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT NOT NULL UNIQUE, watchlist_channel_id INTEGER,
        channel_id TEXT, channel_title TEXT, title TEXT NOT NULL, published_at TEXT, duration_seconds REAL,
        language TEXT, format TEXT, notes TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','archived')),
        source TEXT NOT NULL DEFAULT 'public_observation', last_researched_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        FOREIGN KEY(watchlist_channel_id) REFERENCES watchlist_channels(id) ON DELETE SET NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS watchlist_video_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, watchlist_video_id INTEGER NOT NULL, captured_at TEXT NOT NULL,
        view_count INTEGER, like_count INTEGER, comment_count INTEGER, duration_seconds REAL,
        metadata_json TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'public_observation',
        FOREIGN KEY(watchlist_video_id) REFERENCES watchlist_videos(id) ON DELETE CASCADE)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS watchlist_outlier_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, watchlist_video_id INTEGER NOT NULL, analyzed_at TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('insufficient_evidence','possible_outlier','observed_normal')),
        observed_views INTEGER, baseline_median_views REAL, relative_multiplier REAL, sample_size INTEGER NOT NULL,
        observation_window TEXT NOT NULL, explanation TEXT NOT NULL, signals_json TEXT NOT NULL,
        provenance TEXT NOT NULL DEFAULT 'heuristic_public_observation',
        FOREIGN KEY(watchlist_video_id) REFERENCES watchlist_videos(id) ON DELETE CASCADE)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS demand_research_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, idea_id INTEGER, topic TEXT NOT NULL, language TEXT,
        format TEXT, region TEXT, audience_context TEXT, idea_fingerprint TEXT,
        classification TEXT NOT NULL CHECK(classification IN ('insufficient_evidence','emerging_signal','active_topic','strong_observed_interest')),
        evidence_json TEXT NOT NULL, captured_at TEXT NOT NULL,
        FOREIGN KEY(idea_id) REFERENCES content_ideas(id) ON DELETE SET NULL)""")
    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_watch_channels_state ON watchlist_channels(state, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_watch_channel_snaps ON watchlist_channel_snapshots(watchlist_channel_id, captured_at)",
        "CREATE INDEX IF NOT EXISTS idx_watch_videos_state ON watchlist_videos(state, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_watch_videos_channel ON watchlist_videos(channel_id, published_at)",
        "CREATE INDEX IF NOT EXISTS idx_watch_video_snaps ON watchlist_video_snapshots(watchlist_video_id, captured_at)",
        "CREATE INDEX IF NOT EXISTS idx_outlier_video_time ON watchlist_outlier_analyses(watchlist_video_id, analyzed_at)",
        "CREATE INDEX IF NOT EXISTS idx_demand_topic_time ON demand_research_snapshots(topic, captured_at)",
        "CREATE INDEX IF NOT EXISTS idx_demand_idea_time ON demand_research_snapshots(idea_id, captured_at)",
    ):
        connection.execute(statement)


def _create_content_idea_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS content_ideas (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               topic TEXT NOT NULL,
               notes TEXT,
               format TEXT,
               language TEXT,
               region TEXT,
               visual_or_background TEXT,
               on_screen_text TEXT,
               target_duration_seconds REAL,
               emotion_or_intent TEXT,
               search_angle TEXT,
               browse_angle TEXT,
               audience_angle TEXT,
               evidence_json TEXT NOT NULL DEFAULT '{}',
               status TEXT NOT NULL DEFAULT 'idea'
                   CHECK (status IN ('idea', 'scripted', 'package_generated', 'published', 'archived')),
               analysis_run_id INTEGER,
               published_video_link_id INTEGER,
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL,
               FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE SET NULL,
               FOREIGN KEY(published_video_link_id) REFERENCES published_video_links(id) ON DELETE SET NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS content_idea_research_snapshots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               content_idea_id INTEGER NOT NULL,
               captured_at TEXT NOT NULL,
               evidence_json TEXT NOT NULL,
               FOREIGN KEY(content_idea_id) REFERENCES content_ideas(id) ON DELETE CASCADE
           )"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_content_ideas_status ON content_ideas(status)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_content_ideas_created_at ON content_ideas(created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_content_ideas_cohort ON content_ideas(format, language, region)")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_idea_research_time ON content_idea_research_snapshots(content_idea_id, captured_at)"
    )


def _create_analysis_package_selections(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS analysis_package_selections (
               analysis_run_id INTEGER PRIMARY KEY,
               generated_package_id TEXT NOT NULL,
               package_json TEXT NOT NULL,
               quality_gate_json TEXT,
               selection_source TEXT NOT NULL DEFAULT 'creator'
                   CHECK (selection_source = 'creator'),
               selected_at TEXT NOT NULL,
               updated_at TEXT NOT NULL,
               FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_package_selection_time ON analysis_package_selections(selected_at)"
    )


def _create_published_video_links(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS published_video_links (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               analysis_run_id INTEGER NOT NULL UNIQUE,
               youtube_video_id TEXT NOT NULL UNIQUE,
               published_at TEXT NOT NULL,
               selected_title TEXT,
               selected_thumbnail_package TEXT,
               selected_description TEXT,
               selected_tags_json TEXT,
               selected_hashtags_json TEXT,
               format TEXT,
               language TEXT,
               region TEXT,
               notes TEXT,
               linked_at TEXT NOT NULL,
               updated_at TEXT NOT NULL,
               youtube_metadata_json TEXT,
               metadata_synced_at TEXT,
               ownership_state TEXT NOT NULL DEFAULT 'unverified'
                   CHECK (ownership_state IN ('unverified', 'pending', 'verified', 'failed')),
               ownership_verified INTEGER NOT NULL DEFAULT 0
                   CHECK (ownership_verified IN (0, 1)),
               verified_channel_id TEXT,
               ownership_verified_at TEXT,
               FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
           )"""
    )


def _create_video_performance_snapshots(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS video_performance_snapshots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               published_video_link_id INTEGER,
               youtube_video_id TEXT NOT NULL,
               age_hours REAL NOT NULL,
               views INTEGER,
               watch_time_minutes REAL,
               avg_view_duration_seconds REAL,
               avg_view_percentage REAL,
               likes INTEGER,
               comments INTEGER,
               shares INTEGER,
               subscribers_gained INTEGER,
               impressions INTEGER,
               impressions_ctr REAL,
               snapshot_window TEXT,
               snapshot_status TEXT NOT NULL DEFAULT 'legacy_unverified'
                   CHECK (snapshot_status IN (
                       'display_only', 'pending', 'collecting', 'complete',
                       'empty_retryable', 'failed_retryable', 'legacy_unverified'
                   )),
               attempt_count INTEGER NOT NULL DEFAULT 0,
               last_failure_reason TEXT,
               last_attempted_at TEXT,
               completed_at TEXT,
               source_start_date TEXT,
               source_end_date TEXT,
               captured_at TEXT NOT NULL,
               FOREIGN KEY(published_video_link_id)
                   REFERENCES published_video_links(id) ON DELETE CASCADE
           )"""
    )


def _create_package_experiments(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS package_experiments (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               published_video_link_id INTEGER,
               youtube_video_id TEXT NOT NULL,
               changed_at TEXT NOT NULL,
               old_title TEXT,
               new_title TEXT,
               old_thumbnail TEXT,
               new_thumbnail TEXT,
               reason TEXT,
               performance_before_json TEXT,
               performance_after_json TEXT,
               FOREIGN KEY(published_video_link_id)
                   REFERENCES published_video_links(id) ON DELETE CASCADE
           )"""
    )


def _create_indexes(connection: sqlite3.Connection) -> None:
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_owned_video_snapshots_video_time ON owned_video_snapshots(video_id, captured_at)",
        "CREATE INDEX IF NOT EXISTS idx_video_snapshots_video_time ON video_snapshots(video_id, captured_at)",
        "CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at ON analysis_runs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_pub_links_run_id ON published_video_links(analysis_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_pub_links_yt_id ON published_video_links(youtube_video_id)",
        "CREATE INDEX IF NOT EXISTS idx_pub_links_pub_at ON published_video_links(published_at)",
        "CREATE INDEX IF NOT EXISTS idx_perf_snaps_link_id ON video_performance_snapshots(published_video_link_id)",
        "CREATE INDEX IF NOT EXISTS idx_perf_snaps_yt_id ON video_performance_snapshots(youtube_video_id)",
        "CREATE INDEX IF NOT EXISTS idx_perf_snaps_yt_window ON video_performance_snapshots(youtube_video_id, snapshot_window)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_perf_complete_window_unique ON video_performance_snapshots(youtube_video_id, snapshot_window) WHERE snapshot_window IN ('24h', '7d', '28d') AND snapshot_status = 'complete'",
        "CREATE INDEX IF NOT EXISTS idx_pkg_exp_link_id ON package_experiments(published_video_link_id)",
        "CREATE INDEX IF NOT EXISTS idx_pkg_exp_yt_id ON package_experiments(youtube_video_id)",
    )
    for statement in statements:
        connection.execute(statement)


def _verify_database(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise MigrationError("Database integrity check failed.")
    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise MigrationError(f"Database contains {len(violations)} foreign-key violation(s).")
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != CURRENT_SCHEMA_VERSION:
        raise MigrationError(
            f"Database schema version is {version}; expected {CURRENT_SCHEMA_VERSION}."
        )


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def _assert_same_count(connection: sqlite3.Connection, old_table: str, new_table: str) -> None:
    old_count = int(connection.execute(f'SELECT COUNT(*) FROM "{old_table}"').fetchone()[0])
    new_count = int(connection.execute(f'SELECT COUNT(*) FROM "{new_table}"').fetchone()[0])
    if old_count != new_count:
        raise MigrationError(
            f"Migration row-count mismatch for {new_table}: expected {old_count}, copied {new_count}."
        )
