from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from inkly.plugins.common import validate_plugin_meta


@dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    category: str
    example_queries: List[str]
    run: Callable[[], str]


class PluginManager:
    """
    Discover and enumerate Inkly plugins without hard-coding their names.
    """

    def __init__(self, package_name: str = "inkly.plugins"):
        self.package_name = package_name
        self._plugins: Dict[str, Plugin] = {}

    def discover(self) -> Dict[str, Plugin]:
        package = importlib.import_module(self.package_name)
        discovered: Dict[str, Plugin] = {}

        for module_info in pkgutil.iter_modules(package.__path__):
            module_name = module_info.name

            if module_name.startswith("_") or module_name == "manager":
                continue

            full_name = f"{self.package_name}.{module_name}"
            module = importlib.import_module(full_name)

            if not hasattr(module, "PLUGIN_META"):
                continue
            if not hasattr(module, "run"):
                continue

            meta = module.PLUGIN_META
            validate_plugin_meta(meta)

            plugin = Plugin(
                name=meta["name"],
                description=meta["description"],
                category=meta["category"],
                example_queries=list(meta.get("example_queries", [])),
                run=module.run,
            )

            discovered[plugin.name] = plugin

        self._plugins = discovered
        return dict(self._plugins)

    def list_plugins(self) -> List[Plugin]:
        if not self._plugins:
            self.discover()
        return list(self._plugins.values())

    def get_plugin(self, name: str) -> Optional[Plugin]:
        if not self._plugins:
            self.discover()
        return self._plugins.get(name)
