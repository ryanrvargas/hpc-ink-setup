from __future__ import annotations

import getpass
import grp
import os

from inkly.cluster_profile import resolve_cluster_profile
from inkly.plugins.common import format_plugin_output, validate_plugin_meta


PLUGIN_META = {
    "name": "cluster_profile",
    "description": (
        "Provides trusted cluster-local configuration such as scheduler identity, "
        "installed software configuration, module names, access prerequisites, "
        "and verified local paths."
    ),
    "category": "cluster-profile",
    "example_queries": [
        "How do I run software on this cluster?",
        "Which Gaussian module should I use on this cluster?",
        "Why can I not access Gaussian?",
        "Where is Gaussian scratch configured?",
        "What is verified about this cluster?",
    ],
}

validate_plugin_meta(PLUGIN_META)

TRUSTED_LOCAL_SCOPE = "scope=verified-local-cluster"


def _user_in_group(group_name: str, username: str) -> bool | None:
    """
    Return whether the current user belongs to group_name.

    None means the group itself could not be found.
    """
    try:
        group = grp.getgrnam(group_name)
    except KeyError:
        return None

    if os.getgid() == group.gr_gid:
        return True

    if group.gr_gid in os.getgroups():
        return True

    return username in group.gr_mem


def _gaussian_lines(profile: dict) -> list[str]:
    software = profile.get("software", {})
    gaussian = software.get("gaussian")

    if not isinstance(gaussian, dict):
        return [
            "evidence=UNKNOWN | No trusted local Gaussian configuration is recorded."
        ]

    lines = []

    installed = bool(gaussian.get("installed", False))
    runtime_verified = bool(gaussian.get("runtime_verified", False))

    lines.append(
        "evidence=VERIFIED_CONFIG | "
        f"Gaussian installed/configured: {'yes' if installed else 'no'}"
    )

    modules = gaussian.get("modules", [])
    if modules:
        lines.append(
            "evidence=VERIFIED_CONFIG | Advertised Gaussian modules: "
            + ", ".join(str(module) for module in modules)
        )

    default_module = gaussian.get("advertised_default_module")
    if default_module:
        lines.append(
            "evidence=VERIFIED_CONFIG | "
            f"Advertised default Gaussian module: {default_module}"
        )

    username = getpass.getuser()

    scratch_template = gaussian.get("scratch_template")
    if scratch_template:
        scratch = str(scratch_template).replace("{user}", username)
        lines.append(
            "evidence=VERIFIED_CONFIG | "
            f"Configured Gaussian scratch path for current user: {scratch}"
        )

    access_group = gaussian.get("access_group")
    if access_group:
        membership = _user_in_group(str(access_group), username)

        lines.append(
            f"evidence=VERIFIED_CONFIG | Gaussian access group: {access_group}"
        )

        if membership is False:
            lines.append(
                "evidence=BLOCKED_BY_ACCESS | "
                f"Current user {username} is not a member of {access_group}; "
                "do not describe Gaussian as runnable for this user."
            )
        elif membership is True:
            lines.append(
                "evidence=VERIFIED_ACCESS | "
                f"Current user {username} satisfies the {access_group} "
                "group-access prerequisite."
            )
        else:
            lines.append(
                "evidence=UNKNOWN | "
                f"Could not verify whether access group {access_group} exists."
            )

    environment = gaussian.get("c02_environment", {})
    if isinstance(environment, dict):
        g16root = environment.get("g16root")
        if g16root:
            lines.append(
                f"evidence=VERIFIED_CONFIG | C02 configured g16root: {g16root}"
            )

        omp_threads = environment.get("omp_num_threads")
        if omp_threads is not None:
            lines.append(
                "evidence=VERIFIED_CONFIG | "
                f"C02 modulefile sets OMP_NUM_THREADS={omp_threads}"
            )

    if not runtime_verified:
        lines.append(
            "evidence=UNKNOWN | Successful Gaussian runtime execution has "
            "not yet been verified for this cluster profile."
        )

    return lines


def run(query: str) -> str:
    """Return trusted local cluster facts relevant to the current query."""
    profile = resolve_cluster_profile()

    if profile is None:
        return format_plugin_output(
            "Trusted Cluster Profile",
            ["No trusted local cluster profile matched the current host."],
        )

    lines = [
        TRUSTED_LOCAL_SCOPE,
        f"Cluster: {profile.get('name', 'Unknown')}",
        f"Scheduler: {profile.get('scheduler', 'unknown')}",
    ]

    if "gaussian" in query.casefold():
        lines.extend(_gaussian_lines(profile))

    return format_plugin_output("Trusted Cluster Profile", lines)
