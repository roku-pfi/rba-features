"""The deployment's own login population, Freeman's attacker model (ADR-0042).

Freeman scores a login by how common its values are in the population
(`p_global`, standing in for "a login by anyone") against how common they are
for the user. The training data is a different service's population (2020,
mostly Norway): there, a login from Argentina at 22:00 local time is rare, so
in our deployment every familiar value looked like overwhelming evidence of the
user and an attacker using his browser at his hour scored LOW.

The deployment therefore counts its own population, with the training data as
a Dirichlet prior of strength kappa:

    p_global(v) = (N_dep(v) + kappa * p_train(v)) / (N_dep + kappa)

Only learned logins are counted (an ALLOW, or a passed step-up), so attackers
who stop at the passkey never shape the population. This module only names the
counters; the stores live in profile-service (writes) and the PDP (reads).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from rba_features.canonical import canonical_event
from rba_features.features import freeman_value
from rba_features.profile import FREEMAN_COUNT_FEATURES

TOTAL_FIELD = "_total"


def field_name(feature: str, value: str) -> str:
    return f"{feature}={value}"


def population_fields(event: Mapping[str, Any]) -> list[str]:
    """Counter fields a learned login increments (besides TOTAL_FIELD)."""
    event = canonical_event(event)
    fields = []
    for feature in FREEMAN_COUNT_FEATURES:
        value = freeman_value(feature, event)
        if value is not None:
            fields.append(field_name(feature, value))
    return fields


@dataclass
class PopulationCounts:
    """What the deployment has seen of one login's values: N_dep(v) and N_dep."""

    total: int = 0
    counts: dict[str, int] = field(default_factory=dict)  # field_name → count

    def count(self, feature: str, value: str) -> int:
        return self.counts.get(field_name(feature, value), 0)
