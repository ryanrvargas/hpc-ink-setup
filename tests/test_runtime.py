from pathlib import Path

from inkly.config import TomlParser
from inkly.core.runtime import InklyRuntime

cfg = TomlParser(Path("config.toml")).load()
rt = InklyRuntime(cfg)

print("backend:", cfg.llm.backend)
print("max_concurrent_requests:", cfg.core.max_concurrent_requests)

result = rt.handle_query("test_user", "Why are jobs failing?")
print("\n=== RESULT ===")
print(result)
