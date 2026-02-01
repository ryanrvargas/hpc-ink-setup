from dataclasses import dataclass
from pathlib import Path
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10

@dataclass
class NodeConfig:
    node_version: str
    install_if_missing: bool = True
    allow_curl: bool = True
    allow_wget: bool = True
    nvm_version: str = "0.39.7"

    def validate(self):
        if self.node_version in ("lts", "stable", "latest"):
            raise ValueError(
                "Alias-based Node versions are not supported on HPC. "
                "Use an explicit version."
            )

@dataclass
class InstallConfig:
    user_space_only: bool = True
    allow_modify_shell_rc: bool = True
    shell_rc: str = "~/.bashrc"
    allow_path_injection: bool = True

    def validate(self):
        rc = Path(self.shell_rc).expanduser()
        if self.allow_modify_shell_rc and not rc.exists():
            raise ValueError(f"Shell rc file does not exist: {rc}")
        
@dataclass
class StateConfig:
    inkly_home: str = "~/.inkly"
    bin_dir: str = "~/.inkly/bin"
    copilot_config_dir: str = "~/.inkly/copilot"
    log_dir: str = "~/.inkly/logs"

    def resolve(self):
        """
        Resolve all paths to expanded Path objects.
        """
        self.inkly_home = Path(self.inkly_home).expanduser()
        self.bin_dir = Path(self.bin_dir).expanduser()
        self.copilot_config_dir = Path(self.copilot_config_dir).expanduser()
        self.log_dir = Path(self.log_dir).expanduser()

    def validate(self):
        """
        Validate path relationships and safety.
        """
        # Ensure bin_dir lives under inkly_home
        try:
            self.bin_dir.relative_to(self.inkly_home)
        except ValueError:
            raise ValueError("bin_dir must live under inkly_home")

        try:
            self.copilot_config_dir.relative_to(self.inkly_home)
        except ValueError:
            raise ValueError("copilot_config_dir must live under inkly_home")

        try:
            self.log_dir.relative_to(self.inkly_home)
        except ValueError:
            raise ValueError("log_dir must live under inkly_home")

class TomlParser:
    def __init__(self, path: Path):
        self.path = path

    def load(self):
        if not self.path.exists():
            raise RuntimeError(f"Config not found: {self.path}")

        with self.path.open("rb") as f:
            raw = tomllib.load(f)

        node = NodeConfig(**raw["node"])
        node.validate()

        install = InstallConfig(**raw.get("install", {}))
        install.validate()

        state = StateConfig(**raw.get("state", {}))
        state.resolve()
        state.validate()

        return node, install, state
