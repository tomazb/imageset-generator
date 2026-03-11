import os
from pathlib import Path
import subprocess
import sys


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
