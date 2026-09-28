from types import SimpleNamespace

from inkly.core.runtime import InklyRuntime


DOCS_OUTPUT = """Gaussian Documentation
Cluster-specific Gaussian instructions are unavailable in the current documentation database.
Source: Harvard RC - Gaussian | scope=external-not-verified-for-this-cluster
"""

LOCAL_OUTPUT = """Trusted Cluster Profile
scope=verified-local-cluster
Cluster: Cuttlefish
Scheduler: slurm
evidence=VERIFIED_CONFIG | Advertised default Gaussian module: gaussian/avx2/g16_rev_c02
evidence=VERIFIED_CONFIG | Gaussian access group: gaussian
evidence=BLOCKED_BY_ACCESS | Current user testuser is not a member of gaussian; do not describe Gaussian as runnable for this user.
"""


class FakeConversation:
    def __init__(self, _config):
        self.appended = []

    def append_turn(self, user_id, role, content):
        self.appended.append((user_id, role, content))

    def build_context(self, *_args, **_kwargs):
        return []


class FakePlugin:
    def __init__(self, name, output):
        self.name = name
        self.output = output
        self.queries = []

    def run(self, query):
        self.queries.append(query)
        return self.output


class FakePluginManager:
    def __init__(self):
        self.docs = FakePlugin("docs_gaussian", DOCS_OUTPUT)
        self.local = FakePlugin("cluster_profile", LOCAL_OUTPUT)

    def discover(self):
        return {
            "docs_gaussian": self.docs,
            "cluster_profile": self.local,
        }


class MissEverythingRetriever:
    def select_plugins(self, _query, _plugins):
        return []


class FakeBackend:
    def __init__(self, _config):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return "model response"


def make_config():
    return SimpleNamespace(
        conversation=SimpleNamespace(enabled=True),
        core=SimpleNamespace(
            max_prompt_length=8000,
            max_concurrent_requests=2,
        ),
        llm=SimpleNamespace(backend="github"),
        retrieval=SimpleNamespace(
            enabled=True,
            index_path="unused.json",
            top_k=3,
            min_score=0.01,
            fallback_to_all_plugins=False,
        ),
    )


def install_fakes(monkeypatch):
    config = make_config()
    conversation = FakeConversation(config)
    manager = FakePluginManager()
    backend = FakeBackend(config)

    monkeypatch.setattr(
        "inkly.core.runtime.ConversationManager",
        lambda _cfg: conversation,
    )
    monkeypatch.setattr(
        "inkly.core.runtime.PluginManager",
        lambda: manager,
    )
    monkeypatch.setattr(
        "inkly.core.runtime.LLMBackend",
        lambda _cfg: backend,
    )

    runtime = InklyRuntime(config)
    runtime.retriever = MissEverythingRetriever()

    return runtime, manager, backend


def test_blocked_gaussian_action_bypasses_generation(monkeypatch):
    runtime, manager, backend = install_fakes(monkeypatch)

    response = runtime.handle_query(
        "user1",
        "Which Gaussian module should I load on Cuttlefish?",
    )

    assert "blocked for your account" in response
    assert "`gaussian`" in response
    assert "gaussian/avx2/g16_rev_c02" in response
    assert "configuration evidence" in response
    assert "runnable" in response

    assert manager.docs.queries
    assert manager.local.queries
    assert backend.prompts == []


def test_blocked_gaussian_sbatch_request_bypasses_generation(monkeypatch):
    runtime, _, backend = install_fakes(monkeypatch)

    response = runtime.handle_query(
        "user1",
        "Create an sbatch file for running Gaussian on Cuttlefish.",
    )

    assert "blocked for your account" in response
    assert "runnable SBATCH" in response
    assert backend.prompts == []


def test_local_informational_query_can_still_use_model(monkeypatch):
    runtime, manager, backend = install_fakes(monkeypatch)

    response = runtime.handle_query(
        "user1",
        "Where should Gaussian scratch files go on Cuttlefish?",
    )

    assert response == "model response"
    assert manager.docs.queries
    assert manager.local.queries
    assert backend.prompts

    prompt = backend.prompts[0]

    assert "scope=external-not-verified-for-this-cluster" in prompt
    assert "scope=verified-local-cluster" in prompt
    assert "BLOCKED_BY_ACCESS" in prompt


def test_withheld_external_docs_do_not_hard_stop_when_trusted_local_exists():
    runtime = InklyRuntime(make_config())

    response = runtime._source_scoped_response(
        {
            "docs_gaussian": DOCS_OUTPUT,
            "cluster_profile": LOCAL_OUTPUT,
        },
        query="Where should Gaussian scratch files go on Cuttlefish?",
    )

    assert response is None
