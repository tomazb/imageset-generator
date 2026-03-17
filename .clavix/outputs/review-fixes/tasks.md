---
project: review-fixes
source: review-20260317-repo-reorg-cleanup
date: 2026-03-17
---

# Review Fixes — Pre-Merge Cleanup

## Phase 1: Critical Security & Production Fixes

- [x] **C1**: Fix command injection in k8s_manager.py — validate storage_mount_path against strict pattern, remove bash -c wrapper
- [x] **C2**: Fix Containerfile health check — replace curl with python urllib since curl isn't in ubi-minimal
- [x] **C3**: Sanitize error responses in app.py — stop returning raw str(e) to API clients
- [x] **M1**: Sanitize error responses in automation/api.py — same pattern as C3

## Phase 2: Broken/Dead Code

- [x] **M5**: Fix dead refresh_ocp_operators endpoint — extract catalog from request.args/JSON

## Phase 3: Performance & Validation Hardening

- [x] **M7-perf**: Add caching to discover_ocp_versions() — TTL-based cache to avoid 72 API calls per request
- [x] **M8**: Add arch parameter validation in discovery.py — allowlist amd64, arm64, ppc64le, s390x
- [x] **M2**: Add bounds on automation API query parameters — cap limit and tail to reasonable maximums
- [x] **M6**: Set Flask MAX_CONTENT_LENGTH to prevent oversized request payloads

## Phase 4: Container & Build Fixes

- [x] **M9**: Parameterize OCP version in Containerfile — use ARG instead of hardcoded 4.18

## Phase 5: External Review Regressions (2026-03-17)

- [x] **R1** [P1]: Install skopeo and jq via microdnf in Containerfile
  > **File**: `Containerfile` lines 25-37
  > **Details**: Add `skopeo` and `jq` to the existing `microdnf -y install` package list (both available in UBI9 AppStream). Add after `shadow-utils`.

- [x] **R2** [P1]: Install opm binary from OCP mirror in Containerfile
  > **File**: `Containerfile`, insert new RUN block after oc-mirror install (after line 45)
  > **Details**: Download `opm-linux.tar.gz` from `mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/${OCP_VERSION}/`. Follow oc-mirror pattern: wget → tar → chmod → mv to `/usr/local/bin/` → rm tarball. Reuse existing `OCP_VERSION` ARG.

- [x] **R3** [P2]: Replace curl with python3.11 in startup.sh connectivity check
  > **File**: `scripts/startup.sh` line 7
  > **Details**: Replace `timeout 15 curl -sf ... -o /dev/null` with `timeout 15 python3.11 -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('https://api.openshift.com/api/upgrades_info/v1/graph?channel=stable-4.18&arch=amd64', headers={'Accept': 'application/json'}))"`. Preserve the existing `&& { ... } || { ... }` control flow.

- [x] **R4** [P2]: Pass graph flag in preview generation endpoint
  > **File**: `src/imageset_generator/app.py` ~line 1894
  > **Details**: Read `graph = data.get("graph", True)` before `generator.add_ocp_versions()` call. Add `graph=graph` kwarg. Default `True` preserves backward compat.

- [x] **R5** [P2]: Pass graph flag in download generation endpoint
  > **File**: `src/imageset_generator/app.py` ~line 2118
  > **Details**: Identical fix to R4 in the download handler. Read `graph = data.get("graph", True)`, add `graph=graph` kwarg to `add_ocp_versions()`.
