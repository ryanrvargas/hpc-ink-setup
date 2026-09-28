from inkly.plugins.manager import _query_aware_run


def test_query_aware_run_preserves_legacy_zero_arg_plugin_behavior():
    calls = []

    def legacy_run():
        calls.append("called")
        return "legacy output"

    run = _query_aware_run(legacy_run)

    assert run("current user query") == "legacy output"
    assert calls == ["called"]


def test_query_aware_run_passes_query_to_query_aware_plugin():
    queries = []

    def query_run(query):
        queries.append(query)
        return f"result for {query}"

    run = _query_aware_run(query_run)

    assert run("Gaussian memory failure") == "result for Gaussian memory failure"
    assert queries == ["Gaussian memory failure"]
