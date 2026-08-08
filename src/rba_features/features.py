"""Feature functions.

Each feature is a pure function of the current login event and the user's
ProfileState (history strictly before this event). Implementations land in
Step 4 of Phase 1, after EDA (Step 3) confirms which signals matter.

Design contract (do not break):
    - A feature reads ONLY `event` and `profile` (no global/current-time state).
    - `compute_features` and `update_profile` are the two entry points used by
      both the offline replay driver and the online decision service.
"""

from __future__ import annotations

from typing import Any, Mapping

from rba_features.profile import ProfileState

# The initial feature set planned in plans/development_plan.md section 5.
# Implemented in Step 4.
FEATURE_NAMES: tuple[str, ...] = (
    "device_type_seen_before",
    "os_seen_before",
    "browser_seen_before",
    "ip_seen_before",
    "asn_seen_before",
    "country_seen_before",
    "region_seen_before",
    "city_seen_before",
    "unusual_login_hour",
    "seconds_since_last_login",
    "distance_from_last_login_km",
    "impossible_travel",
    "rtt_deviation_from_user_mean",
    "failed_logins_last_hour",
    "user_login_count",
)


def compute_features(event: Mapping[str, Any], profile: ProfileState) -> dict[str, Any]:
    """Return the feature vector for `event` given the user's prior `profile`.

    Implemented in Step 4.
    """
    raise NotImplementedError("Feature computation is implemented in Phase 1, Step 4.")


def update_profile(profile: ProfileState, event: Mapping[str, Any]) -> ProfileState:
    """Fold `event` into `profile`, returning the state that includes it.

    Called AFTER `compute_features`, so the current event never leaks into its
    own feature vector. Implemented in Step 4.
    """
    raise NotImplementedError("Profile update is implemented in Phase 1, Step 4.")
