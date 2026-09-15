import sys
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
