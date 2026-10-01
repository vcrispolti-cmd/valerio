"""Single source of truth for configuration.

Every YAML file under config/ is loaded and cross-validated here. Nothing else
in the package hard-codes pipelines, routes, roles or thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_FILES = (
    "agents", "roles", "confidentiality", "exposure", "quality_gates",
    "strength", "coverage", "routing", "taxonomy",
)


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    root: Path
    agents: dict
    roles: dict
    confidentiality: dict
    exposure: dict
    quality_gates: dict
    strength: dict
    coverage: dict
    routing: dict
    taxonomy: dict

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    def family(self, agent: str) -> str:
        return self.agents[agent]["family"]

    def stages_for_level(self, level: int) -> list[str]:
        return list(self.routing["levels"][level]["stages"])


def load_config(root: str | Path) -> Config:
    root = Path(root)
    data = {}
    for name in CONFIG_FILES:
        path = root / "config" / f"{name}.yaml"
        if not path.exists():
            raise ConfigError(f"missing config file: {path}")
        with open(path, encoding="utf-8") as f:
            data[name] = yaml.safe_load(f) or {}
    cfg = Config(
        root=root,
        agents=data["agents"]["agents"],
        roles=data["roles"]["roles"],
        confidentiality=data["confidentiality"]["classes"],
        exposure=data["exposure"],
        quality_gates=data["quality_gates"],
        strength=data["strength"],
        coverage=data["coverage"]["document_types"],
        routing=data["routing"],
        taxonomy=data["taxonomy"],
    )
    validate(cfg)
    return cfg


def validate(cfg: Config) -> None:
    errors = []
    for name, spec in cfg.agents.items():
        for key in ("family", "provider", "adapter"):
            if key not in spec:
                errors.append(f"agent {name}: missing '{key}'")
    for role, spec in cfg.roles.items():
        for agent in spec.get("prefer", []):
            if agent not in cfg.agents:
                errors.append(f"role {role}: unknown agent '{agent}'")
        for ref in spec.get("distinct_family_from", []):
            if ref not in cfg.roles:
                errors.append(f"role {role}: distinct_family_from unknown role '{ref}'")
        if spec.get("count", 1) > len(spec.get("prefer", [])):
            errors.append(f"role {role}: count exceeds preference list")
    for role in cfg.exposure.get("roles", {}):
        if role not in cfg.roles and role not in ("critic_rebuttal", "reviser", "targeted"):
            errors.append(f"exposure: unknown role '{role}'")
    for cat, roles in cfg.routing["routes"].items():
        for role in roles:
            if role not in cfg.roles:
                errors.append(f"route {cat}: unknown role '{role}'")
    for lvl in range(5):
        if lvl not in cfg.routing["levels"]:
            errors.append(f"routing: level {lvl} not defined")
    for cls, spec in cfg.confidentiality.items():
        if spec.get("external_ai_allowed") and not spec.get("approval_reference"):
            errors.append(f"confidentiality {cls}: external AI allowed without approval_reference")
    weights = cfg.quality_gates["score_weights"]
    if sum(weights.values()) != 100:
        errors.append(f"quality_gates: score weights sum to {sum(weights.values())}, not 100")
    if errors:
        raise ConfigError("; ".join(errors))
