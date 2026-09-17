from types import SimpleNamespace

from inkly.core.runtime import InklyRuntime


WITHHELD_OUTPUT = """Gaussian Documentation
Cluster-specific Gaussian instructions are unavailable in the current documentation database.
Source: Harvard RC - Gaussian | scope=external-not-verified-for-this-cluster
"""


class FakeConversationManager:
    def __init__(self, _config):
        self.appended = []

    def append_turn(self, user_id, role, content):
        self.appended.append((user_id, role, content))

    def build_context(self, *args, **kwargs):
        raise AssertionError("history should not be built for a withheld cluster answer")


class FakePlugin:
    name = "docs_gaussian"

    def run(self, _query):
        return WITHHELD_OUTPUT


class FakePluginManager:
    def discover(self):
        return {"docs_gaussian": FakePlugin()}


class FakeBackend:
    def __init__(self, _config):
        self.called = False

    def generate(self, _prompt):
        self.called = True
        raise AssertionError("LLM must not generate unverified cluster commands")


def make_config():
    return SimpleNamespace(
        conversation=SimpleNamespace(enabled=True),
        core=SimpleNamespace(max_prompt_length=8000, max_concurrent_requests=2),
        llm=SimpleNamespace(backend="github"),
    )


def test_withheld_gaussian_cluster_context_bypasses_generation(monkeypatch):
    conversation = FakeConversationManager(make_config())
    backend = FakeBackend(make_config())

    monkeypatch.setattr(
        "inkly.core.runtime.ConversationManager", lambda _cfg: conversation
    )
    monkeypatch.setattr("inkly.core.runtime.PluginManager", FakePluginManager)
    monkeypatch.setattr("inkly.core.runtime.LLMBackend", lambda _cfg: backend)

    runtime = InklyRuntime(make_config())
    response = runtime.handle_query("user1", "How do I run Gaussian on Cuttlefish?")

    assert "instructions are unavailable" in response
    assert "not verified for this cluster" in response
    assert "module load" not in response
    assert "sbatch" not in response
    assert "srun" not in response
    assert backend.called is False
    assert conversation.appended[-1] == ("user1", "assistant", response)


def test_source_scoping_helper_does_not_block_normal_gaussian_context(monkeypatch):
    monkeypatch.setattr(
        "inkly.core.runtime.ConversationManager", FakeConversationManager
    )
    monkeypatch.setattr("inkly.core.runtime.PluginManager", FakePluginManager)
    monkeypatch.setattr("inkly.core.runtime.LLMBackend", FakeBackend)

    runtime = InklyRuntime(make_config())

    assert (
        runtime._source_scoped_response(
            {"docs_gaussian": "Gaussian is a quantum chemistry package."}
        )
        is None
    )
