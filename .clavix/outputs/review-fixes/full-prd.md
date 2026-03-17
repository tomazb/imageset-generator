# Product Requirements Document: Code Review Regression Fixes

## Problem & Goal

External code review identified three merge-blocking regressions on the `repo-reorg-cleanup` branch that affect containerized deployments and UI functionality. The container image is missing CLI tools required by the oc-mirror v2 migration (opm, skopeo, jq), the startup script uses curl which isn't installed in the ubi9-minimal base image, and the graph toggle from Advanced Configuration is silently ignored by both generation endpoints.

**Goal:** Fix all three regressions so the containerized application starts cleanly, operator discovery works end-to-end, and the graph toggle in the UI produces correct output.

## Requirements

### Must-Have Features

#### [P1] Install opm, skopeo, and jq in container runtime image
- **File:** `Containerfile` (lines 39-45)
- **Problem:** After the Cincinnati/oc-mirror v2 migration, `app.py` shells out to `opm` (operator listing via `opm render`), `skopeo` (catalog validation via `skopeo inspect`/`list-tags`), and `jq` (operator data extraction via `jq` filters). The Containerfile only installs `oc-mirror`. In containerized deployments, the operator selection flow returns HTTP 500 with ENOENT errors.
- **Fix:** Add `opm`, `skopeo`, and `jq` to the runtime image. Use UBI9-compatible RPM packages where available; for `opm`, download the binary from the official OCP mirror or Red Hat registry similar to how `oc-mirror` is installed.
- **Validation:** Container builds successfully; `opm version`, `skopeo --version`, and `jq --version` all succeed inside the running container; operator catalog endpoints return 200.

#### [P2] Replace curl with python in startup.sh connectivity check
- **File:** `scripts/startup.sh` (line 7)
- **Problem:** The startup script calls `curl` for a Cincinnati API connectivity check, but `curl` is not installed in the `ubi9/ubi-minimal` base image. The HEALTHCHECK directive was already fixed to use `python3.11`, but `startup.sh` was missed.
- **Fix:** Replace the `curl` call with a `python3.11` equivalent using `urllib.request`, matching the pattern already used in the Containerfile HEALTHCHECK.
- **Validation:** Container starts without "curl: command not found" errors; connectivity check still reports success/failure correctly.

#### [P2] Pass graph flag through generation endpoints
- **Files:** `src/imageset_generator/app.py` — preview handler (~line 1894) and download handler (~line 2118)
- **Problem:** `generator.add_ocp_versions()` accepts a `graph: bool` parameter (generator.py:60), but neither the `/api/generate/preview` nor `/api/generate/download` endpoint reads `data.get("graph")` or passes it through. The UI's Advanced Configuration graph toggle has no effect — output always contains `mirror.platform.graph: true`.
- **Fix:** Read the `graph` field from the request JSON in both handlers and pass it to `add_ocp_versions()`. Default to `True` for backward compatibility when the field is absent.
- **Validation:** When graph is set to `false` in the request, the generated YAML output does NOT contain `graph: true`; when set to `true` or omitted, it does.

### Technical Requirements
- All fixes must target the existing `repo-reorg-cleanup` branch
- No new dependencies beyond what's available in UBI9 repos
- Containerfile changes must not significantly increase image size
- Fixes must be backward-compatible (existing API consumers unaffected)

## Out of Scope
- Frontend changes to the graph toggle UI (already working correctly)
- Refactoring the operator discovery pipeline
- Adding integration tests for containerized deployments (separate effort)
- Upgrading the UBI base image version

## Additional Context
- The HEALTHCHECK in the Containerfile (line 82-84) was already fixed to use `python3.11` — only `startup.sh` still uses `curl`
- The `graph` parameter in `add_ocp_versions()` defaults to `True`, so omitting it preserves existing behavior
- These are pre-merge blockers for the `repo-reorg-cleanup` branch

---

*Generated with Clavix Planning Mode*
*Generated: 2026-03-17T00:00:00Z*
