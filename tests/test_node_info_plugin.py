from __future__ import annotations

from inkly.plugins import node_info


def test_run_reports_partition_resources(monkeypatch):
    def fake_command_exists(cmd: str) -> bool:
        return cmd == "sinfo"

    def fake_run_capture(cmd: list[str]) -> str | None:
        if cmd == ["sinfo", "-h", "-o", "%P|%D|%c|%m|%G"]:
            return (
                "general|10|32|128000|(null)\n"
                "gpu|4|64|256000|gpu:4"
            )
        return None

    monkeypatch.setattr(node_info, "_command_exists", fake_command_exists)
    monkeypatch.setattr(node_info, "_run_capture", fake_run_capture)

    output = node_info.run()

    assert "Node / Partition Information" in output
    assert "Partitions and resources:" in output
    assert "- general: 10 nodes, 32 CPUs/node, 128000 MB/node, GPUs: This partition has no GPUs." in output
    assert "- gpu: 4 nodes, 64 CPUs/node, 256000 MB/node, GPUs: gpu:4" in output


def test_run_handles_missing_sinfo(monkeypatch):
    monkeypatch.setattr(node_info, "_command_exists", lambda cmd: False)

    output = node_info.run()

    assert "Node / Partition Information" in output
    assert "Partitions and resources:" in output
    assert "Node information unavailable: sinfo not found." in output


def test_run_handles_unparseable_sinfo_output(monkeypatch):
    def fake_command_exists(cmd: str) -> bool:
        return cmd == "sinfo"

    def fake_run_capture(cmd: list[str]) -> str | None:
        if cmd == ["sinfo", "-h", "-o", "%P|%D|%c|%m|%G"]:
            return "bad output with no separators"
        return None

    monkeypatch.setattr(node_info, "_command_exists", fake_command_exists)
    monkeypatch.setattr(node_info, "_run_capture", fake_run_capture)

    output = node_info.run()

    assert "Node / Partition Information" in output
    assert "Node information unavailable: could not parse sinfo output." in output