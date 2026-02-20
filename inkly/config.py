from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10
from typing import Literal


class ConfigError(Exception):
    """Raised when the configuration file is invalid or incomplete."""


@dataclass
class NodeConfig:
    """Configuration related to Node.js installation and management.

    Attributes:
        node_version (str): The specific version of Node.js to install (e.g. "18.16.0").
            Alias versions like "lts", "stable", or "latest" are not supported on HPC.
        install_if_missing (bool): Whether to attempt installation if Node.js is not found.
        allow_curl (bool): Whether to allow using curl for installation.
        allow_wget (bool): Whether to allow using wget for installation.
        nvm_version (str): The version of nvm to use for managing Node.js versions.
    """

    node_version: str
    install_if_missing: bool = True
    allow_curl: bool = True
    allow_wget: bool = True
    nvm_version: str = "0.39.7"

    def validate(self) -> "NodeConfig":
        """Validates the NodeConfig variables

        This method should be called after initialization to ensure the config is correct.

        Parameters:
            None

        Returns:
            NodeConfig: The validated NodeConfig object (self).

        Raises:
            ValueError: If any of the config variables are invalid.
        """

        if self.node_version in ("lts", "stable", "latest"):
            raise ConfigError(
                "Alias-based Node versions are not supported on HPC. "
                "Use an explicit version."
            )
        return self


@dataclass
class InstallConfig:
    """Configuration related to installation behavior and safety.

    Attributes:
        user_space_only (bool): If True, restricts installation to user space.
        allow_modify_shell_rc (bool): If True, allows modifying the user's shell rc file.
        shell_rc (str): The path to the user's shell rc file (e.g. "~/.bashrc").
        allow_path_injection (bool): If True, allows injecting into PATH for installed binaries.

    """

    user_space_only: bool = True
    allow_modify_shell_rc: bool = True
    shell_rc: str = "~/.bashrc"
    allow_path_injection: bool = True

    def validate(self) -> "InstallConfig":
        """Validates the InstallConfig variables

        This method should be called after initialization to ensure the config is correct.

        Parameters:
            None

        Returns:
            InstallConfig: The validated InstallConfig object (self).

        Raises:
            ValueError: If any of the config variables are invalid or unsafe.

        """

        if self.allow_modify_shell_rc:
            rc = Path(self.shell_rc).expanduser()
            if not rc.parent.exists():
                raise ConfigError(f"Shell rc directory does not exist: {rc.parent}")
        return self


@dataclass
class StateConfig:
    """Configuration related to where Inkly stores its state, logs, and binaries.

    Attributes:
        inkly_home (Path): The root directory for all Inkly state and data.
        bin_dir (Path): The directory where Inkly-managed binaries (like Node.js) are stored.
        log_dir (Path): The directory where Inkly stores logs.

    """

    inkly_home: Path = Path("~/.inkly")
    bin_dir: Path = Path("~/.inkly/bin")
    log_dir: Path = Path("~/.inkly/logs")

    def resolve(self) -> "StateConfig":
        """Resolve and expand all paths to absolute paths.

        This should be called after initialization to ensure all paths are absolute and expanded.

        Parameters:
            None

        Returns:
            StateConfig: The StateConfig object with resolved paths (self).

        """
        self.inkly_home = Path(self.inkly_home).expanduser()
        self.bin_dir = Path(self.bin_dir).expanduser()
        self.log_dir = Path(self.log_dir).expanduser()
        return self

    def validate(self) -> "StateConfig":
        """Validates that all paths are properly set

        Validation checks that bin_dir and log_dir all live under inkly_home
        to prevent misconfiguration that could lead to data being stored in unintended locations.

        Parameters:
            None

        Returns:
            StateConfig: The validated StateConfig object (self).

        Raises:
            ValueError: If any of the paths are not properly configured or violate the expected structure.
        """
        # Ensure bin_dir lives under inkly_home
        try:
            self.bin_dir.relative_to(self.inkly_home)
        except ValueError:
            raise ConfigError("bin_dir must live under inkly_home")

        try:
            self.log_dir.relative_to(self.inkly_home)
        except ValueError:
            raise ConfigError("log_dir must live under inkly_home")

        return self


@dataclass
class LoggingHistoryConfig:
    """Configuration related to in-memory history of prompts and responses for the current session.

    Attributes:
        enabled (bool): Whether to keep an in-memory history of prompts and responses for the current session.
        max_prompts (int): The maximum number of recent prompts to keep in memory for context. Must be > 0 if enabled.

    """

    enabled: bool = True
    max_prompts: int = 5

    def validate(self):
        if self.enabled and self.max_prompts <= 0:
            raise ConfigError("logging.history.max_prompts must be > 0")
        return self


@dataclass
class LoggingConfig:
    enabled: bool = True
    level: Literal["debug", "info", "warning", "error"] = "info"

    schema_version: int = 1

    log_user_prompts: bool = True
    log_ai_responses: bool = True
    log_job_outcomes: bool = False

    log_raw_prompts: bool = False
    log_raw_ai_responses: bool = False

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
            return self
        if self.log_raw_prompts and not self.log_user_prompts:
            raise ConfigError("log_raw_prompts requires log_user_prompts = true")
        if self.log_raw_ai_responses and not self.log_ai_responses:
            raise ConfigError("log_raw_ai_responses requires log_ai_responses = true")

        allowed_levels = {"debug", "info", "warning", "error"}
        if self.level not in allowed_levels:
            raise ConfigError(f"Invalid logging.level: {self.level}")

        if self.schema_version <= 0:
            raise ConfigError("logging.schema_version must be >= 1")
        if self.max_log_file_mb <= 0:
            raise ConfigError("logging.max_log_file_mb must be > 0")
        if self.max_log_files <= 0:
            raise ConfigError("logging.max_log_files must be > 0")
        if not self.per_user_logs and not self.global_log:
            raise ConfigError(
                "At least one of per_user_logs or global_log must be enabled"
            )

        self.history.validate()
        return self


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
            raise ConfigError(f"Missing required config section: [{key}]")
        return raw[key]

    def load(self):
        if not self.path.exists():
            raise ConfigError(f"Config not found: {self.path}")

        with self.path.open("rb") as f:
            raw = tomllib.load(f)

        node = NodeConfig(**self._require(raw, "node")).validate()

        install = InstallConfig(**raw.get("install", {})).validate()

        state = StateConfig(**self._require(raw, "state")).resolve().validate()

        logging_raw = raw.get("logging", {})
        history = LoggingHistoryConfig(**logging_raw.get("history", {}))

        logging_cfg = LoggingConfig(
            **{k: v for k, v in logging_raw.items() if k != "history"}, history=history
        )
        logging_cfg.validate()

        return InklyConfig(
            raw_config=raw, node=node, install=install, state=state, logging=logging_cfg
        )
