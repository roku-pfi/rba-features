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

__version__ = "0.1.0"
