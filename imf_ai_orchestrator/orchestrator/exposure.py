"""Information isolation: each role sees only its whitelisted fields."""
from __future__ import annotations

from .config import Config


class ExposureError(RuntimeError):
    pass


def build_input(cfg: Config, role: str, available: dict) -> dict:
    allowed = cfg.exposure["roles"].get(role)
    if allowed is None:
        raise ExposureError(f"no exposure rule for role '{role}'")
    forbidden = set(cfg.exposure.get("forbidden", {}).get(role, []))
    leak = forbidden & set(allowed)
    if leak:
        raise ExposureError(f"exposure config lets blind role '{role}' see {sorted(leak)}")
    return {k: available[k] for k in allowed if k in available and available[k] not in (None, "", [], {})}
