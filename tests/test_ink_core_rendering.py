from types import SimpleNamespace

from inkly import ink_core


def test_deterministic_source_scoped_response_is_not_treated_as_streamed():
    response = (
        "Cluster-specific Gaussian instructions are unavailable in the current "
        "documentation database. I found external Gaussian documentation, but its "
        "commands and policies are not verified for this cluster, so I won't guess "
        "a local module, partition, path, or scheduler command."
    )
    runtime = SimpleNamespace(CLUSTER_SCOPE_WITHHELD_RESPONSE=response)

    assert ink_core._response_was_streamed(runtime, response) is False


def test_model_response_is_treated_as_streamed():
    runtime = SimpleNamespace(CLUSTER_SCOPE_WITHHELD_RESPONSE="withheld")

    assert ink_core._response_was_streamed(runtime, "model response") is True
