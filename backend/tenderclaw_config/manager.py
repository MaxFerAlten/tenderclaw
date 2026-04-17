"""Configuration Manager with Schema Validation.

Hierarchical config loading with Pydantic validation.
Supports JSON, JSONC, YAML, and environment variables.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from backend.tenderclaw_config.jsonc import load_jsonc, merge_jsonc
from backend.tenderclaw_config.schemas.tenderclaw_config import TenderClawConfig

logger = logging.getLogger("tenderclaw.config")

CONFIG_SEARCH_PATHS = [
    Path.home() / ".tenderclaw" / "config.jsonc",
    Path.home() / ".tenderclaw" / "config.json",
    Path.home() / ".tenderclaw" / "config.yaml",
    Path.home() / ".tenderclaw" / "config.yml",
    Path.cwd() / ".tenderclaw.jsonc",
    Path.cwd() / ".tenderclaw.json",
    Path.cwd() / ".tenderclaw.yaml",
    Path.cwd() / ".tenderclaw.yml",
    Path.cwd() / "tenderclaw.config.jsonc",
    Path.cwd() / "tenderclaw.config.json",
    Path.cwd() / "tenderclaw.config.yaml",
    Path.cwd() / "tenderclaw.config.yml",
]

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default.yaml"

ENV_PREFIX = "TENDERCLAW_"


@dataclass
class ConfigSource:
    """Source of configuration data."""

    name: str
    path: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """Manages TenderClaw configuration with schema validation.

    Loads configuration from multiple sources in order of precedence:
    1. Default configuration (lowest priority)
    2. User/project config files
    3. Environment variables
    4. Runtime overrides (highest priority)
    """

    def __init__(self):
        self._config: Optional[TenderClawConfig] = None
        self._sources: List[ConfigSource] = []
        self._loaded: bool = False

    def load(self, force: bool = False, project_root: Optional[str] = None) -> TenderClawConfig:
        """Load configuration from all sources.

        Args:
            force: Force reload even if already loaded
            project_root: Optional path to the active project. When provided, any
                .tenderclaw/config.jsonc inside it is merged with highest file priority.

        Returns:
            Validated TenderClawConfig instance
        """
        if self._loaded and not force:
            return self._config or TenderClawConfig()

        config_data: Dict[str, Any] = {}
        sources: List[ConfigSource] = []

        default_config = self._load_default_config()
        if default_config:
            config_data.update(default_config)
            sources.append(ConfigSource(name="default", data=default_config))

        repo_root = Path(project_root) if project_root else None
        file_config = self._load_config_files(project_root=repo_root)
        if file_config:
            config_data = merge_jsonc(config_data, file_config)
            sources.append(ConfigSource(name="file", data=file_config))

        env_config = self._load_env_config()
        if env_config:
            config_data = merge_jsonc(config_data, env_config)
            sources.append(ConfigSource(name="environment", data=env_config))

        try:
            self._config = TenderClawConfig.model_validate(config_data)
        except Exception as e:
            logger.warning("Config validation failed, using defaults: %s", e)
            self._config = TenderClawConfig()

        self._sources = sources
        self._loaded = True

        logger.info(
            "Loaded configuration from sources: %s",
            ", ".join(s.name for s in sources),
        )
        return self._config

    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration."""
        if DEFAULT_CONFIG_PATH.exists():
            try:
                return self._load_file(DEFAULT_CONFIG_PATH)
            except Exception as e:
                logger.warning("Failed to load default config: %s", e)
        return {}

    def _load_config_files(self, project_root: Optional[Path] = None) -> Dict[str, Any]:
        """Load configuration from user and project files.

        If project_root is provided, also loads the per-repo config from
        <project_root>/.tenderclaw/config.jsonc (highest file-level priority).
        """
        config_data: Dict[str, Any] = {}

        for path in CONFIG_SEARCH_PATHS:
            if not path.exists():
                continue
            try:
                file_data = self._load_file(path)
                if file_data:
                    config_data = merge_jsonc(config_data, file_data)
                    logger.debug("Loaded config from %s", path)
            except Exception as e:
                logger.warning("Failed to load config from %s: %s", path, e)

        # Per-repo config — applied last so it overrides global/user config
        if project_root:
            repo_paths = [
                Path(project_root) / ".tenderclaw" / "config.jsonc",
                Path(project_root) / ".tenderclaw" / "config.json",
                Path(project_root) / ".tenderclaw" / "config.yaml",
                Path(project_root) / ".tenderclaw" / "config.yml",
            ]
            for path in repo_paths:
                if path.exists():
                    try:
                        repo_data = self._load_file(path)
                        if repo_data:
                            config_data = merge_jsonc(config_data, repo_data)
                            logger.info("Loaded per-repo config from %s", path)
                    except Exception as e:
                        logger.warning("Failed to load per-repo config from %s: %s", path, e)
                    break  # First match wins

        return config_data

    def _load_file(self, path: Path) -> Dict[str, Any]:
        """Load a single config file."""
        suffix = path.suffix.lower()

        if suffix == ".jsonc":
            return load_jsonc(path)
        elif suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        elif suffix in (".yaml", ".yml"):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        else:
            raise ValueError(f"Unsupported config file format: {suffix}")

    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config_data: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.startswith(ENV_PREFIX):
                continue

            config_key = key[len(ENV_PREFIX) :].lower()

            env_mapping = {
                "default_model": str,
                "default_run_agent": str,
                "new_task_system_enabled": lambda x: x.lower() in ("true", "1", "yes"),
                "hashline_edit": lambda x: x.lower() in ("true", "1", "yes"),
                "model_fallback": lambda x: x.lower() in ("true", "1", "yes"),
                "auto_update": lambda x: x.lower() in ("true", "1", "yes"),
            }

            if config_key in env_mapping:
                try:
                    converter = env_mapping[config_key]
                    config_data[config_key] = converter(value)
                except Exception as e:
                    logger.warning(
                        "Failed to convert env %s=%s: %s", key, value, e
                    )
            else:
                parts = config_key.split("_")
                current = config_data
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value

        return config_data

    def get_config(self) -> TenderClawConfig:
        """Get the current configuration, loading if necessary."""
        if self._config is None:
            return self.load()
        return self._config

    def reload(self, project_root: Optional[str] = None) -> TenderClawConfig:
        """Force reload configuration from all sources."""
        self._loaded = False
        self._config = None
        return self.load(force=True, project_root=project_root)

    @classmethod
    def load_for_repo(cls, project_root: str) -> TenderClawConfig:
        """Create a fresh ConfigManager and load config for a specific repo.

        Useful when multiple repos are active simultaneously or in tests.
        """
        mgr = cls()
        return mgr.load(project_root=project_root)

    @staticmethod
    def get_repo_memory_config(project_root: str) -> Dict[str, Any]:
        """Read the memory-related section from a repo's .tenderclaw/config.jsonc.

        Returns an empty dict if the file does not exist or has no memory section.
        """
        candidates = [
            Path(project_root) / ".tenderclaw" / "config.jsonc",
            Path(project_root) / ".tenderclaw" / "config.json",
        ]
        for path in candidates:
            if path.exists():
                try:
                    data = load_jsonc(path) if path.suffix == ".jsonc" else json.loads(path.read_text())
                    return data.get("memory", {})
                except Exception as exc:
                    logger.warning("Failed to read repo memory config from %s: %s", path, exc)
        return {}

    def update_runtime(self, updates: Dict[str, Any]) -> TenderClawConfig:
        """Update configuration at runtime (does not persist to disk).

        Args:
            updates: Configuration updates to apply

        Returns:
            Updated TenderClawConfig
        """
        if self._config is None:
            self.load()

        current_dict = self._config.model_dump(exclude_none=True)
        merged = merge_jsonc(current_dict, updates)

        try:
            self._config = TenderClawConfig.model_validate(merged)
        except Exception as e:
            logger.warning("Runtime config update validation failed: %s", e)

        self._sources.append(ConfigSource(name="runtime", data=updates))
        return self._config

    def get_sources(self) -> List[ConfigSource]:
        """Get list of configuration sources that were loaded."""
        return self._sources.copy()

    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate a configuration dictionary.

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            TenderClawConfig.model_validate(config)
            return True, None
        except Exception as e:
            return False, str(e)

    def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Agent configuration dictionary or None
        """
        config = self.get_config()
        agent_config = config.get_agent_config(agent_name)
        if agent_config:
            return agent_config.model_dump(exclude_none=True)
        return None

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if an experimental feature is enabled.

        Args:
            feature: Feature name (camelCase or snake_case)

        Returns:
            True if enabled, False otherwise
        """
        config = self.get_config()
        if not config.experimental:
            return False
        attr_name = feature.replace("-", "_")
        return getattr(config.experimental, attr_name, False)

    def is_agent_disabled(self, agent_name: str) -> bool:
        """Check if an agent is disabled.

        Args:
            agent_name: Name of the agent

        Returns:
            True if disabled, False otherwise
        """
        return self.get_config().is_agent_disabled(agent_name)

    def is_hook_disabled(self, hook_name: str) -> bool:
        """Check if a hook is disabled.

        Args:
            hook_name: Name of the hook

        Returns:
            True if disabled, False otherwise
        """
        return self.get_config().is_hook_disabled(hook_name)

    def is_mcp_disabled(self, mcp_name: str) -> bool:
        """Check if an MCP is disabled.

        Args:
            mcp_name: Name of the MCP

        Returns:
            True if disabled, False otherwise
        """
        return self.get_config().is_mcp_disabled(mcp_name)


config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """Get the global ConfigManager instance."""
    return config_manager
