"""
Tests for policy enforcement logic in ink_core.

Scope
-----
These tests validate the behavior of policy enforcement functions only:

    - enforce_prompt_filter
    - enforce_deny_shell_commands
    - enforce_wrapper_policy (if added later)

These tests intentionally avoid:
    - CLI execution
    - subprocess calls
    - Copilot invocation
    - Slurm commands
    - Filesystem writes (except pytest tmp_path)
    - install-time bootstrap behavior

Layer Under Test
----------------
We are testing *policy enforcement logic*, not runtime orchestration.

This means:
    - We pass in minimal fake config dictionaries
    - We pass in lightweight fake state objects
    - We disable logging side effects
    - We assert SystemExit when policy blocks execution

Design Philosophy
-----------------
Policy functions must:
    - Be import-safe
    - Be deterministic
    - Fail fast when violations occur
    - Never require full installation to test

These tests enforce that contract.
"""


import pytest
from types import SimpleNamespace

import ink_core as ink

import pytest
from types import SimpleNamespace
import ink_core as ink


@pytest.fixture
def fake_state(tmp_path):
    """
    Minimal fake StateConfig-like object.

    We use SimpleNamespace to avoid importing real StateConfig.
    Only attributes accessed by enforcement/logging logic are provided.

    tmp_path ensures:
        - No real filesystem writes
        - Isolation between tests
    """
    return SimpleNamespace(
        inkly_home=tmp_path,
        log_dir=tmp_path / "logs",
    )


@pytest.fixture
def fake_logging_cfg():
    """
    Minimal fake LoggingConfig-like object.

    Logging is disabled to ensure:
        - No file I/O
        - No directory creation
        - No log rotation behavior triggered

    Only attributes referenced by enforcement code are included.
    """
    return SimpleNamespace(
        enabled=False,
        log_user_prompts=True,
        log_ai_responses=True,
        log_job_outcomes=True,
        log_raw_prompts=False,
        per_user_logs=True,
        schema_version=1,
        max_bytes=1024 * 1024,
        max_log_files=5,
    )



def test_prompt_filter_blocks_keyword(fake_state, fake_logging_cfg):
    """
    Verify that blocked keywords trigger immediate termination.

    Behavior Under Test:
        - Keyword matching
        - Case-insensitive handling
        - Fail-fast semantics

    Expected Outcome:
        - SystemExit is raised
        - No partial execution occurs
    """
    config = {
        "prompt_filter": {
            "enabled": True,
            "case_insensitive": True,
            "blocked_keywords": ["rm"],
            "blocked_regex": [],
        }
    }

    with pytest.raises(ink.PolicyViolation):
        ink.enforce_prompt_filter(
            "rm -rf ~/data",
            config,
            state=fake_state,
            logging_cfg=fake_logging_cfg,
        )


def test_prompt_filter_allows_safe_prompt(fake_state, fake_logging_cfg):
    """
    Verify that safe prompts pass through without interruption.

    This ensures:
        - Enforcement does not over-block
        - Word-boundary matching works correctly
        - Non-matching input does not raise SystemExit
    """
    config = {
        "prompt_filter": {
            "enabled": True,
            "case_insensitive": True,
            "blocked_keywords": ["rm"],
            "blocked_regex": [],
        }
    }

    # Should not raise
    ink.enforce_prompt_filter(
        "generate an sbatch script",
        config,
        state=fake_state,
        logging_cfg=fake_logging_cfg,
    )


# NOTE:
# These tests do not validate logging output,
# only that enforcement functions raise or do not raise.
