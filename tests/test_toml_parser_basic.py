import sys
from pathlib import Path
import pytest
from inkly.config import TomlParser, ConfigError


"""
Ensure the project root is available on sys.path so tests can import the
config module regardless of how pytest is invoked (local runs, CI, or HPC
environments).

This avoids relying on implicit PYTHONPATH behavior, which can vary across
systems and clusters.
"""


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_DIR = ROOT / "tests" / "data"


@pytest.fixture
def full_cfg():
    """
    Fixture that loads a complete, valid configuration file.

    This represents the "happy path" configuration used by Inkly during
    normal operation. It is used by tests that need a fully constructed
    InklyConfig object without repeating setup logic.
    """
    config_path = TEST_DIR / "test.toml"
    return TomlParser(config_path).load()


def test_full_config_parsing():
    """
    Verify that a full, valid configuration file parses successfully.

    This test asserts that:
    - Explicit values from the TOML file are preserved
    - Nested configuration objects are constructed correctly
    - Required sections are present and accessible

    This test does not validate every field; it acts as a sanity check that
    the overall configuration pipeline works end-to-end for valid input.
    """
    config_path = TEST_DIR / "test.toml"
    cfg = TomlParser(config_path).load()

    assert cfg.install.user_space_only is True
    assert cfg.node.node_version == "20.11.1"
    assert cfg.logging.history.max_prompts == 5
    assert cfg.state.log_dir is not None


def test_missing_state_section_raises_error():
    """
    Verify that the [state] section is required.

    The [state] section defines critical filesystem paths used by Inkly.
    If it is missing, the configuration is considered invalid and must
    fail fast with a clear, explicit error.

    This test ensures:
    - Missing required sections are detected
    - The failure is reported as a ConfigError
    - The error message clearly identifies the missing section
    """
    minimal_path = TEST_DIR / "minimal.toml"

    with pytest.raises(
        ConfigError, match="Missing required config section: \\[state\\]"
    ):
        TomlParser(minimal_path).load()


def test_invalid_node_version_type_raises_error():
    """
    Verify that invalid types in the configuration are rejected.

    This test specifically checks that providing a non-string value for
    node.node_version (for example, an integer) results in a configuration
    error.

    The intent is to confirm that schema and type validation errors are:
    - Detected during parsing
    - Reported as ConfigError
    - Not silently coerced or ignored
    """
    bad_path = TEST_DIR / "invalid_node_version.toml"

    with pytest.raises(ConfigError):
        TomlParser(bad_path).load()


def test_invalid_logging_level_raises_config_error():
    """
    Verify that invalid enumerated values are rejected.

    The logging.level field only allows a fixed set of values. Providing an
    unsupported value (for example, "trace") should cause configuration
    loading to fail.

    This test ensures:
    - Validation logic is enforced
    - User mistakes are surfaced early
    - All such failures are consistently reported as ConfigError
    """
    bad_path = TEST_DIR / "invalid_logging_level.toml"

    with pytest.raises(ConfigError):
        TomlParser(bad_path).load()
