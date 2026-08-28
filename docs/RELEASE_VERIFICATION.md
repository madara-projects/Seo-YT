# Win-Engine OS — Release Verification Baseline

This is the Phase 1A verification-debt closure record for the current checkout. Product logic and intended UI behavior were preserved; only browser test contracts and this verification document were updated.

## 1. Repository identity

- Repository: `D:\Seo-YT`
- Branch: `main`
- Commit: `3089f8a3cda1ec36683031a6044cbf799ae312ed`
- Application version: `0.13.0` (`win_engine/core/config.py`; also returned by `/meta`)
- SQLite schema version: `8` (`win_engine/feedback/migrations.py`)
- `docs/CURRENT_STATE.md`: **missing in this checkout**, despite the supplied baseline saying it exists. It was not recreated or modified.
- `docs/ROADMAP_RECONCILIATION.md` was present as a pre-existing untracked file and was read but not changed in this run.

## 2. Environment

- Canonical Python: 3.11 (`.python-version` and `python:3.11-slim` in `Dockerfile`); host Python was 3.11.9.
- Backend dependencies are pinned in `requirements.txt` and installed by the Dockerfile with `pip install -r requirements.txt`.
- Browser dependencies are separate: `requirements-browser.txt` pins Playwright `1.52.0`. Production Docker intentionally does not install browser tooling.
- Browser runtime: installed Google Chrome `152.0.7977.64`, selected with `SEO_YT_BROWSER_EXECUTABLE`. No browser download was performed.
- Docker runtime observed: Docker `29.7.2`; Compose `v5.4.0`.
- Test framework: Python `unittest` discovery; no pytest, tox, package, or lint configuration was present. The repository documents Docker as the reproducible backend environment and keeps browser tooling outside the production image.

## 3. Backend verification

The complete backend set was run in a fresh image built from the current commit. Browser tests were excluded from this command because their `setUpClass` requires a browser runtime:

```text
docker run --rm --network none --entrypoint python seo-yt-phase1a-verification \
  -m unittest tests.test_cloud_sync tests.test_engine tests.test_phase1_integrity \
  tests.test_phase1_migrations tests.test_phase1_youtube_channel \
  tests.test_phase2_metadata_collector tests.test_phase4_generation_quality \
  tests.test_phase5_retention_assistant tests.test_phase7_intelligence \
  tests.test_phase8_audit_experiments tests.test_stage_g1_ideas
```

Result: **190 tests, 190 passed, 0 failed, 0 errors, 0 skipped**, completed in **45.825 seconds**, exit code `0`.

The warning-looking Gemini quota/transient, oEmbed, and analytics retry messages were emitted by mocked failure-path tests and did not fail any test.

## 4. Browser verification

The repository contains one browser test module (`tests/browser/test_critical_workflows.py`), so running it is the complete browser suite:

```text
$env:PYTHONDONTWRITEBYTECODE='1'
$env:SEO_YT_BROWSER_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
python -m unittest tests.browser.test_critical_workflows
```

Result against the fresh current-commit image: **40 tests, 40 passed, 0 failed, 0 errors, 0 skipped**, completed in **127.500 seconds**, process exit code `0`.

- Runtime: Chrome `152.0.7977.64` through Playwright `1.52.0`.
- No explicit viewport matrix or `set_viewport_size` calls exist in the browser suite; tests use Playwright's default Chromium viewport. Responsive/mobile coverage is therefore not established by this run.
- The three former failures are resolved as documented in Section 7. No browser assertion reported a production API, JavaScript console, or network-isolation failure.

## 5. Static verification

- Python compilation: `docker run --rm --network none --entrypoint python seo-yt-phase1a-verification -m compileall -q app.py win_engine` — **passed**, exit code `0`.
- `git diff --check` — **passed**, exit code `0`.
- No repository lint or type-check command/configuration was found; none was run. This is an unverified area rather than a failure.

## 6. Docker verification

- Fresh image build:

  ```text
  docker build --pull=false --tag seo-yt-phase1a-verification .
  ```

  **Passed**. Image `seo-yt-phase1a-verification:latest` was created from the current source (image ID `89d557107e815643a961fc298d74b0fd398c1a0e171b0d49f4542b50b8ddaddb`).

- A disposable app container from that image was run with an isolated development environment, no `.env`, and no source database mount. `docker ps` reported the container **healthy**; it was removed after verification.
- `GET /health` returned HTTP 200 with `status: ok`, `version: 0.13.0`, and `database_ok: true`.
- `GET /meta` returned application version `0.13.0` and the expected capability payload.
- `GET /ready` returned `status: not_ready` only because the isolated container had no YouTube API key; its database check was healthy. This is an intentional missing-configuration result, not a source regression.
- `docker compose config --quiet` — **passed**, exit code `0`.
- The real project Compose services were observed but not started: `youtube-win-engine` and `youtube-win-engine-redis` were both `Exited (0)` approximately 18 hours earlier. Compose has no Redis healthcheck declaration, so live Redis health was not established in this read-only run.
- Compose's application binding is localhost-only (`127.0.0.1:8000:8000`) and Redis has no host port. The disposable verification container also listened on `127.0.0.1:8000`; `netstat` confirmed `127.0.0.1:8000 LISTENING`.
- The real Compose project was deliberately not brought up because it mounts the user's existing `win_engine.db` and the task forbids using it for destructive verification.

## 7. Former failure classification and resolution

| Test | Exact symptom | Root cause | Application defect? | Environment defect? | Production impact | Recommended next action |
|---|---|---|---|---|---|---|
| `test_experiment_creation_duplicate_click_guard_and_detail` | The original `#experimentName.fill()` timed out because the input was resolved but not visible. | The current experiments page intentionally places the form fields inside a collapsed `<details>` disclosure. | No | No | None; the product disclosure remains collapsed until the user opens it. | Resolved in the test with `open_experiment_form()`, which clicks the `Create a comparison` summary and asserts the disclosure is open before filling. |
| `test_experiment_assignment_comparison_and_insufficient_evidence` | Same invisible `#experimentName` timeout prevented assignment/comparison assertions from running. | Same intentional collapsed-disclosure behavior and stale test interaction. | No | No | None; no product behavior changed. | Resolved with the same helper; duplicate-click protection, assignment, comparison, and insufficient-evidence assertions still run. |
| `test_published_audit_navigation_list_and_intent_actual_detail` | The original list assertion expected `Linked rainy highway upload`; after that was aligned, the old detail assertion also expected `INSUFFICIENT EVIDENCE`. | `audits.js` intentionally renders the actual published `youtube_metadata.title` when available and shows the mature-observation conclusion when a completed observation exists. The fixture intentionally contains both package-topic and published-title values. | No | No | None; the test now checks the real linked published title, detail intent/actual metadata, causality limitation, and mature-observation conclusion. | Resolved by assertion-only updates: wait for `Published rainy highway title`, assert one linked audit card, and assert `Enough observation time is available for comparison.`. The fixture and application renderer were unchanged. |

No backend or browser test remains failing. The stopped project services and isolated `/ready` result are environment/configuration observations, not application test failures. No unmocked YouTube, Gemini, OAuth, or Aiven call was made.

## 8. Security verification

Verification did not print, inspect, or write `.env` values, API keys, Gemini keys, OAuth secrets/tokens, encryption keys, Aiven passwords, or database credentials. The isolated container did not receive the project `.env`; backend/compile runs used network isolation, and browser tests intercepted external requests with deterministic fixtures.

## 9. Data safety

- The real `D:\Seo-YT\win_engine.db` was never mounted into a test container and was not reset, migrated, overwritten, or recreated.
- No destructive migration was run and no user records were deleted.
- OAuth tokens and cloud data were not modified; no Aiven write/sync was performed.
- Only ephemeral test databases/fixtures and a disposable Docker image/container were used. The disposable container was removed after verification; the real project containers were left stopped.

## 10. Actual release confidence

**VERIFIED WITH KNOWN LIMITATIONS**

The current commit passes all 190 backend tests and all 40 browser tests, plus compilation, `git diff --check`, Compose configuration validation, fresh image build, isolated health, `/health`, `/meta`, and localhost binding checks. Limitations are unchanged: the real Compose/Redis services were not started, no lint/type workflow exists, live YouTube/Aiven behavior was not exercised, and `docs/CURRENT_STATE.md` is missing from this checkout. The three browser mismatches are closed without product changes.

## 11. Recommended next implementation phase

1. **PHASE 2 — DATA DURABILITY + CLOUD SYNC CONTRACT HARDENING.** This is the next implementation phase now that the reproducible verification target is clean. Do not implement Phase 2 as part of this verification task.
2. Keep the pinned browser/runtime setup and isolated-database rules when Phase 2 adds cloud replay, conflict, reconnect, tombstone, and restore coverage.
3. Do not treat this baseline as live YouTube/Aiven evidence; preserve the existing evidence and security boundaries.

### Run hand-off

- Files changed in this run: [docs/RELEASE_VERIFICATION.md](docs/RELEASE_VERIFICATION.md), `tests/browser/test_critical_workflows.py`.
- Pre-existing untracked file observed and left unchanged: `docs/ROADMAP_RECONCILIATION.md`.
- Tests: backend **190 passed / 0 failed / 0 errors / 0 skipped**; browser **40 passed / 0 failed / 0 errors / 0 skipped**.
- Unresolved defects: **none confirmed**. The three former browser mismatches are resolved in Section 7; no application source defect was found.
- Next phase: **PHASE 2 — DATA DURABILITY + CLOUD SYNC CONTRACT HARDENING**.
- No commit or push was performed.
