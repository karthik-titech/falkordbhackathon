"""Deterministic tie strength from public features or an owner override."""

import math


def tie_strength(features: dict, owner_strength: float | None = None) -> tuple[float, str]:
    if owner_strength is not None:
        if not 0 <= owner_strength <= 1:
            raise ValueError("Owner strength must be in [0, 1]")
        return round(owner_strength, 3), "owner"
    x = (0.35 * min(features.get("shared_repos", 0), 5)
         + 0.6 * bool(features.get("coauthored", False))
         + 0.25 * bool(features.get("mutual_follow", False))
         + 0.5 * bool(features.get("met_today", False))
         + 0.3 * bool(features.get("same_company", False)))
    if not math.isfinite(x):
        raise ValueError("Tie features must be finite")
    return round(1 - math.exp(-x), 3), "formula"
