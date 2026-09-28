import inkly.plugins.cluster_profile as plugin


def profile():
    return {
        "name": "Cuttlefish",
        "scheduler": "slurm",
        "software": {
            "gaussian": {
                "installed": True,
                "runtime_verified": False,
                "access_group": "gaussian",
                "modules": [
                    "gaussian/avx2/g16_rev_c01",
                    "gaussian/avx2/g16_rev_c02",
                ],
                "advertised_default_module": "gaussian/avx2/g16_rev_c02",
                "scratch_template": "/scratch/gaussian/{user}",
                "c02_environment": {
                    "g16root": "/opt/software/gaussian/avx2/rev_c02",
                    "omp_num_threads": 1,
                },
            }
        },
    }


def test_gaussian_profile_reports_blocked_user(monkeypatch):
    monkeypatch.setattr(plugin, "resolve_cluster_profile", profile)
    monkeypatch.setattr(plugin.getpass, "getuser", lambda: "testuser")
    monkeypatch.setattr(
        plugin,
        "_user_in_group",
        lambda _group, _username: False,
    )

    output = plugin.run("How do I run Gaussian on Cuttlefish?")

    assert "scope=verified-local-cluster" in output
    assert "Cluster: Cuttlefish" in output
    assert "BLOCKED_BY_ACCESS" in output
    assert "gaussian/avx2/g16_rev_c02" in output
    assert "/scratch/gaussian/testuser" in output
    assert "Successful Gaussian runtime execution has not yet been verified" in output


def test_gaussian_profile_reports_satisfied_group_prerequisite(monkeypatch):
    monkeypatch.setattr(plugin, "resolve_cluster_profile", profile)
    monkeypatch.setattr(plugin.getpass, "getuser", lambda: "testuser")
    monkeypatch.setattr(
        plugin,
        "_user_in_group",
        lambda _group, _username: True,
    )

    output = plugin.run("Which Gaussian module should I use?")

    assert "scope=verified-local-cluster" in output
    assert "VERIFIED_ACCESS" in output
    assert "group-access prerequisite" in output
    assert "BLOCKED_BY_ACCESS" not in output


def test_no_profile_does_not_emit_trusted_scope(monkeypatch):
    monkeypatch.setattr(plugin, "resolve_cluster_profile", lambda: None)

    output = plugin.run("How do I run Gaussian?")

    assert "scope=verified-local-cluster" not in output
    assert "No trusted local cluster profile matched" in output
