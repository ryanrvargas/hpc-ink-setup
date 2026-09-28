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
        raise AssertionError(
            "history should not be built for a withheld cluster answer"
        )


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


class MissEverythingRetriever:
    def select_plugins(self, _query, _plugins):
        return []


def make_config(*, retrieval_enabled=False):
    return SimpleNamespace(
        conversation=SimpleNamespace(enabled=True),
        core=SimpleNamespace(max_prompt_length=8000, max_concurrent_requests=2),
        llm=SimpleNamespace(backend="github"),
        retrieval=SimpleNamespace(
            enabled=retrieval_enabled,
            index_path="unused.json",
            top_k=3,
            min_score=0.01,
            fallback_to_all_plugins=False,
        ),
    )


def install_runtime_fakes(monkeypatch, conversation, backend):
    monkeypatch.setattr(
        "inkly.core.runtime.ConversationManager", lambda _cfg: conversation
    )
    monkeypatch.setattr("inkly.core.runtime.PluginManager", FakePluginManager)
    monkeypatch.setattr("inkly.core.runtime.LLMBackend", lambda _cfg: backend)


def test_withheld_gaussian_cluster_context_bypasses_generation(monkeypatch):
    conversation = FakeConversationManager(make_config())
    backend = FakeBackend(make_config())
    install_runtime_fakes(monkeypatch, conversation, backend)

    runtime = InklyRuntime(make_config())
    response = runtime.handle_query("user1", "How do I run Gaussian on Cuttlefish?")

    assert "instructions are unavailable" in response
    assert "not verified for this cluster" in response
    assert "module load" not in response
    assert "sbatch" not in response
    assert "srun" not in response
    assert backend.called is False
    assert conversation.appended[-1] == ("user1", "assistant", response)


def test_cluster_gaussian_query_forces_docs_plugin_after_retrieval_miss(monkeypatch):
    config = make_config(retrieval_enabled=True)
    conversation = FakeConversationManager(config)
    backend = FakeBackend(config)
    install_runtime_fakes(monkeypatch, conversation, backend)

    runtime = InklyRuntime(config)
    runtime.retriever = MissEverythingRetriever()
    response = runtime.handle_query("user1", "How do I run Gaussian on this cluster?")

    assert "instructions are unavailable" in response
    assert "not verified for this cluster" in response
    assert backend.called is False


def test_named_cuttlefish_gaussian_query_forces_docs_plugin_after_retrieval_miss(
    monkeypatch,
):
    config = make_config(retrieval_enabled=True)
    conversation = FakeConversationManager(config)
    backend = FakeBackend(config)
    install_runtime_fakes(monkeypatch, conversation, backend)

    runtime = InklyRuntime(config)
    runtime.retriever = MissEverythingRetriever()
    response = runtime.handle_query("user1", "How do I run Gaussian on Cuttlefish?")

    assert "instructions are unavailable" in response
    assert "not verified for this cluster" in response
    assert backend.called is False


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
