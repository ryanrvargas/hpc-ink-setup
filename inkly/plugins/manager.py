from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from inkly.plugins.common import validate_plugin_meta


@dataclass(frozen=True)
class Plugin:
    """
    Represents a fully constructed plugin object.

    This is the normalized structure used by the runtime after discovery.
    It separates plugin metadata from the raw module so everything downstream
    interacts with a consistent interface.
    """

    # Unique plugin name (used as identifier in runtime and prompt)
    name: str

    # Human-readable description (used by retrieval and explainability)
    description: str

    # Category used for retrieval filtering and grouping
    category: str

    # Example queries used for retrieval indexing and similarity matching
    example_queries: List[str]

    # Callable entry point for executing the plugin
    run: Callable[[], str]


class PluginManager:
    """
    Handles dynamic discovery and access of plugins.

    This avoids hard-coding plugin imports and allows new plugins to be added
    simply by placing them in the plugins package.

    Discovery is based on:
    - module presence in the package
    - required attributes (PLUGIN_META, run)
    """

    def __init__(self, package_name: str = "inkly.plugins"):
        # Package to scan for plugins
        self.package_name = package_name

        # Cached plugins after discovery
        self._plugins: Dict[str, Plugin] = {}

    def discover(self) -> Dict[str, Plugin]:
        """
        Discover all valid plugins in the configured package.

        Steps:
        - Import the plugin package
        - Iterate over all modules in the package
        - Skip internal modules (private or manager)
        - Validate required attributes (PLUGIN_META, run)
        - Validate metadata structure
        - Build Plugin objects

        Returns:
            Dictionary mapping plugin name -> Plugin object
        """
        package = importlib.import_module(self.package_name)
        discovered: Dict[str, Plugin] = {}

        # Iterate over all modules inside the plugin package
        for module_info in pkgutil.iter_modules(package.__path__):
            module_name = module_info.name

            # Skip private modules and the manager itself
            if module_name.startswith("_") or module_name == "manager":
                continue

            full_name = f"{self.package_name}.{module_name}"
            module = importlib.import_module(full_name)

            # A valid plugin must define metadata and a run function
            if not hasattr(module, "PLUGIN_META"):
                continue
            if not hasattr(module, "run"):
                continue

            meta = module.PLUGIN_META

            # Ensure metadata is valid before constructing the plugin
            validate_plugin_meta(meta)

            # Build a normalized Plugin object
            plugin = Plugin(
                name=meta["name"],
                description=meta["description"],
                category=meta["category"],
                example_queries=list(meta.get("example_queries", [])),
                run=module.run,
            )

            # Store using plugin name as the key
            discovered[plugin.name] = plugin

        # Cache discovered plugins for reuse
        self._plugins = discovered

        # Return a copy to avoid external mutation of internal state
        return dict(self._plugins)

    def list_plugins(self) -> List[Plugin]:
        """
        Return a list of all discovered plugins.

        If plugins have not been discovered yet, discovery is triggered.
        """
        if not self._plugins:
            self.discover()

        return list(self._plugins.values())

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """
        Retrieve a single plugin by name.

        If plugins have not been discovered yet, discovery is triggered.

        Returns:
            Plugin if found, otherwise None
        """
        if not self._plugins:
            self.discover()

        return self._plugins.get(name)
