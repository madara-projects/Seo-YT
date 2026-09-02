# Phase 2C — Data Durability and Cloud Sync Contract

Verification date: 2026-08-28  
Application: 0.13.0 · SQLite schema: 9

## Contract

SQLite is the authoritative operational database on each device. Aiven/MySQL is
an optional, offline-first mirror of the selected History projection; it is not
a shared transactional database or a replacement for the local workspace.

The mirrored projection contains an `analysis_runs` package, explicit package
selection/quality gate, and its one linked-video projection: selected/published
metadata, ownership provenance, comparable metadata, and saved performance
snapshots. Sync UUIDs are stable local mapping identities, not local SQLite row
IDs. The cloud payload contains no settings, secrets, tokens, or credentials.

Ideas, Watchlist, Demand, Audits, structured Experiments, channel-sync state,
OAuth tokens, API keys, encryption keys, settings, and collector diagnostics
remain local-only. Linked-video observations are mirrored only as part of the
selected History package projection.

## Durability rules

- A History mutation is committed locally before cloud work begins.
- `cloud_sync_outbox` persists active package replay state, including revision,
  content hash, attempt count, attempt time, and a sanitized error type.
- `cloud_sync_tombstones` persists deletion state independently of the deleted
  local package mapping. A tombstone prevents a stale active record from being
  restored after reconnect.
- Pushes acknowledge local outbox/tombstone rows only after a remote commit.
  A crash after a remote commit but before local acknowledgement safely replays
  the same UUID and revision.
- Items are processed independently. A failed package/tombstone remains pending
  with a durable retry marker while other rows can succeed.

## Idempotency and conflicts

Remote upserts are keyed by `sync_uuid`. Replaying an active row or tombstone
cannot create a second remote identity. Revisions are the primary ordering.

For an equal active revision with different payloads, the lexicographically
greater SHA-256 content hash wins. This is deterministic across devices and
does not rely on clock skew. Every observed equal-revision conflict is recorded
in the SQLite `cloud_sync_conflicts` audit table with both revisions/hashes and
the chosen winner. Tombstones always block active resurrection after seen; they
take precedence over active rows at an equal revision.

This is a convergence rule, not a field-by-field merge or collaboration model.
The application deliberately does not claim conflict-free multi-user editing.

## Restore and evidence integrity

Pulling into an empty local History database restores the mirrored package
projection and stable UUID mapping. Repeating the same pull is a no-op. A
newer remote revision can restore a missing or unfinished scheduled snapshot,
but cloud restore never replaces a completed local learning window or a local
current display snapshot. This keeps completed evidence immutable and avoids
turning cloud presence into new evidence or causality.

The existing 5/10/20 evidence thresholds, completed-window rules, ownership
checks, and correlation-only conclusions are unchanged.

## Implementation and tests

Schema 9 adds only `cloud_sync_conflicts`; migration is backup-first through
the existing SQLite migration path and does not reset existing data. New
deterministic fake-cloud tests cover:

- local write + cloud failure + restart/reconnect;
- connection outage retry markers;
- partial batches where peers succeed while one row remains pending;
- replay after remote success before local acknowledgement;
- revision/hash conflict resolution and both winner directions;
- durable tombstones, repeated tombstone pushes, and stale active replay;
- idempotent restore and completed-snapshot preservation;
- cloud-disabled local History behavior; and
- migration from schema 8 to schema 9 without resetting a History row.

No real Aiven service, production SQLite file, YouTube endpoint, Gemini call,
OAuth token, `.env` value, or Compose service is used by these tests.

## Verification results

- Backend suite: **216 passed, 0 failed, 0 errors, 0 skipped**.
- Focused durability suite: **18 passed, 0 failed, 0 errors**.
- Browser suite: **40 passed, 0 failed, 0 errors, 0 skipped**.
- Python compilation, JavaScript syntax verification, `git diff --check`, and
  `docker compose config --quiet`: passed.
- Fresh disposable image build: passed. A disposable container using a temporary
  SQLite path was healthy; `/health` returned `status: ok` and `database_ok:
  true`; `/meta` returned the expected capability list. It was removed after
  verification.

## Limitations

The contract covers the documented History projection only. It does not make
the cloud a full-device backup or synchronize local-only domains. Deterministic
fakes verify retry, replay, and ordering behavior, but do not prove live Aiven
availability, MySQL operational limits, or multi-region network behavior.
