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

The fields below back the Phase 1 feature set (see features.FEATURE_NAMES), chosen
from the EDA findings: the faithful per-user "seen-before" signals plus a few
behavioural ones. RTT and absolute geo distance were intentionally excluded (RTT is
~94% missing; geo is synthesised and region/city are ~42% missing).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Retain at most this many recent failed-login timestamps per user (bounds memory;
# only the last 24h are ever counted by the feature).
_MAX_FAILED_TS = 256


@dataclass
class ProfileState:
    """Rolling summary of a user's past logins (state strictly before "now")."""

    login_count: int = 0
    last_login_ts: float | None = None  # epoch seconds of the most recent prior login

    seen_ips: set[str] = field(default_factory=set)
    seen_asns: set[str] = field(default_factory=set)
    seen_countries: set[str] = field(default_factory=set)
    seen_device_types: set[str] = field(default_factory=set)
    seen_os: set[str] = field(default_factory=set)
    seen_browsers: set[str] = field(default_factory=set)
    seen_hours: set[int] = field(default_factory=set)

    # Epoch seconds of prior failed logins, kept sorted-ish by insertion (append).
    failed_login_ts: list[float] = field(default_factory=list)

    def trim_failed(self) -> None:
        if len(self.failed_login_ts) > _MAX_FAILED_TS:
            self.failed_login_ts = self.failed_login_ts[-_MAX_FAILED_TS:]
