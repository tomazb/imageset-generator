# AGENTS.md - AI Agent Guidelines for ImageSet Generator

This document provides guidance for AI agents working with the ImageSet Generator codebase.

## Project Overview

**ImageSet Generator** is a tool for generating `oc-mirror` ImageSetConfiguration YAML files for OpenShift disconnected installations. It provides:

- **Web UI**: React frontend with Flask API backend
- **CLI**: Command-line interface for direct YAML generation
- **GUI**: Tkinter desktop application
- **Automation**: Scheduled execution with Kubernetes integration

## Directory Structure

```
imageset-generator/
├── README.md                    # Project overview and usage
├── CHANGELOG.md                 # Version history
├── AGENTS.md                    # This file - AI agent guidelines
├── requirements.txt             # Python dependencies
├── Containerfile                # Container build definition
├── podman-compose.yml           # Container orchestration
│
├── src/imageset_generator/      # Main Python package
│   ├── __init__.py              # Package exports
│   ├── app.py                   # Flask API backend (main entry)
│   ├── generator.py             # ImageSetGenerator class
│   ├── discovery.py             # Cincinnati API client
│   ├── constants.py             # Configuration constants
│   ├── validation.py            # Input validation functions
│   ├── exceptions.py            # Custom exception classes
│   ├── cli/                     # CLI/GUI subpackage
│   │   ├── __init__.py
│   │   ├── launcher.py          # CLI entry point
│   │   └── gui.py               # Tkinter GUI
│   ├── automation/              # Kubernetes automation subpackage
│   │   ├── api.py               # Automation API endpoints
│   │   ├── engine.py            # Orchestration engine
│   │   ├── scheduler.py         # Cron scheduling
│   │   ├── k8s_manager.py       # Kubernetes job management
│   │   ├── notifier.py          # Notifications (email, Slack)
│   │   └── config.yaml          # Automation configuration
│   ├── data/*.json              # Bundled seed data (33 files)
│   └── frontend/build/          # Compiled React UI
│
├── automation/                  # Automation documentation & examples
│   ├── README.md                # Automation module guide
│   ├── QUICKSTART.md            # Quick-start guide
│   └── examples/                # K8s manifest examples
│
├── frontend/                    # React frontend
│   ├── src/components/          # React components
│   └── public/                  # Static assets
│
├── tests/                       # Test suite
│   ├── conftest.py              # Pytest configuration
│   ├── unit/                    # Unit tests
│   └── smoke/                   # Smoke tests
│
├── scripts/                     # Shell scripts
│   ├── start-web.sh             # Start web application
│   ├── start-dev.sh             # Development mode
│   ├── start-podman.sh          # Container start
│   └── startup.sh               # Container entrypoint
│
├── docs/                        # Documentation
│   ├── guides/                  # User guides
│   ├── implementation/          # Feature implementation docs
│   ├── review/                  # Code review notes
│   └── images/                  # Documentation screenshots
│
├── data/                        # Runtime cache (gitignored, empty on checkout)
│                                # Populated by /api/*/refresh endpoints
│
└── examples/                    # Sample configurations
    ├── imageset-config.yaml     # Example output
    └── test-imageset.yaml       # Test configuration
```

## Module Dependencies

```
app.py
  ├── generator.py (ImageSetGenerator)
  ├── discovery.py (discover_ocp_versions, discover_channels, etc.)
  ├── constants.py (TLS_VERIFY, timeouts, catalogs)
  ├── validation.py (validate_version, validate_channel, etc.)
  ├── exceptions.py (CatalogError, OperatorError, etc.)
  └── automation/ (optional, if config exists)

cli/launcher.py
  ├── cli/gui.py
  └── generator.py

cli/gui.py
  └── generator.py
```

## Coding Conventions

### Input Validation

**Always use functions from `validation.py`** instead of inline regex:

```python
# ✓ CORRECT
from imageset_generator.validation import validate_version, validate_channel, ValidationError

try:
    version = validate_version(user_input)
    channel = validate_channel(channel_input)
except ValidationError as e:
    return jsonify({'error': str(e)}), 400

# ✗ WRONG - inline regex
if not re.match(r'^\d+\.\d+$', version):
    return error_response()
```

### Exception Handling

**Use specific exceptions from `exceptions.py`**:

```python
# ✓ CORRECT
from imageset_generator.exceptions import CatalogRenderError, CatalogError

if result.returncode != 0:
    raise CatalogRenderError(
        "opm render failed",
        catalog=catalog_url,
        version=version
    )

# ✗ WRONG - generic exception
raise Exception(f"opm render failed: {result.stderr}")
```

### Exception Hierarchy

| Exception | Use Case |
|-----------|----------|
| `ImageSetGeneratorError` | Base class for all errors |
| `CatalogError` | Catalog operations |
| `CatalogRenderError` | OPM render failures |
| `CatalogParseError` | Catalog parsing failures |
| `OperatorError` | Operator operations |
| `OperatorNotFoundError` | Operator not found |
| `VersionError` | Version operations |
| `ConfigurationError` | Invalid configuration |
| `FileOperationError` | File I/O failures |
| `NetworkError` | Network issues |
| `GenerationError` | ImageSet generation |

### API Response Format

All API responses should follow this format:

```python
# Success
return jsonify({
    'status': 'success',
    'data': result_data,
    'timestamp': datetime.now().isoformat()
})

# Error
return jsonify({
    'status': 'error',
    'message': 'Human readable error message',
    'timestamp': datetime.now().isoformat()
}), 400  # or appropriate HTTP status
```

## Common Development Tasks

### Adding a New API Endpoint

1. Add route in `src/imageset_generator/app.py`
2. Use validation functions for input validation
3. Use specific exceptions for error handling
4. Follow the response format convention
5. Add tests in `tests/unit/`

### Adding Validation

1. Add new function in `src/imageset_generator/validation.py`
2. Add tests in `tests/unit/test_validation.py`
3. Export in `src/imageset_generator/__init__.py`

### Running Tests

```bash
# From project root
cd /path/to/imageset-generator
PYTHONPATH=src pytest tests/

# Run specific test file
PYTHONPATH=src pytest tests/unit/test_validation.py

# Run with coverage
PYTHONPATH=src pytest tests/ --cov=src/imageset_generator
```

### Running the Application

```bash
# Development mode (Flask)
PYTHONPATH=src python -m imageset_generator.app --debug

# Using scripts
./scripts/start-dev.sh

# Container mode
podman-compose up imageset-generator
```

## Key Files to Understand

| File | Purpose | When to Modify |
|------|---------|----------------|
| `src/imageset_generator/app.py` | Main Flask API | Adding/modifying API endpoints |
| `src/imageset_generator/generator.py` | Core generation logic | Changing YAML output format |
| `src/imageset_generator/constants.py` | Configuration values | Timeouts, patterns, defaults |
| `src/imageset_generator/validation.py` | Input validation | Adding validation rules |
| `src/imageset_generator/exceptions.py` | Exception classes | Adding error types |

## Known Issues and TODOs

1. **app.py is large** (~2500 lines) - Consider refactoring into Flask blueprints
2. **CI workflows need updates** - GitHub Actions reference old file paths
3. **Some inline validation remains** - Parsing patterns in output processing (intentional)

## Security Considerations

- All user inputs must be validated using `validation.py` functions
- Use `safe_path_component()` for any dynamic file path construction
- Catalog URLs must match allowlist pattern in `validate_catalog_url()`
- TLS verification is controlled by `constants.TLS_VERIFY`


<!-- CLAVIX:START -->
# Clavix - Prompt Improvement Assistant

Clavix is installed in this project. Use the following slash commands:

- `/clavix:improve [prompt]` - Optimize prompts with smart depth auto-selection
- `/clavix:prd` - Generate a PRD through guided questions
- `/clavix:start` - Start conversational mode for iterative refinement
- `/clavix:summarize` - Extract optimized prompt from conversation

**When to use:**
- **Standard depth**: Quick cleanup for simple, clear prompts
- **Comprehensive depth**: Thorough analysis for complex requirements
- **PRD mode**: Strategic planning with architecture and business impact

Clavix automatically selects the appropriate depth based on your prompt quality.

For more information, run `clavix --help` in your terminal.
<!-- CLAVIX:END -->
