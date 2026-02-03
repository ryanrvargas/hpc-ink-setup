
from dataclasses import dataclass, field
from pathlib import Path
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10
from typing import Literal

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
        if self.allow_modify_shell_rc:
            rc = Path(self.shell_rc).expanduser()
            if not rc.parent.exists():
                raise ValueError(f"Shell rc directory does not exist: {rc.parent}")
        
@dataclass
class StateConfig:
    inkly_home: Path = Path("~/.inkly")
    bin_dir: Path = Path("~/.inkly/bin")
    copilot_config_dir: Path = Path("~/.inkly/copilot")
    log_dir: Path = Path("~/.inkly/logs")

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

@dataclass
class LoggingHistoryConfig:
    enabled: bool = True
    max_prompts: int = 5

    def validate(self):
        if self.enabled and self.max_prompts <= 0:
            raise ValueError("logging.history.max_prompts must be > 0")
        
@dataclass
class LoggingConfig:
    enabled: bool = True
    level: Literal["debug", "info", "warning", "error"] = "info"

    schema_version: int = 1

    log_user_prompts: bool = True
    log_ai_responses: bool = True
    log_job_outcomes: bool = False

    per_user_logs: bool = True
    global_log: bool = False

    max_log_file_mb: int = 10
    max_log_files: int = 5

    history: LoggingHistoryConfig = field(default_factory=LoggingHistoryConfig)

    @property
    def max_bytes(self) -> int:
        return self.max_log_file_mb * 1024 * 1024

    def validate(self):
        if not self.enabled:
            return

        allowed_levels = {"debug", "info", "warning", "error"}
        if self.level not in allowed_levels:
            raise ValueError(f"Invalid logging.level: {self.level}")

        if self.schema_version <= 0:
            raise ValueError("logging.schema_version must be >= 1")

        if self.max_log_file_mb <= 0:
            raise ValueError("logging.max_log_file_mb must be > 0")

        if self.max_log_files <= 0:
            raise ValueError("logging.max_log_files must be > 0")

        if not self.per_user_logs and not self.global_log:
            raise ValueError(
                "At least one of per_user_logs or global_log must be enabled"
            )

        self.history.validate()

# NOTE:
# Runtime code must consume resolved config objects only.
# raw_config is not a supported runtime interface.
@dataclass
class InklyConfig:
    raw_config: dict
    node: NodeConfig
    install: InstallConfig
    state: StateConfig
    logging: LoggingConfig


class TomlParser:
    def __init__(self, path: Path):
        self.path = path

    def _require(self, raw: dict, key: str) -> dict:
        if key not in raw:
            raise RuntimeError(f"Missing required config section: [{key}]")
        return raw[key]

    def load(self):
        if not self.path.exists():
            raise RuntimeError(f"Config not found: {self.path}")

        with self.path.open("rb") as f:
            raw = tomllib.load(f)

        node = NodeConfig(**self._require(raw, "node"))
        node.validate()

        install = InstallConfig(**raw.get("install", {}))
        install.validate()

        state = StateConfig(**self._require(raw, "state"))
        state.resolve()
        state.validate()

        logging_raw = raw.get("logging", {})
        history = LoggingHistoryConfig(**logging_raw.get("history", {}))

        logging_cfg = LoggingConfig(
            **{k: v for k, v in logging_raw.items() if k != "history"},
            history=history
        )
        logging_cfg.validate()

        return InklyConfig(
            raw_config=raw,
            node=node,
            install=install,
            state=state,
            logging=logging_cfg
        )

