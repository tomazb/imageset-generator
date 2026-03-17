import os
import subprocess
import sys
from pathlib import Path


def test_cli_package_import_does_not_require_tkinter():
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")

    result = subprocess.run(
        [sys.executable, "-c", "import imageset_generator.cli; print('ok')"],
        capture_output=True,
        text=True,
        env=env,
        cwd=project_root,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_cli_package_main_is_importable_without_preloading_launcher():
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from imageset_generator.cli import main; print(callable(main))",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=project_root,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_module_launcher_help_works_with_warning_as_error():
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-m",
            "imageset_generator.cli.launcher",
            "--cli",
            "--help",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=project_root,
    )

    assert result.returncode == 0, result.stderr
    assert "Generate OpenShift ImageSetConfiguration files" in result.stdout
    assert "--operators" in result.stdout
