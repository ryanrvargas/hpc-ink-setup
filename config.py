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

        return node, install
