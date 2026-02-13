"""
Policy Enforcement Layer

This module defines Inkly's safety boundary.

It contains:
- PolicyViolation (domain-level exception)
- enforce_* guardrail functions

No orchestration, no logging, no subprocess execution.
"""


import os
import re
import shutil

class PolicyViolation(Exception):
    """
    Raised when a user request violates an Inkly policy rule.

    This represents a domain-level failure (not a process crash).
    The CLI layer is responsible for converting this into
    a user-facing message and exit code.
    """

    pass


# Policy Enforcement
# Policy level semantics restrictions on what users are allowed to ask
def enforce_prompt_filter(user_prompt: str, config: dict, *, state, logging_cfg):
    """
    Enforce prompt-level intent restrictions.

    Blocks disallowed keywords or patterns before any
    tool-level execution occurs.
    """
    pf = config.get("prompt_filter", {})  #
    if not pf.get("enabled", False):
        return  # filtering disabled, allow everything

    text = user_prompt
    if pf.get("case_insensitive", False):
        text = text.lower()

    # Keyword blocking
    for kw in pf.get("blocked_keywords", []):  # return list of keywords
        check_kw = kw.lower() if pf.get("case_insensitive", False) else kw
        # .escape turns userspecified keyword into literal match. \b is word boundary, so the key word is a standalone word
        if re.search(rf"\b{re.escape(check_kw)}\b", text):
            # If any blocked keyword is found, die with policy block message
            raise PolicyViolation("Blocked by policy")

    # Regex blocking
    for pattern in pf.get("blocked_regex", []):
        flags = re.IGNORECASE if pf.get("case_insensitive", False) else 0
        if re.search(pattern, user_prompt, flags):
            raise PolicyViolation("Blocked by policy")


def enforce_deny_shell_commands(
    user_prompt: str, config: dict, *, state, logging_cfg
):  # * forces callers to pass state as keyword argument
    """
    Enforce hard denial of dangerous shell commands.

    This layer prevents filesystem destruction or
    privilege escalation regardless of intent.
    """
    guardrails = config.get("copilot", {}).get(
        "guardrails", {}
    )  # get copilot/guardrails section of config into a dict
    rules = guardrails.get(
        "deny_shell_commands", []
    )  # find deny_shell_commands keyword, return list of rules, emypty list if missing

    if not rules:
        return  # nothing to enforce, exit function

    text = user_prompt.strip()

    for rule in rules:
        # Format: "rm:*", "sudo:*"
        cmd = rule.split(":", 1)[0]  # everything before the first colon is kept

        # Very intentional: shell-like word boundary
        if re.search(rf"\b{re.escape(cmd)}\b", text):
            raise PolicyViolation(f"Blocked by policy: shell command '{cmd}'")


def enforce_wrapper_policy(config: dict, *, state, logging_cfg):
    """
    Enforce wrapper-level runtime requirements.

    Validates authentication and required tooling
    before invoking Copilot.
    """
    wrapper = config.get("wrapper", {})

    if wrapper.get("require_login", False):
        if not os.environ.get("COPILOT_AUTHENTICATED"):
            raise PolicyViolation("Copilot login required by policy")

    if wrapper.get("fail_on_missing_copilot", True):
        if not shutil.which("copilot"):
            raise PolicyViolation("Copilot CLI not found (required by policy)")


def enforce_network_policy(config: dict):
    """
    Apply network access constraints.

    Signals downstream tools when outbound
    network access is prohibited.
    """
    net = config.get("network", {})
    if not net.get("require_internet", True):
        os.environ["NO_NETWORK"] = "1"
