# Code Review Regression Fixes - Quick PRD

External code review found three merge-blocking regressions on `repo-reorg-cleanup`. [P1] The container image is missing `opm`, `skopeo`, and `jq` CLI tools that `app.py` now shells out to after the oc-mirror v2 migration — operator discovery endpoints return 500s in containerized deployments. [P2] `scripts/startup.sh` uses `curl` for a Cincinnati connectivity check but curl isn't installed in ubi9-minimal (the HEALTHCHECK was already fixed to use python but startup.sh was missed). [P2] Both `/api/generate/preview` and `/api/generate/download` call `add_ocp_versions()` without forwarding the `graph` field from request data, making the UI's Advanced Configuration graph toggle ineffective.

Fixes: (1) Install opm, skopeo, and jq in the Containerfile runtime image using UBI9 RPMs or binary downloads. (2) Replace the curl call in startup.sh with a python3.11 urllib.request equivalent matching the existing HEALTHCHECK pattern. (3) Read `data.get("graph", True)` in both generation handlers and pass it to `add_ocp_versions()`. All changes target existing files on the current branch with no new external dependencies.

Out of scope: frontend graph toggle UI changes (already correct), operator pipeline refactoring, containerized integration tests, UBI base image upgrades. Validation: container builds and starts cleanly, operator endpoints return 200, graph toggle produces correct YAML output.

---

*Generated with Clavix Planning Mode*
*Generated: 2026-03-17T00:00:00Z*
