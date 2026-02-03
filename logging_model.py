# This file will contain only schema + validation
# This file defines log record structure only
# No filesystem access
# No printing
# No timestamps generated here
# No defaults pulled from environment

from dataclasses import dataclass
from pathlib import Path
import tomllib

@dataclass
class LoggingHistoryConfig:
    enabled: bool = False
    max_turns: int = 1000

    def validate(self):
        if self.max_turns <= 0:
            raise ValueError("logging.history.max_turns must be > 0")
@dataclass
class LoggingConfig:
    level: str = "info"
    schema_version: int = 1

    per_user_logs: bool = False
    global_log: bool = True
    max_log_file_mb: int = 10
    history: LoggingHistoryConfig = LoggingHistoryConfig()
    def validate(self):
        if self.level not in ["debug", "info", "warning", "error", "critical"]:
            raise ValueError("logging.level must be one of debug, info, warning, error, critical")
        if self.schema_version != 1:
            raise ValueError("Unsupported logging.schema_version, must be 1")
        self.history.validate()
        if not self.per_user_logs and not self.global_log:
            raise ValueError("At least one of logging.per_user_logs or logging.global_log must be True")
        if self.max_log_file_mb <= 0:
            raise ValueError("logging.max_log_file_mb must be > 0")


