import sys
from pathlib import Path
import pytest

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import TomlParser

@pytest.fixture
def full_cfg():
    config_path = ROOT / "tests" / "data" / "test.toml"
    return TomlParser(config_path).load()

def test_full_config_parsing():
    config_path = ROOT / "tests" / "data" / "test.toml"
    cfg = TomlParser(config_path).load()

    assert cfg.install.user_space_only is True
    assert cfg.node.node_version == "20.11.1"
    assert cfg.logging.history.max_prompts == 5
    assert cfg.state.log_dir is not None

def test_missing_state_section_raises_error():
    minimal_path = ROOT / "tests" / "data" / "minimal.toml"

    with pytest.raises(RuntimeError, match="Missing required config section: \\[state\\]"):
        TomlParser(minimal_path).load()