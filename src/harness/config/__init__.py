"""Configuration model for LLM providers and backends.

Layers:
- **Project defaults:** ``.harness/providers.yaml`` (env-var refs only,
  safe to commit).
- **User overrides:** ``~/.harness/providers.yaml`` (actual keys, never committed).
  User config is merged on top and wins on conflicts.
"""

from harness.config.architecture import (
    ArchitectureGoal,
    DetectionRule,
    LayerGoal,
    load_architecture_goal,
    save_architecture_goal,
)
from harness.config.manager import (
    HarnessConfigManager,
    NLTranslatorSettings,
    WebSearchSettings,
    allow_refactoring_suggestions,
    ensure_project_config,
    load_project_config,
    load_settings,
)
from harness.config.provider_models import (
    ProviderConfig,
    ProviderConfigSet,
    ProviderError,
)
from harness.config.provider_registry import load_providers

__all__ = [
    "ProviderConfig",
    "ProviderConfigSet",
    "ProviderError",
    "load_providers",
    "allow_refactoring_suggestions",
    "ensure_project_config",
    "load_project_config",
    # Settings (Wave 8b)
    "NLTranslatorSettings",
    "WebSearchSettings",
    "load_settings",
    # Architecture goal
    "ArchitectureGoal",
    "LayerGoal",
    "DetectionRule",
    "load_architecture_goal",
    "save_architecture_goal",
]
