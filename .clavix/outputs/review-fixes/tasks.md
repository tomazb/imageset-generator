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
