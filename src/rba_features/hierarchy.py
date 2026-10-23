"""Freeman's hierarchical features, rooted at the population (ADR-0043).

Two features, each a nested hierarchy (Freeman et al. 2016, Sect. II-C):

    network: world → country → ASN → IP
    agent:   world → device → device+OS → device+OS+browser   (families)

For a path x with ancestor h at level k (k = 0 the world, L the leaf):

    p_k(x) = max(c(x), 1) / (N_h + M_h) · N_h / N      (k < L; 0 if c(h) = 0)
    p_L(x) = c(x) / N
    M_h    = (L − k) · |h|                            (μ_h = |h|: unseen leaves per entity)
    p(x)   = mean_k p_k(x)                            (uniform interpolation)

`|h|` is the number of distinct leaves seen under h. The same estimate over the
user's own counts gives p(x | u), except that its world level is the
population's p(x) (the rooting of finding 2026-10-23-hierarchical): a value new
at every level then costs log 4, and among values new to the user, those common
in the population look more like an attacker. Each hierarchy contributes
log p(x) − log p(x | u); a user with no history contributes 0.

Counts are stored flat, keyed by the prefix joined with SEP ("" is the world):
`counts[key]` = logins under that prefix, `leaves[key]` = distinct leaves under it.
The same layout serves the per-user profile, the training artifact and the
deployment's population in Redis.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Mapping

from rba_features.canonical import canonical_event
from rba_features.features import is_missing

HIERARCHIES: dict[str, tuple[str, ...]] = {
    "network": ("country", "asn", "ip_address"),
    "agent": ("device_type", "os", "browser"),
}
SEP = "\x1f"
MISSING = "-"

Lookup = Callable[[str], int]


def hier_path(event: Mapping[str, Any], name: str) -> tuple[str, ...]:
    """The login's path in one hierarchy: families, strings, "-" for missing."""
    event = canonical_event(event)
    return tuple(
        MISSING if is_missing(event.get(field)) else str(event.get(field))
        for field in HIERARCHIES[name]
    )


def prefix_key(path: tuple[str, ...], k: int) -> str:
    return SEP.join(path[:k])


def hier_add(counts: dict[str, int], leaves: dict[str, int], path: tuple[str, ...]) -> None:
    """Fold one login into counts / distinct-leaf counts (in place)."""
    depth = len(path)
    for k in range(depth + 1):
        key = prefix_key(path, k)
        counts[key] = counts.get(key, 0) + 1
    if counts[prefix_key(path, depth)] == 1:  # a leaf seen for the first time
        for k in range(depth):
            key = prefix_key(path, k)
            leaves[key] = leaves.get(key, 0) + 1


def level_probs(count: Lookup, leaves: Lookup, path: tuple[str, ...]) -> list[float]:
    """[p_0(x), …, p_L(x)] from count / distinct-leaf lookups (0 for unknown keys)."""
    depth = len(path)
    n = count("")
    if n == 0:
        return [0.0] * (depth + 1)
    c_leaf = count(prefix_key(path, depth))
    out = []
    for k in range(depth + 1):
        if k == depth:
            out.append(c_leaf / n)
            continue
        key = prefix_key(path, k)
        n_h = count(key)
        if n_h == 0:
            out.append(0.0)
            continue
        m_h = (depth - k) * leaves(key)
        out.append(max(c_leaf, 1) / (n_h + m_h) * (n_h / n))
    return out


def population_p(
    train: tuple[Lookup, Lookup],
    deployment: tuple[Lookup, Lookup] | None,
    path: tuple[str, ...],
    kappa: float | None,
) -> float:
    """p(x): the deployment's estimate blended with training's (ADR-0042, κ logins)."""
    p_train = _mean(level_probs(*train, path))
    if deployment is None or kappa is None:
        return p_train
    n_dep = deployment[0]("")
    if n_dep == 0:
        return p_train
    p_dep = _mean(level_probs(*deployment, path))
    return (n_dep * p_dep + kappa * p_train) / (n_dep + kappa)


def contribution(user: tuple[Lookup, Lookup], path: tuple[str, ...], p_global: float) -> float:
    """log p(x) − log p(x | u) for one hierarchy; 0 without history."""
    if user[0]("") == 0:
        return 0.0
    levels = level_probs(*user, path)
    levels[0] = p_global
    return math.log(p_global) - math.log(_mean(levels))


def familiar_depth(user_count: Lookup, path: tuple[str, ...]) -> int:
    """How many levels of `path` the user has seen (0 = nothing, L = the exact leaf)."""
    depth = 0
    for k in range(1, len(path) + 1):
        if user_count(prefix_key(path, k)) == 0:
            break
        depth = k
    return depth


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)
