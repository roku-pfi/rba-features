"""Hierarchical Freeman rooted at the population (ADR-0043)."""

import math
import random
from collections import defaultdict
from datetime import datetime, timezone

from rba_features.features import update_profile
from rba_features.hierarchy import (
    contribution,
    familiar_depth,
    hier_add,
    hier_path,
    level_probs,
    population_p,
)
from rba_features.population import hier_read_fields, learn_population
from rba_features.profile import ProfileState, profile_from_dict, profile_to_dict


def _reference_levels(seen: list[tuple], path: tuple) -> list[float]:
    """The set-based estimate of the offline evaluation (ml/models/hierarchical.py)."""
    n, depth = len(seen), len(path)
    count = defaultdict(int)
    leaves = defaultdict(set)
    for p in seen:
        for k in range(1, depth + 1):
            count[p[:k]] += 1
        for k in range(depth):
            leaves[p[:k]].add(p)
    out = []
    for k in range(depth + 1):
        if k == depth:
            out.append(count[path] / n)
            continue
        n_h = n if k == 0 else count[path[:k]]
        if n_h == 0:
            out.append(0.0)
            continue
        out.append(max(count[path], 1) / (n_h + (depth - k) * len(leaves[path[:k]])) * n_h / n)
    return out


def test_flat_counts_match_the_set_based_estimate():
    rng = random.Random(3)
    seen = [(rng.choice("AB"), rng.choice("xyz"), str(rng.randrange(6))) for _ in range(200)]
    counts, leaves = {}, {}
    for p in seen:
        hier_add(counts, leaves, p)
    for probe in [seen[0], ("A", "x", "99"), ("A", "q", "1"), ("C", "x", "1")]:
        got = level_probs(lambda k: counts.get(k, 0), lambda k: leaves.get(k, 0), probe)
        assert got == [pytest_approx(v) for v in _reference_levels(seen, probe)]


def pytest_approx(v):
    import pytest

    return pytest.approx(v, rel=1e-12, abs=1e-15)


def _login(**kw):
    base = dict(
        login_timestamp=datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc),
        ip_address="203.0.113.10", asn="7303", country="AR",
        device_type="desktop", os="Mac OS X 10.14.6", browser="Chrome 130.0",
        login_successful=True,
    )
    base.update(kw)
    return base


def test_profile_keeps_hierarchical_counts_for_learned_logins_only():
    profile = ProfileState()
    update_profile(profile, _login())
    update_profile(profile, _login(login_successful=False))
    assert profile.hier_counts["network"][""] == 1
    assert hier_path(_login(), "agent") == ("desktop", "macOS", "Chrome")
    assert profile_from_dict(profile_to_dict(profile)).hier_counts == profile.hier_counts


def _lookups(profile, name):
    c, l = profile.hier_counts.get(name, {}), profile.hier_leaves.get(name, {})
    return (lambda k: c.get(k, 0), lambda k: l.get(k, 0))


def test_rooted_contributions_rank_novelty_once_and_bounded():
    profile = ProfileState()
    for _ in range(10):
        update_profile(profile, _login())
    user = _lookups(profile, "network")
    p_g = 1e-4
    usual = contribution(user, hier_path(_login(), "network"), p_g)
    new_ip = contribution(user, hier_path(_login(ip_address="203.0.113.99"), "network"), p_g)
    new_country = contribution(user, hier_path(_login(country="JP", asn="16509", ip_address="18.0.0.1"), "network"), p_g)
    assert usual < new_ip < new_country
    assert new_country == pytest_approx(math.log(4))  # new at every level: −log λ₀
    assert familiar_depth(user[0], hier_path(_login(ip_address="203.0.113.99"), "network")) == 2
    assert contribution(_lookups(ProfileState(), "network"), hier_path(_login(), "network"), p_g) == 0.0


def test_population_blend_and_counters():
    store: dict[str, int] = {}

    def hincrby(field, n):
        store[field] = store.get(field, 0) + n
        return store[field]

    learn_population(_login(), hincrby)
    learn_population(_login(), hincrby)
    assert store["h:network:"] == 2 and store["d:network:"] == 1
    fields = hier_read_fields(_login())
    assert "h:agent:" in fields and all(f.startswith(("h:", "d:")) for f in fields)

    train = ({"": 100, "AR": 1}.get, {"": 50, "AR": 1}.get)
    train = (lambda k: {"": 100, "AR": 1}.get(k, 0), lambda k: {"": 50, "AR": 1}.get(k, 0))
    dep = (lambda k: store.get(f"h:network:{k}", 0), lambda k: store.get(f"d:network:{k}", 0))
    path = hier_path(_login(), "network")
    p_train = population_p(train, None, path, 100)
    p_mixed = population_p(train, dep, path, 100)
    assert p_mixed > p_train  # the deployment has seen this network, training barely has
