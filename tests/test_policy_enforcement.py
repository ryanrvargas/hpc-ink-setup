"""
Tests for policy enforcement logic in ink_core.

Overview
--------
This module contains unit tests for Inkly's *policy enforcement layer*.

We explicitly test deterministic guardrail behavior implemented in:

    - enforce_prompt_filter
    - enforce_deny_shell_commands
    - enforce_wrapper_policy
    - enforce_network_policy

These tests validate safety-critical logic that executes *before*
Copilot invocation or any runtime side effects

These tests intentionally avoid:
    - CLI execution
    - subprocess calls
    - Copilot invocation
    - Slurm commands
    - Full runtime orchestration
    - Filesystem writes (except pytest tmp_path)
    - install-time bootstrap behavior

Layer Under Test
----------------
We are testing *policy enforcement logic*, not runtime orchestration.

This means:
    - We pass in minimal fake config dictionaries
    - We pass in lightweight fake state objects
    - We disable logging side effects

Design Philosophy
-----------------
Policy functions must:
    - Be import-safe
    - Be deterministic
    - Fail fast when violations occur
    - Never require full installation to test
    - Raise PolicyViolation (never SystemExit)
    - Avoid requiring full installation to test

These tests enforce that contract.
"""

import os
import shutil
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
    Why?
        - Keep tests lightweight
        - Avoid installation coupling
        - Maintain isolation
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
        - No file creation
        - No directory creation
        - No log rotation behavior triggered
        - No permission changes

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
    Verify that blocked keywords trigger PolicyViolation.

    Behavior Under Test:
        - Keyword matching
        - Case-insensitive handling
        - Word-boundary matching
        - Fail-fast semantics

    Expected Outcome:
        - PolicyViolation is raised
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

def test_prompt_filter_disabled_allows_everything(fake_state, fake_logging_cfg):
    """
    Validate early-return behavior when filtering is disabled.

    Even if a blocked keyword is present, enforcement must not trigger.
    """
    config = {
        "prompt_filter": {
            "enabled": False,
            "case_insensitive": True,
            "blocked_keywords": ["rm"],
            "blocked_regex": [],
        }
    }

    # Should not raise even though keyword present
    ink.enforce_prompt_filter(
        "rm -rf /",
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
        - Non-matching input does not raise PolicyViolation
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

def test_prompt_filter_case_sensitive(fake_state, fake_logging_cfg):
    """
    Validate case-sensitive mode behavior.

    When case_insensitive=False, uppercase variants should not match.
    """
    config = {
        "prompt_filter": {
            "enabled": True,
            "case_insensitive": False,
            "blocked_keywords": ["rm"],
            "blocked_regex": [],
        }
    }

    # Uppercase RM should NOT match
    ink.enforce_prompt_filter(
        "RM -rf /",
        config,
        state=fake_state,
        logging_cfg=fake_logging_cfg,
    )


def test_prompt_filter_blocks_regex(fake_state, fake_logging_cfg):
    """
    Validate regex-based blocking rules.

    Covers:
        - Regex evaluation branch
        - Pattern-based enforcement
    """
    config = {
        "prompt_filter": {
            "enabled": True,
            "case_insensitive": False,
            "blocked_keywords": [],
            "blocked_regex": [r"rm\s+-rf"],
        }
    }

    with pytest.raises(ink.PolicyViolation):
        ink.enforce_prompt_filter(
            "rm -rf /tmp",
            config,
            state=fake_state,
            logging_cfg=fake_logging_cfg,
        )

def test_deny_shell_command_blocks(fake_state, fake_logging_cfg):
    """
    Validate that deny_shell_commands triggers PolicyViolation.

    Covers:
        - Pattern matching with wildcards
        - Multiple blocked commands
    """
    config = {
        "copilot": {
            "guardrails": {
                "deny_shell_commands": ["rm:*", "sudo:*"]
            }
        }
    }

    with pytest.raises(ink.PolicyViolation):
        ink.enforce_deny_shell_commands(
            "rm -rf /",
            config,
            state=fake_state,
            logging_cfg=fake_logging_cfg,
        )


def test_deny_shell_command_allows_safe(fake_state, fake_logging_cfg):
    """
    Ensure non-denied commands pass enforcement.
    """
    config = {
        "copilot": {
            "guardrails": {
                "deny_shell_commands": ["rm:*"]
            }
        }
    }

    ink.enforce_deny_shell_commands(
        "echo hello",
        config,
        state=fake_state,
        logging_cfg=fake_logging_cfg,
    )


def test_deny_shell_with_semicolon(fake_state, fake_logging_cfg):
    """
    Validate detection of dangerous commands embedded in compound statements.
    """
    config = {
        "copilot": {
            "guardrails": {
                "deny_shell_commands": ["rm:*"]
            }
        }
    }

    with pytest.raises(ink.PolicyViolation):
        ink.enforce_deny_shell_commands(
            "echo hi; rm -rf /",
            config,
            state=fake_state,
            logging_cfg=fake_logging_cfg,
        )


def test_wrapper_requires_login(monkeypatch, fake_state, fake_logging_cfg):
    """
    Validate authentication requirement enforcement.
    """
    monkeypatch.delenv("COPILOT_AUTHENTICATED", raising=False)

    config = {
        "wrapper": {
            "require_login": True,
            "fail_on_missing_copilot": False,
        }
    }

    with pytest.raises(ink.PolicyViolation):
        ink.enforce_wrapper_policy(
            config,
            state=fake_state,
            logging_cfg=fake_logging_cfg,
        )


def test_wrapper_missing_copilot(monkeypatch, fake_state, fake_logging_cfg):
    """
    Validate enforcement when Copilot CLI is unavailable.
    """
    monkeypatch.setenv("COPILOT_AUTHENTICATED", "1")
    monkeypatch.setattr("shutil.which", lambda x: None)

    config = {
        "wrapper": {
            "require_login": False,
            "fail_on_missing_copilot": True,
        }
    }

    with pytest.raises(ink.PolicyViolation):
        ink.enforce_wrapper_policy(
            config,
            state=fake_state,
            logging_cfg=fake_logging_cfg,
        )


def test_network_policy_sets_flag(monkeypatch):
    """
    Validate network restriction flag behavior.

    When require_internet=False:
        - NO_NETWORK environment variable must be set.
    """
    monkeypatch.delenv("NO_NETWORK", raising=False)

    ink.enforce_network_policy({
        "network": {
            "require_internet": False
        }
    })

    assert os.environ["NO_NETWORK"] == "1"

def test_network_policy_no_flag_when_allowed(monkeypatch):
    monkeypatch.delenv("NO_NETWORK", raising=False)

    ink.enforce_network_policy({
        "network": {"require_internet": True}
    })

    assert "NO_NETWORK" not in os.environ


def test_no_guardrails_allows(fake_state, fake_logging_cfg):
    ink.enforce_deny_shell_commands(
        "rm -rf /",
        {},
        state=fake_state,
        logging_cfg=fake_logging_cfg,
    )

def test_wrapper_passes_when_authenticated(monkeypatch, fake_state, fake_logging_cfg):
    monkeypatch.setenv("COPILOT_AUTHENTICATED", "1")
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/copilot")

    config = {"wrapper": {"require_login": True, "fail_on_missing_copilot": True}}

    ink.enforce_wrapper_policy(
        config,
        state=fake_state,
        logging_cfg=fake_logging_cfg,
    )

def test_main_short_circuits_before_subprocess(monkeypatch):
    # Prevent actual subprocess execution
    monkeypatch.setattr("ink_core.subprocess.run",
                        lambda *a, **k: pytest.fail("subprocess should not run"))

    # Mock minimal config/state loader
    fake_cfg = SimpleNamespace(logging=SimpleNamespace(
        enabled=False,
        log_raw_prompts=False
    ))
    fake_state = SimpleNamespace(copilot_config_dir=".", log_dir=".")

    monkeypatch.setattr("ink_core.load_config_and_state",
                        lambda: (fake_cfg, {
                            "prompt_filter": {
                                "enabled": True,
                                "case_insensitive": True,
                                "blocked_keywords": ["rm"],
                                "blocked_regex": []
                            }
                        }, fake_state))

    monkeypatch.setattr("ink_core.parse_args",
                        lambda: SimpleNamespace(prompt=["rm -rf /"]))

    monkeypatch.setattr("ink_core.ensure_bootstrap_import", lambda: None)
    monkeypatch.setattr("ink_core.log_event", lambda *a, **k: None)

    with pytest.raises(SystemExit):
        ink.main()

# NOTE:
# These tests validate *only* enforcement decisions (raise / no raise).
# They do not validate:
#     - Logging output
#     - Runtime orchestration
#     - Copilot invocation
#     - Slurm integration
#     - Filesystem persistence