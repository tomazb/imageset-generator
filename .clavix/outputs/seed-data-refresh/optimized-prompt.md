# Optimized Prompt (Clavix Enhanced)

Create `scripts/refresh-seed-data.sh` — a bash script that refreshes the three Cincinnati-sourced seed data files (`ocp-versions.json`, `ocp-channels.json`, `channel-releases.json`) in `src/imageset_generator/data/`.

## Workflow

1. **Start the app** using `.venv/bin/python` (never system python). Wait for the Flask app to become ready (health check or port probe).
2. **Hit refresh endpoints** via `curl` to populate the runtime cache at `data/`:
   - `/api/versions/refresh` (populates `ocp-versions.json`)
   - `/api/channels/refresh` (populates `ocp-channels.json`)
   - `/api/releases/refresh` (populates `channel-releases.json`)
3. **Validate** the refreshed runtime cache against the current seed data:
   - Compare version count, channel count, and release entry count
   - Reject if any count decreased (e.g., "versions: 23 -> 1, REJECTED")
   - Report per-file pass/fail with counts
4. **Copy** validated files from `data/` to `src/imageset_generator/data/`
5. **Cleanup** — stop the app process, regardless of success or failure (trap on EXIT)

## Constraints

- **Architecture:** amd64 only — use default filenames (no arch-scoped variants)
- **Idempotent:** Safe to run multiple times
- **Exit codes:** Non-zero on any failure (app won't start, endpoint fails, validation rejects)
- **Error reporting:** Clear, actionable messages showing what failed and why
- **Partial failure:** If any single file's refresh or validation fails, report it but continue attempting the others; exit non-zero at the end

## Validation Logic

For each of the three files, compare the refreshed version against the current seed:
- `ocp-versions.json`: count of `.releases[]` array
- `ocp-channels.json`: count of top-level channel keys
- `channel-releases.json`: count of `.channel_releases` keys

Reject if `new_count < current_count`. Accept if `new_count >= current_count`.

## Success Criteria

- Runs end-to-end, updating all three seed files with fresh Cincinnati data
- Catches regressions (fewer versions/channels than current seed)
- Exits cleanly with actionable error messages on failure
- Suitable for integration into a release checklist or CI gate

---

## Optimization Improvements Applied

1. **[CLARIFIED]** — Specified the exact API endpoint paths for each file refresh, removing ambiguity about which endpoints to call
2. **[STRUCTURED]** — Organized into clear sequential workflow steps (start -> refresh -> validate -> copy -> cleanup)
3. **[EXPANDED]** — Added specific validation logic per file (which JSON fields to compare counts on)
4. **[COMPLETENESS]** — Added cleanup/trap requirement, partial failure handling, and health check before hitting endpoints
5. **[ACTIONABILITY]** — Added concrete exit code and error reporting requirements so the script can be CI-gated
6. **[SCOPED]** — Explicitly called out amd64-only and idempotency constraints

---
*Optimized by Clavix on 2026-03-17. This version is ready for implementation.*
