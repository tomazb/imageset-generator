from pathlib import Path
import subprocess
import sys


def test_launcher_can_run_directly_in_cli_mode(tmp_path):
    launcher_path = Path(__file__).resolve().parents[2] / "src" / "imageset_generator" / "cli" / "launcher.py"
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
