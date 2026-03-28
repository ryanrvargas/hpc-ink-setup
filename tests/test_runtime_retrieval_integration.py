from __future__ import annotations

from types import SimpleNamespace

from inkly.core.runtime import InklyRuntime
from inkly.plugins.manager import Plugin


class FakeConversation:
    def __init__(self):
        self.turns = []

    def append_turn(self, user_id, role, content):
        self.turns.append((user_id, role, content))

    def build_context(self, user_id, *, current_query=None, max_prompt_length=None):
        return ["assistant: prior context"]


class FakeBackend:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "ok"


class FakeRetriever:
    def __init__(self, selected_names):
        self.selected_names = selected_names

    def select_plugins(self, query, discovered):
        return [discovered[name] for name in self.selected_names]


class FakePluginManager:
    def __init__(self, plugins):
        self._plugins = plugins

    def discover(self):
        return self._plugins


def make_config(tmp_path):
    conversation = SimpleNamespace(enabled=True, max_messages=4, summarize=True, summary_trigger=6, max_summary_chars=300)
    core = SimpleNamespace(max_concurrent_requests=2, max_prompt_length=4000)
    llm = SimpleNamespace(backend="github", model="dummy")
    retrieval = SimpleNamespace(
        enabled=True,
        top_k=2,
        min_score=0.0,
        fallback_to_all_plugins=True,
        index_path=str(tmp_path / "retrieval.json"),
    )
    return SimpleNamespace(conversation=conversation, core=core, llm=llm, retrieval=retrieval)


def test_runtime_executes_only_selected_plugins(tmp_path):
    cfg = make_config(tmp_path)
    runtime = InklyRuntime(cfg)

    called = []

    def run_jobs():
        called.append("jobs_summary")
        return "jobs output"

    def run_queue():
        called.append("queue_status")
        return "queue output"

    def run_docs():
        called.append("docs_gaussian")
        return "docs output"

    plugins = {
        "jobs_summary": Plugin("jobs_summary", "job stats", "job-history", ["why did jobs fail"], run_jobs),
        "queue_status": Plugin("queue_status", "queue status", "queue-status", ["how busy is queue"], run_queue),
        "docs_gaussian": Plugin("docs_gaussian", "gaussian docs", "documentation", ["gaussian help"], run_docs),
    }

    runtime.conversation = FakeConversation()
    runtime.backend = FakeBackend()
    runtime.plugins = FakePluginManager(plugins)
    runtime.retriever = FakeRetriever(["queue_status", "docs_gaussian"])

    response = runtime.handle_query("user1", "How busy is the queue and where are Gaussian docs?")

    assert response == "ok"
    assert called == ["queue_status", "docs_gaussian"]
    prompt = runtime.backend.prompts[0]
    assert "[queue_status]" in prompt
    assert "[docs_gaussian]" in prompt
    assert "[jobs_summary]" not in prompt
