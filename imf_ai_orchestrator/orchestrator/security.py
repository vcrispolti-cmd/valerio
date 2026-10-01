"""Confidentiality gate.

Called immediately before every transmission (agents.Agent.call), not once at
start-up, so no code path can reach an external model without passing it.
"""
from __future__ import annotations

from .config import Config


class ConfidentialityError(PermissionError):
    pass


def provider_allowed(cfg: Config, confidentiality: str, agent: str) -> tuple[bool, str]:
    cls = cfg.confidentiality.get(confidentiality)
    if cls is None:
        return False, f"unknown confidentiality class '{confidentiality}'"
    if not cls.get("external_ai_allowed"):
        return False, f"{confidentiality}: external AI not allowed"
    if not cls.get("approval_reference"):
        return False, f"{confidentiality}: no institutional approval reference recorded"
    provider = cfg.agents[agent]["provider"]
    if provider not in cls.get("approved_providers", []):
        return False, f"{confidentiality}: provider '{provider}' ({agent}) not approved"
    return True, "allowed"


def check(cfg: Config, confidentiality: str, agent: str, mode: str) -> None:
    """Raise unless this transmission is permitted. Mock mode never transmits."""
    if mode == "mock":
        return
    ok, why = provider_allowed(cfg, confidentiality, agent)
    if not ok:
        raise ConfidentialityError(f"BLOCKED before transmission to {agent}: {why}")


def permitted_agents(cfg: Config, confidentiality: str, mode: str) -> list[str]:
    if mode == "mock":
        return list(cfg.agents)
    return [a for a in cfg.agents if provider_allowed(cfg, confidentiality, a)[0]]
