"""Per-user profile state.

ProfileState is the compact, serializable accumulator that summarises everything
we have seen about a user *before* the current login attempt. Every feature is a
pure function of (current_event, profile_state), so this object is the single
source of "history" both offline and online:

    - Offline (training): rebuilt incrementally by replaying a user's events in
      timestamp order (see replay.py). This mechanically enforces "past-only"
      information and prevents label/temporal leakage.
    - Online (serving): materialised in Redis by the profile-service and loaded
      on each request.

Keep this object small and JSON-serialisable: it will be stored per user.

NOTE: the concrete fields below are a starting point for Phase 1 (Step 4) and
will be refined once EDA (Step 3) tells us which signals actually matter.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProfileState:
    """Rolling summary of a user's past logins."""

    login_count: int = 0
    last_login_ts: float | None = None  # epoch seconds
    last_lat: float | None = None
    last_lon: float | None = None

    seen_countries: set[str] = field(default_factory=set)
    seen_regions: set[str] = field(default_factory=set)
    seen_cities: set[str] = field(default_factory=set)
    seen_ips: set[str] = field(default_factory=set)
    seen_asns: set[str] = field(default_factory=set)
    seen_device_types: set[str] = field(default_factory=set)
    seen_os: set[str] = field(default_factory=set)
    seen_browsers: set[str] = field(default_factory=set)

    rtt_sum: float = 0.0
    rtt_count: int = 0

    @property
    def rtt_mean(self) -> float | None:
        return self.rtt_sum / self.rtt_count if self.rtt_count else None
