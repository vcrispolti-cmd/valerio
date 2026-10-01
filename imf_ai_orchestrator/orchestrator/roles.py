"""Role assignment by constraint solving.

Brands are preferences, not fixtures. The solver enforces independence: a
model family never reviews, grades or verifies its own work. If the permitted
agents cannot satisfy a constraint, assignment fails loudly instead of
quietly letting a model certify itself.
"""
from __future__ import annotations

import random

from .config import Config


class AssignmentError(RuntimeError):
    pass


def _order(cfg: Config) -> list[str]:
    """Topological order so referenced roles are assigned first."""
    done, order = set(), []

    def visit(role, stack=()):
        if role in done:
            return
        if role in stack:
            raise AssignmentError(f"cyclic distinct_family_from involving {role}")
        for ref in cfg.roles[role].get("distinct_family_from", []):
            visit(ref, stack + (role,))
        done.add(role)
        order.append(role)

    for role in cfg.roles:
        visit(role)
    return order


def assign(cfg: Config, permitted: list[str], rotation_seed: int | None = None,
           overrides: dict | None = None) -> dict[str, list[str]]:
    rng = random.Random(rotation_seed)
    overrides = overrides or {}
    out: dict[str, list[str]] = {}
    for role in _order(cfg):
        spec = cfg.roles[role]
        prefer = list(overrides.get(role, spec["prefer"]))
        if spec.get("rotate") and rotation_seed is not None:
            rng.shuffle(prefer)
        banned = {cfg.family(a) for ref in spec.get("distinct_family_from", []) for a in out.get(ref, [])}
        chosen: list[str] = []
        for agent in prefer:
            if agent not in permitted or cfg.family(agent) in banned:
                continue
            if spec.get("distinct_within") and cfg.family(agent) in {cfg.family(a) for a in chosen}:
                continue
            chosen.append(agent)
            if len(chosen) == spec.get("count", 1):
                break
        if len(chosen) < spec.get("count", 1):
            raise AssignmentError(
                f"role '{role}': need {spec.get('count', 1)} agent(s) from {prefer} that are permitted "
                f"({permitted}) and not of families {sorted(banned)}; found {chosen}")
        out[role] = chosen
    return out


def for_claim(cfg: Config, role: str, assignments: dict, permitted: list[str], author: str) -> list[str]:
    """Agents for a per-claim role, excluding the claim author's family.

    Starts from the role's assigned agents and tops up from the preference
    list if exclusion removes some. Returns [] if independence is impossible
    (the caller records RED-12 rather than proceeding).
    """
    spec = cfg.roles[role]
    need = spec.get("count", 1)
    author_family = cfg.family(author) if author in cfg.agents else None
    pool = assignments.get(role, []) + [a for a in spec["prefer"] if a not in assignments.get(role, [])]
    chosen: list[str] = []
    for agent in pool:
        if agent not in permitted or cfg.family(agent) == author_family:
            continue
        if spec.get("distinct_within") and cfg.family(agent) in {cfg.family(a) for a in chosen}:
            continue
        chosen.append(agent)
        if len(chosen) == need:
            break
    return chosen if len(chosen) == need else []
