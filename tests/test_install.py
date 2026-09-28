import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import install


def test_install_ink_uses_current_python_interpreter(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    monkeypatch.setattr(
        install,
        "STATE_CFG",
        SimpleNamespace(bin_dir=bin_dir),
    )

    install.install_ink()

    installed_ink = bin_dir / "ink"

    assert installed_ink.exists()

    first_line = installed_ink.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == f"#!{sys.executable}"

    assert installed_ink.stat().st_mode & 0o111


def _write_fake_runtime(package_root: Path, marker: str) -> None:
    package = package_root / "inkly"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "ink_core.py").write_text(
        f"def main():\n    print({marker!r})\n    return 0\n",
        encoding="utf-8",
    )


def test_source_launcher_prefers_checkout_runtime_over_installed_copy(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    launcher = tmp_path / "checkout" / "ink"
    launcher.parent.mkdir()
    launcher.write_text(
        (repo_root / "ink").read_text(encoding="utf-8"), encoding="utf-8"
    )

    _write_fake_runtime(launcher.parent, "checkout-runtime")

    home = tmp_path / "home"
    _write_fake_runtime(home / ".inkly" / "lib", "stale-installed-runtime")

    result = subprocess.run(
        [sys.executable, str(launcher)],
        cwd=launcher.parent,
        env={"HOME": str(home)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "checkout-runtime"


def test_installed_launcher_uses_private_runtime(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    launcher = tmp_path / "bin" / "ink"
    launcher.parent.mkdir()
    launcher.write_text(
        (repo_root / "ink").read_text(encoding="utf-8"), encoding="utf-8"
    )

    home = tmp_path / "home"
    _write_fake_runtime(home / ".inkly" / "lib", "installed-runtime")

    result = subprocess.run(
        [sys.executable, str(launcher)],
        cwd=launcher.parent,
        env={"HOME": str(home)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "installed-runtime"
