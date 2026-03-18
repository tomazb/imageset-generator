#!/usr/bin/env python3
"""Tests for cache reliability: TTL, completeness validation, and atomic writes."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from imageset_generator.constants import (
    CACHE_FILE_MAX_AGE_SECONDS,
    _cache_file_is_fresh,
    _cache_file_is_plausible,
    atomic_json_dump,
    get_data_read_path,
)


# ---------------------------------------------------------------------------
# TTL / freshness tests
# ---------------------------------------------------------------------------


def test_fresh_cache_file_is_accepted(tmp_path):
    """A cache file with a recent timestamp is considered fresh."""
    cache = tmp_path / "ocp-versions.json"
    cache.write_text(
        json.dumps(
            {
                "releases": ["4.14", "4.15", "4.16"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    assert _cache_file_is_fresh(cache) is True


def test_stale_cache_file_is_rejected(tmp_path):
    """A cache file older than max age is considered stale."""
    old_ts = datetime.now(timezone.utc) - timedelta(
        seconds=CACHE_FILE_MAX_AGE_SECONDS + 3600
    )
    cache = tmp_path / "ocp-versions.json"
    cache.write_text(
        json.dumps({"releases": ["4.14"], "timestamp": old_ts.isoformat()})
    )
    assert _cache_file_is_fresh(cache) is False


def test_cache_without_timestamp_is_stale(tmp_path):
    """A cache file missing the timestamp field is treated as stale."""
    cache = tmp_path / "ocp-versions.json"
    cache.write_text(json.dumps({"releases": ["4.14"]}))
    assert _cache_file_is_fresh(cache) is False


def test_corrupted_cache_file_is_stale(tmp_path):
    """A non-JSON cache file is treated as stale."""
    cache = tmp_path / "ocp-versions.json"
    cache.write_text("NOT JSON {{{")
    assert _cache_file_is_fresh(cache) is False


# ---------------------------------------------------------------------------
# Completeness / plausibility tests
# ---------------------------------------------------------------------------


def test_plausible_versions_cache(tmp_path):
    """ocp-versions with enough releases passes plausibility."""
    cache = tmp_path / "ocp-versions.json"
    cache.write_text(json.dumps({"releases": ["4.14", "4.15", "4.16"]}))
    assert _cache_file_is_plausible(cache) is True


def test_implausible_versions_cache(tmp_path):
    """ocp-versions with too few releases fails plausibility."""
    cache = tmp_path / "ocp-versions.json"
    cache.write_text(json.dumps({"releases": ["4.16"]}))
    assert _cache_file_is_plausible(cache) is False


def test_arch_scoped_plausibility(tmp_path):
    """ocp-versions-arm64.json should still match the ocp-versions threshold."""
    cache = tmp_path / "ocp-versions-arm64.json"
    cache.write_text(json.dumps({"releases": ["4.16"]}))
    assert _cache_file_is_plausible(cache) is False


def test_unknown_cache_file_always_plausible(tmp_path):
    """Files without a known prefix are always considered plausible."""
    cache = tmp_path / "catalogs-4.17.json"
    cache.write_text(json.dumps({"some": "data"}))
    assert _cache_file_is_plausible(cache) is True


def test_channels_cache_plausibility(tmp_path):
    """ocp-channels with at least 1 entry passes plausibility."""
    cache = tmp_path / "ocp-channels.json"
    cache.write_text(json.dumps({"channels": {"4.16": ["stable-4.16"]}}))
    assert _cache_file_is_plausible(cache) is True


def test_channels_cache_empty_fails(tmp_path):
    """ocp-channels with no entries fails plausibility."""
    cache = tmp_path / "ocp-channels.json"
    cache.write_text(json.dumps({"channels": {}}))
    assert _cache_file_is_plausible(cache) is False


# ---------------------------------------------------------------------------
# get_data_read_path integration: stale/partial cache falls through
# ---------------------------------------------------------------------------


def test_stale_cache_falls_through_to_seed(tmp_path, monkeypatch):
    """A stale runtime cache should not shadow packaged seed data."""
    runtime_dir = tmp_path / "runtime" / "data"
    runtime_dir.mkdir(parents=True)
    packaged_dir = tmp_path / "packaged" / "data"
    packaged_dir.mkdir(parents=True)

    # Stale runtime cache
    old_ts = datetime.now(timezone.utc) - timedelta(
        seconds=CACHE_FILE_MAX_AGE_SECONDS + 3600
    )
    runtime_file = runtime_dir / "ocp-versions.json"
    runtime_file.write_text(
        json.dumps({"releases": ["4.16"], "timestamp": old_ts.isoformat()})
    )

    # Good packaged seed
    packaged_file = packaged_dir / "ocp-versions.json"
    packaged_file.write_text(
        json.dumps({"releases": [f"4.{v}" for v in range(14, 23)]})
    )

    monkeypatch.setattr(
        "imageset_generator.constants.RUNTIME_DATA_DIR", runtime_dir
    )
    monkeypatch.setattr(
        "imageset_generator.constants.PACKAGED_DATA_DIR", packaged_dir
    )

    result = get_data_read_path("ocp-versions.json")
    assert result == packaged_file


def test_partial_cache_falls_through_to_seed(tmp_path, monkeypatch):
    """A runtime cache with too few entries should not shadow seed data."""
    runtime_dir = tmp_path / "runtime" / "data"
    runtime_dir.mkdir(parents=True)
    packaged_dir = tmp_path / "packaged" / "data"
    packaged_dir.mkdir(parents=True)

    # Partial runtime cache (fresh but only 1 version)
    runtime_file = runtime_dir / "ocp-versions.json"
    runtime_file.write_text(
        json.dumps(
            {
                "releases": ["4.16"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    )

    packaged_file = packaged_dir / "ocp-versions.json"
    packaged_file.write_text(
        json.dumps({"releases": [f"4.{v}" for v in range(14, 23)]})
    )

    monkeypatch.setattr(
        "imageset_generator.constants.RUNTIME_DATA_DIR", runtime_dir
    )
    monkeypatch.setattr(
        "imageset_generator.constants.PACKAGED_DATA_DIR", packaged_dir
    )

    result = get_data_read_path("ocp-versions.json")
    assert result == packaged_file


def test_fresh_complete_cache_takes_priority(tmp_path, monkeypatch):
    """A fresh and complete runtime cache should take priority over seed data."""
    runtime_dir = tmp_path / "runtime" / "data"
    runtime_dir.mkdir(parents=True)
    packaged_dir = tmp_path / "packaged" / "data"
    packaged_dir.mkdir(parents=True)

    runtime_file = runtime_dir / "ocp-versions.json"
    runtime_file.write_text(
        json.dumps(
            {
                "releases": ["4.14", "4.15", "4.16", "4.17"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    )

    packaged_file = packaged_dir / "ocp-versions.json"
    packaged_file.write_text(json.dumps({"releases": ["4.14", "4.15", "4.16"]}))

    monkeypatch.setattr(
        "imageset_generator.constants.RUNTIME_DATA_DIR", runtime_dir
    )
    monkeypatch.setattr(
        "imageset_generator.constants.PACKAGED_DATA_DIR", packaged_dir
    )

    result = get_data_read_path("ocp-versions.json")
    assert result == runtime_file


def test_no_runtime_cache_uses_seed(tmp_path, monkeypatch):
    """When no runtime cache exists, seed data is returned."""
    runtime_dir = tmp_path / "runtime" / "data"
    runtime_dir.mkdir(parents=True)
    packaged_dir = tmp_path / "packaged" / "data"
    packaged_dir.mkdir(parents=True)

    packaged_file = packaged_dir / "ocp-versions.json"
    packaged_file.write_text(json.dumps({"releases": ["4.14", "4.15"]}))

    monkeypatch.setattr(
        "imageset_generator.constants.RUNTIME_DATA_DIR", runtime_dir
    )
    monkeypatch.setattr(
        "imageset_generator.constants.PACKAGED_DATA_DIR", packaged_dir
    )

    result = get_data_read_path("ocp-versions.json")
    assert result == packaged_file


# ---------------------------------------------------------------------------
# Atomic write tests
# ---------------------------------------------------------------------------


def test_atomic_json_dump_writes_valid_json(tmp_path):
    """atomic_json_dump should produce a valid, readable JSON file."""
    target = tmp_path / "test.json"
    data = {"releases": ["4.14", "4.15"], "count": 2}

    atomic_json_dump(data, target)

    assert target.exists()
    loaded = json.loads(target.read_text())
    assert loaded == data


def test_atomic_json_dump_creates_parent_dirs(tmp_path):
    """atomic_json_dump should create intermediate directories."""
    target = tmp_path / "deep" / "nested" / "dir" / "test.json"

    atomic_json_dump({"key": "value"}, target)

    assert target.exists()
    assert json.loads(target.read_text()) == {"key": "value"}


def test_atomic_json_dump_overwrites_existing(tmp_path):
    """atomic_json_dump should atomically overwrite an existing file."""
    target = tmp_path / "test.json"
    target.write_text(json.dumps({"old": True}))

    atomic_json_dump({"new": True}, target)

    assert json.loads(target.read_text()) == {"new": True}


def test_atomic_json_dump_no_temp_file_on_success(tmp_path):
    """After a successful write, no .tmp files should remain."""
    target = tmp_path / "test.json"
    atomic_json_dump({"key": "val"}, target)

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []


def test_atomic_json_dump_cleans_up_on_failure(tmp_path):
    """If serialization fails, no partial file or temp file is left."""
    target = tmp_path / "test.json"

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomic_json_dump({"bad": Unserializable()}, target)

    assert not target.exists()
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []
