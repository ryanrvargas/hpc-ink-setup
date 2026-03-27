from types import SimpleNamespace

from inkly.core.conversation import ConversationManager


def make_config(
    enabled=True,
    max_messages=4,
    summarize=True,
    summary_trigger=6,
    max_summary_chars=300,
):
    conversation = SimpleNamespace(
        enabled=enabled,
        max_messages=max_messages,
        summarize=summarize,
        summary_trigger=summary_trigger,
        max_summary_chars=max_summary_chars,
    )
    core = SimpleNamespace(max_prompt_length=1000)
    return SimpleNamespace(conversation=conversation, core=core)


def test_append_persists_full_history(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "inkly.core.conversation.Path.home",
        lambda: tmp_path,
    )

    cfg = make_config(max_messages=2)
    cm = ConversationManager(cfg)

    for i in range(5):
        cm.append_turn("user1", "user", f"q{i}")

    full_history = cm._read_full_history("user1")
    assert len(full_history) == 5


def test_load_recent_returns_last_n(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "inkly.core.conversation.Path.home",
        lambda: tmp_path,
    )

    cfg = make_config(max_messages=3)
    cm = ConversationManager(cfg)

    for i in range(5):
        cm.append_turn("user1", "user", f"q{i}")

    recent = cm.load_recent("user1")
    assert [t["content"] for t in recent] == ["q2", "q3", "q4"]


def test_summary_triggers_when_history_exceeds_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "inkly.core.conversation.Path.home",
        lambda: tmp_path,
    )

    cfg = make_config(max_messages=2, summary_trigger=4, summarize=True)
    cm = ConversationManager(cfg)

    turns = [
        ("user", "first question"),
        ("assistant", "first answer"),
        ("user", "second question"),
        ("assistant", "second answer"),
        ("user", "third question"),
    ]
    for role, content in turns:
        cm.append_turn("user1", role, content)

    lines = cm.build_context("user1")

    joined = "\n".join(lines)
    assert "[SUMMARY OF OLDER CONTEXT]" in joined
    assert "[RECENT HISTORY]" in joined
    assert "third question" in joined


def test_summary_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "inkly.core.conversation.Path.home",
        lambda: tmp_path,
    )

    cfg = make_config(max_messages=2, summary_trigger=4, summarize=False)
    cm = ConversationManager(cfg)

    for i in range(5):
        cm.append_turn("user1", "user", f"q{i}")

    lines = cm.build_context("user1")
    joined = "\n".join(lines)

    assert "[SUMMARY OF OLDER CONTEXT]" not in joined
    assert "q3" in joined
    assert "q4" in joined
    assert "q0" not in joined


def test_current_query_not_duplicated_in_context(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "inkly.core.conversation.Path.home",
        lambda: tmp_path,
    )

    cfg = make_config()
    cm = ConversationManager(cfg)

    cm.append_turn("user1", "user", "hello")
    cm.append_turn("user1", "assistant", "hi")
    cm.append_turn("user1", "user", "current question")

    lines = cm.build_context("user1", current_query="current question")
    joined = "\n".join(lines)

    assert joined.count("current question") == 0