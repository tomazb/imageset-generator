from pathlib import Path
import subprocess
import sys
import zipfile


def test_wheel_includes_runtime_assets(tmp_path):
    project_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(project_root),
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert result.returncode == 0, result.stderr

    wheel_path = next(tmp_path.glob("imageset_generator-*.whl"))
    with zipfile.ZipFile(wheel_path) as wheel_file:
        names = set(wheel_file.namelist())

    assert "imageset_generator/frontend/build/index.html" in names
    assert any(
        name.startswith("imageset_generator/frontend/build/static/js/")
        for name in names
    )
    assert any(
        name.startswith("imageset_generator/frontend/build/static/css/")
        for name in names
    )
    assert "imageset_generator/data/ocp-versions.json" in names
    assert "imageset_generator/automation/config.yaml" in names
