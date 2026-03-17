import subprocess
import sys
from pathlib import Path


def test_launcher_can_run_directly_in_cli_mode(tmp_path):
    launcher_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "imageset_generator"
        / "cli"
        / "launcher.py"
    )
    output_path = tmp_path / "generated-imageset.yaml"

    result = subprocess.run(
        [
            sys.executable,
            str(launcher_path),
            "--cli",
            "--operators",
            "logging",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    assert "Generated ImageSetConfiguration" in result.stdout


def test_launcher_forwards_cli_help_when_run_directly():
    launcher_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "imageset_generator"
        / "cli"
        / "launcher.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(launcher_path),
            "--cli",
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Generate OpenShift ImageSetConfiguration files" in result.stdout
    assert "--operators" in result.stdout


def test_launcher_shows_wrapper_help_without_cli_flag():
    launcher_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "imageset_generator"
        / "cli"
        / "launcher.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(launcher_path),
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "OpenShift ImageSetConfiguration Generator" in result.stdout
    assert "For CLI options, use: imageset-generator --cli --help" in result.stdout
