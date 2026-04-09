from types import SimpleNamespace

from inkly.core.runtime import InklyRuntime


def make_config(max_prompt_length=1000, max_concurrent_requests=2):
    conversation = SimpleNamespace(
        enabled=True,
        max_messages=4,
        summarize=True,
        summary_trigger=6,
        max_summary_chars=300,
    )
    core = SimpleNamespace(
        max_prompt_length=max_prompt_length,
        max_concurrent_requests=max_concurrent_requests,
    )
    llm = SimpleNamespace(backend="github")
    return SimpleNamespace(conversation=conversation, core=core, llm=llm)


class FakeConversationManager:
    def __init__(self, config):
        self.config = config
        self.appended = []
        self.build_context_calls = []

    def append_turn(self, user_id, role, content):
        self.appended.append((user_id, role, content))

    def build_context(self, user_id, current_query=None, max_prompt_length=None):
        self.build_context_calls.append((user_id, current_query, max_prompt_length))
        return [
            "[SUMMARY OF OLDER CONTEXT]",
            "- user: asked about failures",
            "",
            "[RECENT HISTORY]",
            "assistant: previous answer",
        ]


class FakePlugin:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error

    def run(self):
        if self.error is not None:
            raise self.error
        return self.output


class FakePluginManager:
    def __init__(self, plugins=None):
        self._plugins = plugins or {}

    def discover(self):
        return self._plugins


class FakeBackend:
    def __init__(self, response="mock response", raise_error=None):
        self.response = response
        self.raise_error = raise_error
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if self.raise_error is not None:
            raise self.raise_error
        return self.response


def make_runtime(monkeypatch, config=None):
    config = config or make_config()

    conversation = FakeConversationManager(config)
    plugins = FakePluginManager(
        {
            "jobs_summary": FakePlugin("cluster looks healthy"),
            "broken_plugin": FakePlugin(error=RuntimeError("boom")),
        }
    )
    backend = FakeBackend("final answer")

    monkeypatch.setattr(
        "inkly.core.runtime.ConversationManager",
        lambda cfg: conversation,
    )
    monkeypatch.setattr(
        "inkly.core.runtime.PluginManager",
        lambda: plugins,
    )
    monkeypatch.setattr(
        "inkly.core.runtime.LLMBackend",
        lambda cfg: backend,
    )

    runtime = InklyRuntime(config)
    return runtime, conversation, plugins, backend


def test_handle_query_builds_prompt_with_history_plugins_and_query(monkeypatch):
    runtime, conversation, _, backend = make_runtime(monkeypatch)

    response = runtime.handle_query("user1", "Why are jobs failing?")

    assert response == "final answer"

    assert conversation.appended[0] == (
        "user1",
        "user",
        "Why are jobs failing?",
    )
    assert conversation.appended[-1] == (
        "user1",
        "assistant",
        "final answer",
    )

    assert conversation.build_context_calls == [
        ("user1", "Why are jobs failing?", runtime.config.core.max_prompt_length // 2)
    ]

    prompt = backend.prompts[0]
    assert "=== CONVERSATION HISTORY ===" in prompt
    assert "[SUMMARY OF OLDER CONTEXT]" in prompt
    assert "=== PLUGIN CONTEXT ===" in prompt
    assert "[jobs_summary]" in prompt
    assert "cluster looks healthy" in prompt
    assert "[broken_plugin]" in prompt
    assert "Plugin error: boom" in prompt
    assert "=== USER QUERY ===" in prompt
    assert "Why are jobs failing?" in prompt


def test_handle_query_does_not_duplicate_current_query_in_history(monkeypatch):
    runtime, _, _, backend = make_runtime(monkeypatch)

    runtime.handle_query("user1", "Why are jobs failing?")

    prompt = backend.prompts[0]

    assert prompt.count("Why are jobs failing?") == 1


def test_handle_query_trims_prompt_to_max_length(monkeypatch):
    config = make_config(max_prompt_length=120)

    runtime, _, _, backend = make_runtime(monkeypatch, config=config)

    runtime.handle_query("user1", "Why are jobs failing?")

    prompt = backend.prompts[0]
    assert len(prompt) <= 120


def test_handle_query_records_backend_failure_in_history(monkeypatch):
    config = make_config()

    conversation = FakeConversationManager(config)
    plugins = FakePluginManager({"jobs_summary": FakePlugin("ok")})
    backend = FakeBackend(raise_error=RuntimeError("backend down"))

    monkeypatch.setattr(
        "inkly.core.runtime.ConversationManager",
        lambda cfg: conversation,
    )
    monkeypatch.setattr(
        "inkly.core.runtime.PluginManager",
        lambda: plugins,
    )
    monkeypatch.setattr(
        "inkly.core.runtime.LLMBackend",
        lambda cfg: backend,
    )

    runtime = InklyRuntime(config)

    try:
        runtime.handle_query("user1", "test query")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == "backend down"

    assert conversation.appended[0] == ("user1", "user", "test query")
    assert conversation.appended[-1] == (
        "user1",
        "assistant",
        "Backend error: backend down",
    )


def test_build_prompt_omits_empty_sections(monkeypatch):
    runtime, _, _, _ = make_runtime(monkeypatch)

    prompt = runtime._build_prompt([], {}, "Just answer this")
    assert "=== INKLY RESPONSE CONTRACT ===" in prompt
    assert "You are Inkly, an HPC assistant for a Slurm-based cluster." in prompt
    assert "=== CONVERSATION HISTORY ===" not in prompt
    assert "=== PLUGIN CONTEXT ===" not in prompt
    assert "=== USER QUERY ===" in prompt
    assert "Just answer this" in prompt
