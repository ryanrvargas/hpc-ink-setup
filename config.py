from dataclasses import dataclass
from pathlib import Path
import tomllib

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
        
class TomlParser:
    def __init__(self, path: Path):
        self.path = path

    def load(self):
        if not self.path.exists():
            raise RuntimeError(f"Config not found: {self.path}")

        with self.path.open("rb") as f:
            raw = tomllib.load(f)

        # Build NodeConfig
        if "node" not in raw:
            raise RuntimeError("Missing [node] section in config.toml")

        node = NodeConfig(**raw["node"])
        node.validate()

        return node
