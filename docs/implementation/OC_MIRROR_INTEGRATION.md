# OC-Mirror Integration Documentation

## Overview
The OpenShift ImageSetConfiguration Generator integrates with the `oc-mirror` tool for mirroring OCP content to disconnected environments and for discovering available OCP releases, channels, and operator catalogs.

## oc-mirror v1 vs v2

As of OCP 4.18, `oc-mirror` requires an explicit `--v1` or `--v2` flag. Running `oc-mirror` without one of these flags is a fatal error.

- **v1 (`--v1`):** Deprecated since OCP 4.18. Still functional but prints a deprecation warning. Will be removed in a future release.
- **v2 (`--v2`):** The supported version going forward. Used for all mirroring workflows (mirrorToDisk, diskToMirror, mirrorToMirror).

### Discovery command differences

The `list` subcommand (used for discovering releases, channels, and operator catalogs) **only exists in v1**. It was removed in v2 with no direct replacement.

| Discovery Task | v1 Command | v2 Equivalent |
|---|---|---|
| List OCP release versions | `oc-mirror --v1 list releases` | None — use static data files or `--v1` |
| List channels for a version | `oc-mirror --v1 list releases --channels --version=4.18` | None — use static data files or `--v1` |
| List releases in a channel | `oc-mirror --v1 list releases --channel=stable-4.18` | None — use static data files or `--v1` |
| List operator catalogs | `oc-mirror --v1 list operators --catalogs --version=4.18` | None — use static data files or `--v1` |
| List operator packages | `oc-mirror --v1 list operators --catalog=<name>` | None — use static data files or `--v1` |
| Mirror images to disk | `oc-mirror --v1 -c isc.yaml file:///path` | `oc-mirror --v2 -c isc.yaml file:///path` |
| Disk to mirror | `oc-mirror --v1 -c isc.yaml --from file:///path docker://registry` | `oc-mirror --v2 -c isc.yaml --from file:///path docker://registry` |

### How this application handles discovery

Since v2 has no `list` equivalent, the application uses a **static-data-first strategy**:

1. **Primary:** Serve discovery data from pre-built static JSON files in `src/imageset_generator/data/` (e.g., `ocp-versions.json`, `ocp-channels.json`, `channel-releases.json`, `catalogs-*.json`)
2. **Fallback:** If static files are missing, the refresh endpoints call `oc-mirror --v1 list ...` to populate them (this still works but triggers deprecation warnings)
3. **Manual refresh:** The `/api/versions/refresh` endpoint can be called to re-populate static files

> **Known issue:** The refresh code paths in `app.py` currently invoke `oc-mirror --v2 list releases`, which silently fails (v2 ignores the `list` subcommand and exits with code 1). These calls should be updated to use `--v1` for discovery, or removed in favor of a purely static-data approach. The application works today only because the static data files are present.

## Features

### Startup Integration
- The `oc-mirror` tool is automatically downloaded and installed during container build
- On startup, the application loads release data from static JSON files
- The application continues to start even if data loading fails (graceful degradation)

### API Endpoints

**`GET /api/versions/`** — List available OCP release versions

```json
{
  "status": "success",
  "releases": ["4.12", "4.13", "4.14", "4.15", "4.16", "4.17", "4.18", "4.19", "4.20", "4.21"],
  "count": 10,
  "timestamp": "2025-07-30T02:33:39.810676",
  "source": "static_file"
}
```

**`POST /api/versions/refresh`** — Refresh cached release data via oc-mirror

**`GET /api/releases/<version>/<channel>`** — List releases for a version/channel

**`GET /api/channels/<version>`** — List channels for a version

**`GET /api/catalogs/<version>`** — List operator catalogs for a version

**Error Response:**
```json
{
  "status": "error",
  "message": "Error description",
  "timestamp": "2025-07-30T02:33:39.810676"
}
```

## Technical Implementation

### Container Updates
- **Containerfile:** Added dependencies for `oc-mirror` tool:
  - `libgpgme11` - GPG signature verification
  - `libassuan0` - GPG assistant library
  - `libdevmapper1.02.1` - Device mapper library

### Backend Changes
- **API Routes:** Multiple endpoints in `app.py` for versions, releases, channels, and catalogs
- **Static Data Layer:** Pre-built JSON files under `src/imageset_generator/data/` serve as the primary data source
- **Subprocess Integration:** Uses Python's `subprocess` module to execute `oc-mirror` when refreshing data
- **Error Handling:** Includes timeout handling (30s) and graceful fallback to static files

### Mirroring (v2)
For actual mirroring operations (as opposed to discovery), the application uses `oc-mirror --v2`:
- Kubernetes Job manager (`automation/k8s_manager.py`) runs `oc-mirror --v2 --config /config/imageset-config.yaml file://<path>`
- The `-c`/`--config` flag points to the generated ImageSetConfiguration YAML

## Usage Examples

### Command Line Testing
```bash
# Test the releases endpoint
curl -s http://localhost:5000/api/versions/ | jq .

# Test application health
curl -s http://localhost:5000/api/health | jq .

# Refresh release data
curl -s -X POST http://localhost:5000/api/versions/refresh | jq .
```

### Manual oc-mirror discovery (v1)
```bash
# List available OCP versions (requires --v1 flag)
oc-mirror --v1 list releases

# List channels for a specific version
oc-mirror --v1 list releases --channels --version=4.18

# List releases in a channel
oc-mirror --v1 list releases --channel=stable-4.18

# List operator catalogs for a version
oc-mirror --v1 list operators --catalogs --version=4.18
```

### Frontend Integration
The releases can be fetched from the React frontend:
```javascript
fetch('/api/versions/')
  .then(response => response.json())
  .then(data => {
    if (data.status === 'success') {
      console.log('Available releases:', data.releases);
    }
  });
```

## Benefits
1. **Static-First Performance:** Serves data from pre-built JSON files without waiting for oc-mirror subprocess calls
2. **Graceful Degradation:** Application continues to work even if oc-mirror is unavailable
3. **API Access:** Programmatic access to releases, channels, and catalog data for frontend integration
4. **Comprehensive Logging:** Startup logs show available releases for troubleshooting

## Future Enhancements
- Replace `--v1 list` fallback with a purely static or API-based discovery mechanism before v1 removal
- Add release metadata (architectures, errata links, etc.)
- Periodic background refresh of static data files
- Support for filtering releases by version patterns
