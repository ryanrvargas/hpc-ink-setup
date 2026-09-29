import inkly.plugins.cluster_profile as plugin


def profile():
    return {
        "name": "Cuttlefish",
        "scheduler": "slurm",
        "software": {
            "gaussian": {
                "installed": True,
                "runtime_verified": True,
                "runtime_verified_on": "2026-09-29",
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
                "slurm": {
                    "verified_partition": "general",
                    "cpu_hint": "nomultithread",
                    "cpu_selection": (
                        "one logical CPU per unique physical core from the allocated cpuset"
                    ),
                    "cpu_launch": "g16 -c=<selected_cpu_ids>",
                    "memory_enforced_by_cgroup": True,
                    "auto_memory_fraction": 0.75,
                    "memory_rounding": "down",
                    "validated_slurm_memory_mib": 1024,
                    "validated_gaussian_memory_mib": 800,
                    "validated_memory_workloads": ["test0983", "test0400"],
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
    assert "VERIFIED_RUNTIME" in output
    assert "runtime execution has been verified" in output
    assert "Verified Gaussian Slurm partition: general" in output
    assert "--cpus-per-task=N" in output
    assert "--hint=nomultithread" in output
    assert "g16 -c=<selected_cpu_ids>" in output
    assert "75% of Slurm --mem" in output
    assert "never set %mem equal" in output
    assert "test0983" in output
    assert "test0400" in output


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
