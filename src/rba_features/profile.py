"""Per-user profile state.

ProfileState is the compact, serializable accumulator that summarises everything
we have seen about a user *before* the current login attempt. Every feature is a
pure function of (current_event, profile_state), so this object is the single
source of "history" both offline and online:

    - Offline (training): rebuilt incrementally by replaying a user's events in
      timestamp order (see replay.py). This mechanically enforces "past-only"
      information and prevents label/temporal leakage.
    - Online (serving): materialised in Redis by the profile-service (and, during
      Phase 3, optionally by decision-service) and loaded on each request.

The fields below back the Phase 1 feature set (see features.FEATURE_NAMES), chosen
from the EDA findings: the faithful per-user "seen-before" signals plus a few
behavioural ones. RTT and absolute geo distance were intentionally excluded (RTT is
~94% missing; geo is synthesised and region/city are ~42% missing).

`freeman_counts` / `freeman_totals` carry the per-value counts the Freeman scorer
needs online (ADR-0008 Phase 3 follow-up). Seen-sets remain the source for
`*_seen_before` features; counts are the source for online LLRs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Retain at most this many recent failed-login timestamps per user (bounds memory;
# only the last 24h are ever counted by the feature).
_MAX_FAILED_TS = 256

# Freeman categorical keys whose per-value counts are materialised for online scoring.
# Must stay aligned with rba_ml_training.ml.models.freeman.FREEMAN_FEATURES (and
# rba_contracts.FREEMAN_FEATURES). `hour` is stored as a decimal string ("12").
FREEMAN_COUNT_FEATURES: tuple[str, ...] = (
    "ip_address",
    "asn",
    "country",
    "device_type",
    "os",
    "browser",
    "hour",
)


@dataclass
class ProfileState:
    """Rolling summary of a user's past logins (state strictly before "now")."""

    login_count: int = 0
    last_login_ts: float | None = None  # epoch seconds of the most recent prior login
    # Travel-rule anchors (ADR-0022): last *successful* non-VPN login only.
    last_login_country: str | None = None
    last_success_login_ts: float | None = None

    seen_ips: set[str] = field(default_factory=set)
    seen_asns: set[str] = field(default_factory=set)
    seen_countries: set[str] = field(default_factory=set)
    seen_device_types: set[str] = field(default_factory=set)
    seen_os: set[str] = field(default_factory=set)
    seen_browsers: set[str] = field(default_factory=set)
    seen_hours: set[int] = field(default_factory=set)

    # Epoch seconds of prior failed logins, kept sorted-ish by insertion (append).
    failed_login_ts: list[float] = field(default_factory=list)

    # Per-value counts for Freeman online scoring: feature -> {value_str: count}.
    freeman_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    freeman_totals: dict[str, int] = field(default_factory=dict)

    def trim_failed(self) -> None:
        if len(self.failed_login_ts) > _MAX_FAILED_TS:
            self.failed_login_ts = self.failed_login_ts[-_MAX_FAILED_TS:]

    def freeman_count(self, feature: str, value: str) -> int:
        return self.freeman_counts.get(feature, {}).get(value, 0)

    def freeman_total(self, feature: str) -> int:
        return self.freeman_totals.get(feature, 0)


def profile_to_dict(profile: ProfileState) -> dict[str, Any]:
    """JSON-friendly snapshot for Redis / fixtures."""
    return {
        "login_count": profile.login_count,
        "last_login_ts": profile.last_login_ts,
        "last_login_country": profile.last_login_country,
        "last_success_login_ts": profile.last_success_login_ts,
        "seen_ips": sorted(profile.seen_ips),
        "seen_asns": sorted(profile.seen_asns),
        "seen_countries": sorted(profile.seen_countries),
        "seen_device_types": sorted(profile.seen_device_types),
        "seen_os": sorted(profile.seen_os),
        "seen_browsers": sorted(profile.seen_browsers),
        "seen_hours": sorted(profile.seen_hours),
        "failed_login_ts": list(profile.failed_login_ts),
        "freeman_counts": {
            f: dict(counts) for f, counts in profile.freeman_counts.items()
        },
        "freeman_totals": dict(profile.freeman_totals),
    }


def profile_from_dict(data: dict[str, Any] | None) -> ProfileState:
    """Hydrate ProfileState from a Redis / fixture dict. None → empty profile."""
    if not data:
        return ProfileState()
    return ProfileState(
        login_count=int(data.get("login_count", 0)),
        last_login_ts=data.get("last_login_ts"),
        last_login_country=(
            str(data["last_login_country"])
            if data.get("last_login_country") is not None
            else None
        ),
        last_success_login_ts=(
            float(data["last_success_login_ts"])
            if data.get("last_success_login_ts") is not None
            else None
        ),
        seen_ips=set(data.get("seen_ips") or []),
        seen_asns=set(data.get("seen_asns") or []),
        seen_countries=set(data.get("seen_countries") or []),
        seen_device_types=set(data.get("seen_device_types") or []),
        seen_os=set(data.get("seen_os") or []),
        seen_browsers=set(data.get("seen_browsers") or []),
        seen_hours={int(h) for h in (data.get("seen_hours") or [])},
        failed_login_ts=[float(t) for t in (data.get("failed_login_ts") or [])],
        freeman_counts={
            str(f): {str(v): int(c) for v, c in counts.items()}
            for f, counts in (data.get("freeman_counts") or {}).items()
        },
        freeman_totals={
            str(f): int(t) for f, t in (data.get("freeman_totals") or {}).items()
        },
    )
