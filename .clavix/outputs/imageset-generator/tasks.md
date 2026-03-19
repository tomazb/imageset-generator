# Implementation Plan

**Project**: imageset-generator
**Generated**: 2026-03-17T12:00:00Z
**Source**: PRD sections 2.9, 2.10, 2.11 (oc-mirror v2 full support)

## Technical Context & Standards
*Detected Stack & Patterns*
- **Architecture**: Flask REST API + React/PatternFly frontend
- **Framework**: Python 3.10+ / Flask 3.1.x
- **Automation**: `automation/` module with `k8s_manager.py` (K8s Job creation), `engine.py` (orchestration), `config.yaml` (YAML-based config)
- **Validation**: Custom `validation.py` module with `validate_catalog_url()`, `validate_version()`, `validate_channel()`, `safe_path_component()`
- **Command builders**: `build_opm_command()`, `build_skopeo_command()` in `app.py` — pattern for subprocess arg construction with TLS support
- **Conventions**: `datetime.now(timezone.utc).isoformat()` for timestamps; `TLS_VERIFY` constant from `constants.py` for all TLS decisions
- **K8s Job pattern**: ConfigMap for ImageSetConfig YAML, Secret for registry creds, PVC or emptyDir for storage, labels for tracking

---

## Phase 1: Fix broken code path — wrong dict key in get_operator_catalogs

- [x] **Fix `catalogs.json.get("data")` to use correct key `"catalogs"`** (ref: Verification #3)
  Task ID: phase-1-broken-key-01
  > **Implementation**: Edit `src/imageset_generator/app.py:1153`.
  > **Details**: `refresh_catalogs_for_version()` returns `{"catalogs": {...}}` (line 853), but `get_operator_catalogs()` reads `catalogs.json.get("data", [])`. Change `"data"` to `"catalogs"`. The value is a version-keyed dict `{"4.17": [...]}`, so also extract the version list: `catalogs.json.get("catalogs", {}).get(version, [])`.

- [x] **Add regression test for get_operator_catalogs fallback path** (ref: Verification #3)
  Task ID: phase-1-broken-key-02
  > **Implementation**: Edit `tests/unit/test_src_layout.py`.
  > **Details**: Add a test that mocks `load_catalogs_from_file` to return `None` and `subprocess.run` to succeed, then asserts `GET /api/operators/catalogs/<version>` returns the catalog list from the refresh path (not empty/error). Verify the response `catalogs` field is a list, not a dict.

---

## Phase 2: Add catalog URL validation to generation endpoints

- [x] **Validate `operator_catalog` in `/api/generate/preview`** (ref: Verification #2, PRD 1.6)
  Task ID: phase-2-catalog-validation-01
  > **Implementation**: Edit `src/imageset_generator/app.py:1568`.
  > **Details**: Before passing `catalog` to `generator.add_operators()`, call `validate_catalog_url(catalog)` from `validation.py`. Catch `ValidationError` and return 400 with a clear message. The import for `validate_catalog_url` already exists (line 38). Apply to the catalog variable at line 1568 and the equivalent location in `/api/generate/download`.

- [x] **Validate `operator_catalog` in `/api/generate/download`** (ref: Verification #2, PRD 1.6)
  Task ID: phase-2-catalog-validation-02
  > **Implementation**: Edit `src/imageset_generator/app.py` in the `generate_download()` function.
  > **Details**: Same pattern as preview — validate `catalog` with `validate_catalog_url()` before passing to generator. Find the catalog assignment in `generate_download()` (mirrors the preview logic) and add validation there.

- [x] **Add test for catalog URL validation in generation endpoints** (ref: Verification #2)
  Task ID: phase-2-catalog-validation-03
  > **Implementation**: Edit `tests/unit/test_src_layout.py` or create `tests/unit/test_generate_validation.py`.
  > **Details**: Test that POST to `/api/generate/preview` with `operator_catalog: "evil.registry.io/malicious/index"` returns 400, not 200 with generated YAML containing the malicious URL. Also test that `registry.redhat.io/redhat/redhat-operator-index` passes validation.

---

## Phase 3: Standardize timestamps to timezone-aware UTC

- [x] **Replace all `datetime.now().isoformat()` with `datetime.now(timezone.utc).isoformat()`** (ref: Verification #1)
  Task ID: phase-3-timestamps-01
  > **Implementation**: Edit `src/imageset_generator/app.py` — all ~41 occurrences of `datetime.now().isoformat()`.
  > **Details**: Use find-and-replace: `datetime.now().isoformat()` → `datetime.now(timezone.utc).isoformat()`. The `timezone` import already exists (line 2: `from datetime import datetime, timezone`). This is a mechanical replacement — every occurrence has the same pattern. Verify no other files in `src/imageset_generator/` use naive `datetime.now()`.

- [x] **Add test asserting API timestamps include timezone offset** (ref: Verification #1)
  Task ID: phase-3-timestamps-02
  > **Implementation**: Edit `tests/unit/test_src_layout.py`.
  > **Details**: Add a test that hits a representative endpoint (e.g., `GET /api/ocp-versions` with seed data) and asserts the `timestamp` field in the response contains `+00:00` (timezone-aware ISO format). This prevents future regressions.

---

## Phase 4: Update PRD with current metrics

- [x] **Update test count and LOC in PRD appendix** (ref: Verification #5, #6)
  Task ID: phase-4-prd-update-01
  > **Implementation**: Edit `.clavix/outputs/imageset-generator/full-prd.md:118` and `:325`.
  > **Details**: Update "46 passing tests" to current count (79+ after new tests from this plan). Update app.py LOC estimate. Run `wc -l src/imageset_generator/app.py` and `pytest --co -q | tail -1` for accurate numbers.

---

## Phase 5: Honor target architecture in Cincinnati discovery

- [x] **Thread `arch` parameter through API refresh endpoints to discovery functions** (ref: External review P2)
  Task ID: phase-5-arch-discovery-01
  > **Implementation**: Edit `src/imageset_generator/app.py` — lines 311, 632, 717.
  > **Details**: All three call sites (`discover_ocp_versions()`, `discover_channel_releases(channel)`, `discover_channels_for_version(version)`) omit the `arch` parameter, defaulting to `"amd64"`. Add an optional `arch` query parameter to the three API endpoints (`/api/versions/refresh`, `/api/releases/<version>/<channel>/refresh`, `/api/channels/refresh`) that gets parsed from `request.args.get('arch', 'amd64')` and passed through. The discovery functions already accept `arch` — no changes needed in `discovery.py`.

- [x] **Add tests for non-amd64 architecture parameter passthrough** (ref: External review P2)
  Task ID: phase-5-arch-discovery-02
  > **Implementation**: Edit `tests/unit/test_api.py` or `tests/unit/test_discovery.py`.
  > **Details**: Test that `POST /api/versions/refresh?arch=arm64` passes `arch="arm64"` to `discover_ocp_versions()` (mock the discovery function and assert the call args). Similarly test the channel and release refresh endpoints. Also test that omitting `arch` defaults to `"amd64"`.

---

## Phase 6: Respect TLS_VERIFY in Cincinnati requests

- [x] **Configure requests session to honor TLS_VERIFY** (ref: External review P2)
  Task ID: phase-6-tls-cincinnati-01
  > **Implementation**: Edit `src/imageset_generator/discovery.py` — `_get_session()` function (line 25-33).
  > **Details**: Import `TLS_VERIFY` from `.constants`. In `_get_session()`, set `_session.verify = TLS_VERIFY` on the session object. This makes all Cincinnati API calls respect the global TLS setting. No changes needed at call sites since the session object carries the verify setting.

- [x] **Add test for TLS_VERIFY=False in discovery module** (ref: External review P2)
  Task ID: phase-6-tls-cincinnati-02
  > **Implementation**: Edit `tests/unit/test_discovery.py` or `tests/unit/test_tls_config.py`.
  > **Details**: Patch `imageset_generator.discovery.TLS_VERIFY` to `False` and `imageset_generator.discovery._session` to `None` (to force re-creation), then call `_get_session()` and assert `session.verify is False`. Also test the default case (`TLS_VERIFY=True`) gives `session.verify` of `True`.

---

## Phase 7: Propagate TLS_VERIFY to skopeo catalog validation

- [x] **Create `build_skopeo_command()` helper with TLS support** (ref: External review P2)
  Task ID: phase-7-tls-skopeo-01
  > **Implementation**: Edit `src/imageset_generator/app.py` — add function near `build_opm_command()` (after line 77).
  > **Details**: Create `build_skopeo_command(subcommand, image_ref, skip_tls=None, extra_args=None)` following the same pattern as `build_opm_command()`. When `skip_tls` is True (or defaults to `not TLS_VERIFY`), append `--tls-verify=false` to the command. The `subcommand` parameter handles both `'inspect'` and `'list-tags'` use cases. Example: `build_skopeo_command('inspect', f'docker://{url}', extra_args=['--no-tags'])`.

- [x] **Replace inline skopeo commands with `build_skopeo_command()`** (ref: External review P2)
  Task ID: phase-7-tls-skopeo-02
  > **Implementation**: Edit `src/imageset_generator/app.py` — lines 808-810 and 1180-1182.
  > **Details**: Replace the hardcoded `['skopeo', 'inspect', '--no-tags', f'docker://{catalog_url}']` at line 808-810 with `build_skopeo_command('inspect', f'docker://{catalog_url}', extra_args=['--no-tags'])`. Replace `['skopeo', 'list-tags', f'docker://{catalog["base_url"]}']` at line 1180 with `build_skopeo_command('list-tags', f'docker://{catalog["base_url"]}')`. Both now respect TLS_VERIFY.

- [x] **Add tests for skopeo TLS_VERIFY propagation** (ref: External review P2)
  Task ID: phase-7-tls-skopeo-03
  > **Implementation**: Edit `tests/unit/test_tls_config.py`.
  > **Details**: Test `build_skopeo_command()` with `skip_tls=True` asserts `'--tls-verify=false'` is in the returned command list. Test with `skip_tls=False` asserts `'--tls-verify=false'` is NOT present. Test default behavior (skip_tls=None) respects the `TLS_VERIFY` constant. Follow the existing test patterns in `test_tls_config.py` for `build_opm_command()`.

---

## Phase 8: Mirror destination modes — support file://, docker://, and enclave (ref: PRD 2.9)

> **Note**: PRD 2.9 also requires "Destination mode selection in UI and CLI". The UI/CLI tasks are deferred to a separate phase after the backend automation support is complete, since the UI depends on the backend config schema and API being stable first. Re-verify line numbers in `k8s_manager.py` before starting — Phases 1-7 may have shifted them. Use function/method names as primary anchors.

- [ ] **Add destination configuration to automation config schema** (ref: PRD 2.9)
  Task ID: phase-8-destination-config-01
  > **Implementation**: Edit `src/imageset_generator/automation/config.yaml`.
  > **Details**: Add a new `kubernetes.destination` section with keys: `type` (enum: `"file"`, `"registry"`, `"enclave"`; default: `"file"`), `registry_url` (string, used when type is `"registry"`, e.g. `"docker://disconnected-registry.example.com:5000"`), `enclave_source_dir` (string, default: `"/mirror/source"`), `enclave_dest_dir` (string, default: `"/mirror/dest"`). Keep existing `storage.mount_path` as the file destination path. Add inline YAML comments explaining each mode.

- [ ] **Add `build_oc_mirror_command()` helper function** (ref: PRD 2.9)
  Task ID: phase-8-destination-cmd-02
  > **Implementation**: Edit `src/imageset_generator/automation/k8s_manager.py` — add function before `create_mirror_job()`.
  > **Details**: Create `build_oc_mirror_command(config_path: str, destination: dict, skip_tls: bool = False, workspace_path: Optional[str] = None) -> list` following the `build_skopeo_command()` pattern from `app.py`. Logic: if `destination['type'] == 'file'`, return `['oc-mirror', '--v2', '--config', config_path, f'file://{destination.get("mount_path", "/mirror")}']`. If `'registry'`, return `['oc-mirror', '--v2', '--config', config_path, destination['registry_url']]`. If `'enclave'`, return `['oc-mirror', '--v2', 'copy', 'enclave', '--config', config_path, '--from', destination['enclave_source_dir'], '--to', destination['enclave_dest_dir']]`. When `skip_tls` is True, append `--dest-tls-verify=false` (registry/file mode) or `--src-tls-verify=false --dest-tls-verify=false` (enclave mode). These are the actual oc-mirror v2 flags (confirmed via `oc-mirror --v2 --help`). When `workspace_path` is provided, insert `--workspace file://{workspace_path}` before the destination arg. Replace the hardcoded command in `_build_job_manifest()` with a call to this function.

- [ ] **Replace hardcoded oc-mirror command in `_build_job_manifest()`** (ref: PRD 2.9)
  Task ID: phase-8-destination-job-03
  > **Implementation**: Edit `src/imageset_generator/automation/k8s_manager.py:438-443`.
  > **Details**: Replace the hardcoded `f"oc-mirror --v2 --config /config/imageset-config.yaml file://{storage_mount_path}"` with a call to `build_oc_mirror_command()`. Note: `self.config` in `KubernetesManager` is already the `kubernetes` sub-dict (set in `__init__`), so read destination as `self.config.get('destination', {'type': 'file'})`. Pass `skip_tls=not TLS_VERIFY` (import `TLS_VERIFY` from `..constants`). Wrap the command list with `['/bin/bash', '-c', ' '.join(cmd)]` to match the existing shell execution pattern.

- [ ] **Add CA certificate volume mount for internal registries** (ref: PRD 2.9)
  Task ID: phase-8-destination-ca-04
  > **Implementation**: Edit `src/imageset_generator/automation/k8s_manager.py` — in `_build_job_manifest()` volumes section (lines 390-430).
  > **Details**: Add optional CA certificate support. Read `ca_bundle` config from `self.config.get('ca_bundle', {})` (note: `self.config` is already the `kubernetes` sub-dict). If `ca_bundle.get('enabled')` is True, add a volume from ConfigMap (`ca_bundle.get('config_map_name', 'custom-ca-bundle')`) and mount it at `/etc/pki/ca-trust/source/anchors/`. Add `update-ca-trust` to the bash command prefix so certificates are trusted before oc-mirror runs. Also add the config.yaml keys: `kubernetes.ca_bundle.enabled` (bool, default: false), `kubernetes.ca_bundle.config_map_name` (string).

- [ ] **Add destination validation function** (ref: PRD 2.9, 1.6)
  Task ID: phase-8-destination-validate-05
  > **Implementation**: Edit `src/imageset_generator/validation.py`.
  > **Details**: Add `validate_mirror_destination(destination: dict) -> dict` that validates: `type` must be one of `("file", "registry", "enclave")`; if type is `"registry"`, `registry_url` must be present and start with `"docker://"` followed by a valid hostname; if type is `"enclave"`, both `enclave_source_dir` and `enclave_dest_dir` must be non-empty strings. Raise `ValidationError` with descriptive messages on failure. Return validated dict on success.

- [ ] **Thread destination config through engine orchestration** (ref: PRD 2.9)
  Task ID: phase-8-destination-engine-06
  > **Implementation**: Edit `src/imageset_generator/automation/engine.py` — `run_automation()` method.
  > **Details**: Before calling `k8s_manager.create_mirror_job()`, read the destination config from `self.config.get('kubernetes', {}).get('destination', {'type': 'file'})` and call `validate_mirror_destination()` on it. On `ValidationError`, log the error, send failure notification, and return early with error status. The destination dict is already available to k8s_manager through `self.config` — no need to pass it separately.

- [ ] **Add tests for mirror destination modes** (ref: PRD 2.9)
  Task ID: phase-8-destination-tests-07
  > **Implementation**: Create `tests/unit/test_mirror_destinations.py`.
  > **Details**: Test `build_oc_mirror_command()` for all three modes: (1) file mode produces `['oc-mirror', '--v2', '--config', ..., 'file:///mirror']`; (2) registry mode produces `['oc-mirror', '--v2', '--config', ..., 'docker://registry.example.com:5000']`; (3) enclave mode produces `['oc-mirror', '--v2', 'copy', 'enclave', '--config', ..., '--from', ..., '--to', ...]`. Test TLS flags: `skip_tls=True` appends `--dest-tls-verify=false`. Test enclave TLS: `skip_tls=True` appends both `--src-tls-verify=false` and `--dest-tls-verify=false`. Test `validate_mirror_destination()`: valid configs pass, invalid type raises `ValidationError`, missing `registry_url` for registry type raises error, missing dirs for enclave raises error.

- [ ] **Standardize automation module timestamps to timezone-aware UTC** (ref: Phase 3 consistency)
  Task ID: phase-8-datetime-cleanup-08
  > **Implementation**: Edit `src/imageset_generator/automation/k8s_manager.py` and `src/imageset_generator/automation/engine.py`.
  > **Details**: Replace all `datetime.utcnow()` calls with `datetime.now(timezone.utc)` to match the pattern established in Phase 3 for `app.py`. In `k8s_manager.py` this affects lines ~128, 213, 228, 476. In `engine.py` check all timestamp assignments. Ensure `from datetime import datetime, timezone` is imported in both files. All new code in Phases 8-10 must use `datetime.now(timezone.utc)` exclusively.

---

## Phase 9: Registry cleanup and pruning — oc-mirror delete support (ref: PRD 2.10)

- [ ] **Add `build_oc_mirror_delete_command()` helper** (ref: PRD 2.10)
  Task ID: phase-9-delete-cmd-01
  > **Implementation**: Edit `src/imageset_generator/automation/k8s_manager.py` — add function after `build_oc_mirror_command()`.
  > **Details**: Create `build_oc_mirror_delete_command(config_path: str, registry_url: str, skip_tls: bool = False, dry_run: bool = True, workspace_path: str = "/workspace") -> list`. Returns `['oc-mirror', '--v2', 'delete', '--config', config_path, '--workspace', f'file://{workspace_path}', registry_url]`. When `dry_run` is True (default for safety), append `--generate` (oc-mirror delete uses `--generate` for dry-run preview). When `skip_tls` is True, append `--dest-tls-verify=false`. The `workspace_path` defaults to `"/workspace"` and will be updated by Phase 10 to read from workspace config.

- [ ] **Add delete configuration to automation config schema** (ref: PRD 2.10)
  Task ID: phase-9-delete-config-02
  > **Implementation**: Edit `src/imageset_generator/automation/config.yaml`.
  > **Details**: Add a new top-level `cleanup` section with keys: `enabled` (bool, default: false), `dry_run` (bool, default: true — safety first), `schedule` (string, cron expression, default: empty — manual trigger only), `prune_stale_operators` (bool, default: false — whether to auto-prune operator versions no longer in catalog). Add inline comments explaining that delete operations are destructive and dry_run should always be tested first.

- [ ] **Add `create_delete_job()` method to KubernetesManager** (ref: PRD 2.10)
  Task ID: phase-9-delete-job-03
  > **Implementation**: Edit `src/imageset_generator/automation/k8s_manager.py` — add method to `KubernetesManager` class.
  > **Details**: Create `create_delete_job(self, delete_config: str, registry_url: str, dry_run: bool = True, job_name: Optional[str] = None) -> Tuple[str, Dict[str, Any]]`. Follow the same pattern as `create_mirror_job()`: create ConfigMap with delete config YAML, build job manifest with `build_oc_mirror_delete_command()`, mount workspace PVC (required for delete), mount registry credentials. The `dry_run` parameter is passed in by `engine.py` which reads it from `self.config.get('cleanup', {}).get('dry_run', True)` (engine holds root config). `KubernetesManager` does NOT read cleanup config directly — it only knows about the `kubernetes` sub-dict. Job labels should include `app: "imageset-delete"` to distinguish from mirror jobs.

- [ ] **Add delete API endpoints** (ref: PRD 2.10, 2.7)
  Task ID: phase-9-delete-api-04
  > **Implementation**: Edit `src/imageset_generator/automation/api.py`.
  > **Details**: Add two endpoints to the automation blueprint: `POST /api/automation/delete/preview` (returns the delete command that would run, always dry-run) and `POST /api/automation/delete/execute` (creates the actual K8s delete job). Both accept JSON body with `registry_url` (required) and optional `delete_config` (ImageSetConfiguration YAML for what to delete). The preview endpoint calls `build_oc_mirror_delete_command(dry_run=True)` and returns the command list without executing. The execute endpoint validates config, checks `cleanup.enabled`, and creates the job via `k8s_manager.create_delete_job()`.

- [ ] **Add stale operator pruning logic to engine** (ref: PRD 2.10)
  Task ID: phase-9-prune-logic-05
  > **Implementation**: Edit `src/imageset_generator/automation/engine.py`.
  > **Details**: Add `_generate_prune_config(self, current_catalogs: dict) -> Optional[str]` method. When `self.config.get('cleanup', {}).get('prune_stale_operators')` is True, compare the operator packages in the current ImageSetConfiguration against the operators available in the latest catalog data (from cached catalog JSON files). Generate a delete-specific ImageSetConfiguration YAML containing only the operators that are no longer present in the catalog. Return the YAML string, or `None` if nothing to prune. This ties into the delete job workflow — after a mirror run succeeds, optionally trigger a prune delete job.

- [ ] **Add tests for delete command building and job creation** (ref: PRD 2.10)
  Task ID: phase-9-delete-tests-06
  > **Implementation**: Create `tests/unit/test_mirror_delete.py`.
  > **Details**: Test `build_oc_mirror_delete_command()`: (1) default produces command with `--generate` (dry-run); (2) `dry_run=False` omits `--generate`; (3) `skip_tls=True` appends `--dest-tls-verify=false`; (4) command includes `'delete'` subcommand and `'--workspace'` flag. Test that delete job labels use `app: "imageset-delete"`. Test that `dry_run` parameter is correctly threaded through.

---

## Phase 10: Incremental mirroring via v2 workspace (ref: PRD 2.11)

- [ ] **Add workspace volume configuration to config schema** (ref: PRD 2.11)
  Task ID: phase-10-workspace-config-01
  > **Implementation**: Edit `src/imageset_generator/automation/config.yaml`.
  > **Details**: Add `kubernetes.workspace` section with keys: `enabled` (bool, default: true — v2 workspace is essential for incremental mirroring), `pvc.name` (string, default: `"imageset-mirror-workspace"`), `pvc.size` (string, default: `"100Gi"`), `pvc.storage_class` (string, default: same as storage PVC), `mount_path` (string, default: `"/workspace"`). Add inline comment explaining that the workspace persists oc-mirror's internal state between runs, enabling incremental updates.

- [ ] **Mount workspace PVC in mirror and delete jobs** (ref: PRD 2.11)
  Task ID: phase-10-workspace-mount-02
  > **Implementation**: Edit `src/imageset_generator/automation/k8s_manager.py` — `_build_job_manifest()` volumes section (lines 390-430).
  > **Details**: Read workspace config from `self.config.get('workspace', {})` (note: `self.config` in `KubernetesManager` is already the `kubernetes` sub-dict). This task builds on Phase 8 task 04 which also modifies the volumes section. If `workspace.get('enabled', True)`, add a PVC volume `{"name": "oc-mirror-workspace", "persistentVolumeClaim": {"claimName": workspace['pvc']['name']}}` and mount at `workspace.get('mount_path', '/workspace')`. Update `build_oc_mirror_command()` to include `--workspace file:///workspace` argument when workspace is enabled. This makes oc-mirror v2 track state between runs for true incremental mirroring.

- [ ] **Add `--workspace` flag to oc-mirror command builder** (ref: PRD 2.11)
  Task ID: phase-10-workspace-cmd-03
  > **Implementation**: Edit `src/imageset_generator/automation/k8s_manager.py` — `build_oc_mirror_command()` function.
  > **Details**: Add optional `workspace_path: Optional[str] = None` parameter. When provided, insert `'--workspace', f'file://{workspace_path}'` into the command args (after `--config` and before the destination). In `_build_job_manifest()`, pass `workspace_path=workspace_mount_path` if workspace is enabled. This ensures both mirror and delete commands use the same workspace directory.

- [ ] **Add workspace state reporting to automation API** (ref: PRD 2.11, 2.7)
  Task ID: phase-10-workspace-api-04
  > **Implementation**: Edit `src/imageset_generator/automation/api.py`.
  > **Details**: Add `GET /api/automation/workspace/status` endpoint. This reads the automation state file (`data/automation-state.json`) and returns: `last_mirror_time`, `last_processed_version`, `workspace_pvc_name`, `workspace_enabled`. This gives visibility into the incremental mirroring state without needing to inspect the K8s cluster. Return 200 with JSON response following the existing API response pattern (`{"status": "success", "data": {...}, "timestamp": ...}`).

- [ ] **Add mirror diff report generation** (ref: PRD 2.11)
  Task ID: phase-10-diff-report-05
  > **Implementation**: Edit `src/imageset_generator/automation/engine.py` and `src/imageset_generator/automation/api.py`.
  > **Details**: Add `_generate_diff_report(self, version_info: dict) -> dict` method to `AutomationEngine`. This generates the ImageSetConfiguration that would be used for the next mirror run (via `_generate_imageset_config()`), then compares it against the last known state from `data/automation-state.json`. Returns a dict with `added_versions`, `updated_operators`, `removed_items`, and `unchanged_count`. Add `GET /api/automation/mirror/preview` endpoint to `api.py` that calls this method and returns the diff as JSON. This lets platform engineers see what an incremental mirror will do before triggering it.

- [ ] **Add tests for workspace volume mounting and command flags** (ref: PRD 2.11)
  Task ID: phase-10-workspace-tests-06
  > **Implementation**: Create `tests/unit/test_workspace.py`.
  > **Details**: Test `build_oc_mirror_command()` with `workspace_path="/workspace"` includes `'--workspace', 'file:///workspace'` in the command list. Test without workspace_path omits the flag. Test `_build_job_manifest()` with workspace enabled: assert volume list includes PVC with correct claim name, assert volume mounts include workspace mount at correct path. Test `_build_job_manifest()` with workspace disabled: assert no workspace volume or mount is present.

---

## Phase 11: Code review fixes — hardening and documentation (ref: CodeRabbit review)

- [x] **Handle JSONDecodeError in Cincinnati API client** (ref: CodeRabbit #3)
  Task ID: phase-11-json-decode-01
  > **Implementation**: Edit `src/imageset_generator/discovery.py` — `_query_cincinnati()` function, line ~51.
  > **Details**: Wrap `resp.json()` in a try/except to catch `ValueError` (parent of `json.JSONDecodeError`). When caught, log a warning with `logger.warning("Cincinnati returned invalid JSON for channel=%s", channel)` and return `None`. This matches the existing error handling pattern where `requests.RequestException` is caught and returns `None`. The caller (`discover_ocp_versions`, etc.) already handles `None` returns gracefully by falling back to cached data.

- [x] **Add subprocess timeout to test_src_layout import check** (ref: CodeRabbit #4)
  Task ID: phase-11-subprocess-timeout-02
  > **Implementation**: Edit `tests/unit/test_src_layout.py` — the `subprocess.run()` call around line 50.
  > **Details**: Add `timeout=30` parameter to the `subprocess.run()` call that checks `PROJECT_ROOT` and `RUNTIME_ROOT` imports. This prevents the test from hanging if the Python interpreter blocks on startup. No try/except needed — `subprocess.TimeoutExpired` will naturally fail the test with a clear traceback.

- [x] **Remove `|| true` from CI quality workflow** (ref: CodeRabbit #6)
  Task ID: phase-11-ci-quality-gate-03
  > **Implementation**: Edit `.github/workflows/quality.yml` — lines 31, 35, 39, 43, 47.
  > **Details**: Remove `|| true` from the black, isort, flake8, pylint, and mypy commands so lint/type failures actually fail the CI job. Currently all quality checks are silently swallowed. Before removing, verify the codebase passes all checks locally by running: `black --check --diff src tests`, `isort --check-only --diff src tests`, `flake8 --max-line-length=120 --extend-ignore=E203,W503 src tests`, `pylint --max-line-length=120 --disable=C0111,R0913,R0914 src/imageset_generator`, `mypy --ignore-missing-imports src/imageset_generator`. Fix any failures before removing `|| true` to avoid breaking CI.

- [x] **Update README test counts and fix import paths in code snippets** (ref: CodeRabbit #7)
  Task ID: phase-11-readme-update-04
  > **Implementation**: Edit `README.md`.
  > **Details**: Search for all test count references (e.g., "46 passing tests", "27 tests") and update to current count (98 tests, 97 passing). Also fix code snippets that use bare imports (`from constants import ...`, `from app import ...`, `from validation import ...`) to use fully-qualified package imports (`from imageset_generator.constants import ...`, etc.) so examples are copy-pasteable. Run `grep -n "tests" README.md` and `grep -n "^from " README.md` to find all occurrences.

---

## Phase 12: Fix API regressions — catalog lookup, arch-scoped reads, and channel discovery (ref: External review)

- [x] **Use normalized major.minor key when reading refreshed catalogs** (ref: External review P2)
  Task ID: phase-12-catalog-version-key-01
  > **Implementation**: Edit `src/imageset_generator/app.py` — `get_operator_catalogs()` function, around line 1205.
  > **Details**: When `version` is a patch release like "4.17.9", `refresh_catalogs_for_version()` normalizes it to "4.17" and returns `{"catalogs": {"4.17": [...]}}`. But line 1205 does `all_catalogs.get(version, [])` using the original patch version, which misses the key. Fix: normalize the version before lookup. Add `version_key = '.'.join(version.split('.')[:2])` before the lookup and use `all_catalogs.get(version_key, [])`. This matches the normalization logic in `refresh_catalogs_for_version()` (lines 838-840).

- [x] **Honor arch parameter in /api/ocp-versions endpoint** (ref: External review P2)
  Task ID: phase-12-arch-ocp-versions-02
  > **Implementation**: Edit `src/imageset_generator/app.py` — `get_ocp_versions_static()` function, around line 1935.
  > **Details**: This endpoint hardcodes `_data_read_file("ocp-versions.json")`, ignoring any `arch` query parameter. After `POST /api/versions/refresh?arch=arm64` writes to `ocp-versions-arm64.json`, `GET /api/ocp-versions?arch=arm64` still reads the amd64 file. Fix: add `arch = request.args.get('arch', 'amd64')` and change the file path to `_data_read_file(_arch_scoped_filename("ocp-versions.json", arch))`. This matches the pattern already used in `get_versions()` (lines 907-916) and the refresh endpoint.

- [x] **Probe all channel prefixes when discovering OCP minor versions** (ref: External review P2)
  Task ID: phase-12-discovery-channels-03
  > **Implementation**: Edit `src/imageset_generator/discovery.py` — `discover_ocp_versions()` function, lines 71-73.
  > **Details**: Currently only probes `stable-4.X`, so versions that exist only in candidate or fast channels are invisible. Change the loop to probe all prefixes from `CINCINNATI_CHANNEL_PREFIXES` (already imported from constants: `["candidate", "fast", "stable", "eus"]`). A minor version should be included if ANY channel prefix returns nodes. Update the inner loop: `for minor in OCP_MINOR_PROBE_RANGE: found = False; for prefix in CINCINNATI_CHANNEL_PREFIXES: channel = f"{prefix}-4.{minor}"; data = _query_cincinnati(channel, arch); if data and data.get("nodes"): found = True; break; if found: versions.append(f"4.{minor}")`. Use `break` on first hit to avoid redundant API calls — stable is most common, so order the prefixes as `["stable", "fast", "candidate", "eus"]` for efficiency.

- [x] **Add tests for catalog patch-version lookup, arch-scoped reads, and multi-channel discovery** (ref: External review P2)
  Task ID: phase-12-regression-tests-04
  > **Implementation**: Edit `tests/unit/test_refresh.py` and `tests/unit/test_discovery.py`.
  > **Details**: Three tests: (1) In `test_refresh.py`, test that `GET /api/operators/catalogs/4.17.9` returns catalogs after refresh — mock `refresh_catalogs_for_version` to return `{"catalogs": {"4.17": [catalog_list]}}` and assert the response contains the catalog list (not empty). (2) In `test_refresh.py`, test that `GET /api/ocp-versions?arch=arm64` reads from `ocp-versions-arm64.json` — mock `_data_read_file` and assert it's called with the arch-scoped filename. (3) In `test_discovery.py`, test that `discover_ocp_versions()` finds a version that only exists on `candidate` channel — mock `_query_cincinnati` to return None for `stable-4.19` but valid data for `candidate-4.19`, assert "4.19" appears in the result.

---

## Phase 13: Smart release version filtering in web UI (ref: PRD 1.3)

- [x] **Add `filterReleasesByMinorVersion()` utility and apply to channel releases** (ref: PRD 1.3)
  Task ID: phase-13-minor-filter-01
  > **Implementation**: Edit `frontend/src/App.js` — in `fetchReleasesForChannelAndVersion()` (the function that handles the `/api/releases/{version}/{channel}` response).
  > **Details**: Add a helper function `filterReleasesByMinorVersion(releases, minorVersion)` near the top of `App.js`. It takes the raw releases array (e.g., `["4.18.0", "4.18.1", ..., "4.20.15"]`) and a minor version string (e.g., `"4.20"`) and returns only releases whose major.minor matches using string prefix: `releases.filter(r => r.startsWith(minorVersion + '.'))`. Apply this filter after receiving the API response and before setting the `channelReleases` state. The selected minor version is `config.ocp_versions[0]`. Preserve the existing sort order (already sorted by the backend's `_version_sort_key`).

- [x] **Filter max version dropdown to only show versions >= min version** (ref: PRD 1.3)
  Task ID: phase-13-max-constraint-02
  > **Implementation**: Edit `frontend/src/components/BasicConfig.js` — in the max version `FormSelect` rendering (around lines 305-344).
  > **Details**: Compute a filtered release list for the max version dropdown: only include releases `>=` the selected `config.ocp_min_version`. Use semantic version comparison: split on `'.'`, compare each segment numerically (to correctly handle `4.20.9` vs `4.20.15`). Add a helper `compareVersions(a, b)` that returns -1/0/1 (split both on `'.'`, compare parseInt of each segment left-to-right). Then filter: `channelReleases.filter(v => compareVersions(v, config.ocp_min_version) >= 0)`. If no min version is selected, show all releases.

- [x] **Auto-clear max version when it becomes invalid after min version change** (ref: PRD 1.3)
  Task ID: phase-13-clear-invalid-max-03
  > **Implementation**: Edit `frontend/src/components/BasicConfig.js` — in `handleMinVersionChange()` (around lines 152-168).
  > **Details**: After the min version changes, check if the currently selected `config.ocp_max_version` is non-empty and lower than the new min version (using the `compareVersions()` helper from task 02). If so, clear it by calling `onConfigChange({...config, ocp_max_version: ''})`. This prevents an invalid state where max < min.

- [x] **Verify reactive clearing on version/channel change** (ref: PRD 1.3)
  Task ID: phase-13-verify-reset-04
  > **Implementation**: Verify existing behavior in `frontend/src/components/BasicConfig.js` — `handleSingleOcpVersionChange()` (around lines 95-113) and `handleChannelChange()` (around lines 124-150).
  > **Details**: Confirm that changing the OCP minor version or channel already resets `ocp_min_version` and `ocp_max_version` to `""`. `handleChannelChange()` does this at lines 141-142. Verify `handleSingleOcpVersionChange()` triggers a channel change which resets releases transitively. If not, add explicit clearing of min/max fields. This is a verification task — may require no code changes.

- [x] **Add tests for version filtering and max constraint logic** (ref: PRD 1.3)
  Task ID: phase-13-tests-05
  > **Implementation**: Create `frontend/src/__tests__/versionFiltering.test.js` (or add to existing test file if one exists for App.js).
  > **Details**: Test `filterReleasesByMinorVersion()`: (1) `filterReleasesByMinorVersion(["4.18.0", "4.19.1", "4.20.0", "4.20.15"], "4.20")` returns `["4.20.0", "4.20.15"]`; (2) empty array returns empty; (3) no matches returns empty. Test `compareVersions()`: (1) `compareVersions("4.20.9", "4.20.15")` returns -1; (2) `compareVersions("4.20.15", "4.20.15")` returns 0; (3) `compareVersions("4.20.15", "4.20.9")` returns 1. Test max filtering: given min="4.20.10" and releases=["4.20.0","4.20.10","4.20.15"], filtered max options are ["4.20.10","4.20.15"].

---

*Generated by Clavix /clavix:plan*
