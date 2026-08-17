"""rba-features: shared feature library for risk-based authentication.

This package is imported by BOTH the offline ML pipeline (rba-ml-training) and,
later, the online decision service. A single implementation of every feature is
the mechanism that guarantees train/serve parity (see plans/development_plan.md
sections 3-5).

Public surface:
    - schema:   canonical column names / login-event field definitions
    - profile:  ProfileState, the per-user accumulator passed to every feature
    - features: the feature functions f(event, profile_state) -> value
    - replay:   offline event-replay driver used to build training vectors
"""

from rba_features import features, profile, replay, schema  # noqa: F401
from rba_features.profile import (  # noqa: F401
    FREEMAN_COUNT_FEATURES,
    ProfileState,
    profile_from_dict,
    profile_to_dict,
)
from rba_features.travel import (  # noqa: F401
    SPEED_KMH_THRESHOLD,
    TravelSignals,
    compute_travel,
    is_vpn_or_hosting,
)

__version__ = "0.1.2"
