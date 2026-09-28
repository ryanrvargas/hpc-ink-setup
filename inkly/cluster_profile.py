from __future__ import annotations

import fnmatch
import os
from pathlib import Path
import socket

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


PROFILE_DIR = Path(__file__).resolve().parent / "cluster_profiles"


def _load_profile(path: Path) -> dict:
    """Load one trusted cluster profile from TOML."""
    with path.open("rb") as handle:
        profile = tomllib.load(handle)

    profile["_profile_path"] = str(path)
    return profile


def resolve_cluster_profile() -> dict | None:
    """
    Find the trusted profile for the current cluster.

    Resolution order:
    1. INKLY_CLUSTER_PROFILE - explicit file path
    2. INKLY_CLUSTER_PROFILE_NAME - bundled profile name
    3. automatic hostname matching against profile host_patterns
    """
    explicit_path = os.environ.get("INKLY_CLUSTER_PROFILE", "").strip()
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if path.is_file():
            return _load_profile(path)
        return None

    explicit_name = os.environ.get("INKLY_CLUSTER_PROFILE_NAME", "").strip()
    if explicit_name:
        path = PROFILE_DIR / f"{explicit_name}.toml"
        if path.is_file():
            return _load_profile(path)
        return None

    hostname = socket.gethostname().casefold()

    for path in sorted(PROFILE_DIR.glob("*.toml")):
        try:
            profile = _load_profile(path)
        except (OSError, ValueError):
            continue

        patterns = profile.get("host_patterns", [])

        if any(
            fnmatch.fnmatch(hostname, str(pattern).casefold()) for pattern in patterns
        ):
            return profile

    return None
