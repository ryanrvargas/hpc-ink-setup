from pathlib import Path

import inkly.cluster_profile as cluster_profile


def test_profile_is_selected_from_hostname(tmp_path, monkeypatch):
    profile_path = tmp_path / "cuttlefish.toml"
    profile_path.write_text(
        """
schema_version = 1
name = "Cuttlefish"
host_patterns = ["cuttlefish*"]
scheduler = "slurm"
"""
    )

    monkeypatch.delenv("INKLY_CLUSTER_PROFILE", raising=False)
    monkeypatch.delenv("INKLY_CLUSTER_PROFILE_NAME", raising=False)
    monkeypatch.setattr(cluster_profile, "PROFILE_DIR", tmp_path)
    monkeypatch.setattr(
        cluster_profile.socket,
        "gethostname",
        lambda: "cuttlefish",
    )

    profile = cluster_profile.resolve_cluster_profile()

    assert profile is not None
    assert profile["name"] == "Cuttlefish"
    assert profile["scheduler"] == "slurm"


def test_explicit_profile_path_overrides_hostname(tmp_path, monkeypatch):
    profile_path = tmp_path / "custom.toml"
    profile_path.write_text(
        """
schema_version = 1
name = "CustomCluster"
host_patterns = []
scheduler = "slurm"
"""
    )

    monkeypatch.setenv("INKLY_CLUSTER_PROFILE", str(profile_path))
    monkeypatch.setattr(
        cluster_profile.socket,
        "gethostname",
        lambda: "something-else",
    )

    profile = cluster_profile.resolve_cluster_profile()

    assert profile is not None
    assert profile["name"] == "CustomCluster"
    assert Path(profile["_profile_path"]) == profile_path
