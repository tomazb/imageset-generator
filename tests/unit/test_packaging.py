import shutil
from pathlib import Path
import subprocess
import sys
import zipfile


def test_wheel_includes_runtime_assets(tmp_path):
    project_root = Path(__file__).resolve().parents[2]

    uv = shutil.which("uv")
    if uv:
        result = subprocess.run(
            [uv, "build", "--wheel", "--out-dir", str(tmp_path)],
            capture_output=True, text=True, cwd=project_root,
        )
    else:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", str(project_root),
             "--no-deps", "--no-build-isolation",
             "--wheel-dir", str(tmp_path)],
            capture_output=True, text=True, cwd=project_root,
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


def test_containerfile_uses_disconnected_safe_local_install():
    project_root = Path(__file__).resolve().parents[2]
    containerfile = (project_root / "Containerfile").read_text()

    assert "python3.11 -m pip install --no-cache-dir --no-build-isolation --no-deps ." in containerfile


def test_ci_workflows_use_non_isolated_editable_installs():
    project_root = Path(__file__).resolve().parents[2]
    test_workflow = (project_root / ".github" / "workflows" / "test.yml").read_text()
    quality_workflow = (project_root / ".github" / "workflows" / "quality.yml").read_text()

    assert "pip install --no-build-isolation --no-deps -e ." in test_workflow
    assert "pip install -r requirements.txt" in quality_workflow
    assert "pip install --no-build-isolation --no-deps -e ." in quality_workflow


def test_editable_install_succeeds_without_build_isolation(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    venv_dir = tmp_path / "venv"

    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)],
        check=True,
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    install_result = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "--no-deps",
            "-e",
            str(project_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert install_result.returncode == 0, install_result.stderr

    import_result = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            "import imageset_generator; print(imageset_generator.__file__)",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert import_result.returncode == 0, import_result.stderr
    assert import_result.stdout.strip().endswith("src/imageset_generator/__init__.py")
