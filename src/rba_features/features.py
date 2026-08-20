"""Feature functions.

Each feature is a pure function of the current login event and the user's
ProfileState (history strictly before this event). `compute_features` and
`update_profile` are the two entry points used by BOTH the offline replay driver
and (later) the online decision service — this shared implementation is what
guarantees train/serve parity.

Contract (do not break):
    - `compute_features(event, profile)` reads only `event` and `profile`.
    - `update_profile(profile, event)` is called AFTER compute, so the current
      event never leaks into its own feature vector.

Feature set (Phase 1, EDA-informed — see docs/findings/2026-08-08-phase1-eda.md):
    faithful per-user "seen-before" signals + a few behavioural ones. RTT and
    absolute geo distance were intentionally excluded from Freeman. Country-centroid
    impossible travel lives in ``rba_features.travel.compute_travel`` as a PDP
    escalate (ADR-0022), not in FEATURE_NAMES.

Missing values: geo/UA fields use "-" (and NaN) as "missing" in the raw data. A
missing categorical is treated as "not seen before" (0) and is NOT added to the
profile's seen-set, so missingness never counts as a match.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

from rba_features.profile import FREEMAN_COUNT_FEATURES, ProfileState

# Event field names (canonical snake_case; see schema.RAW_TO_FIELD).
F_TS = "login_timestamp"
F_IP = "ip_address"
F_ASN = "asn"
F_COUNTRY = "country"
F_DEVICE = "device_type"
F_OS = "os"
F_BROWSER = "browser"
F_SUCCESS = "login_successful"

_MISSING_TOKENS = {"", "-", "nan", "none", "null"}
_WINDOW_SECONDS = 24 * 3600
_NO_PRIOR = -1.0  # sentinel for seconds_since_last_login when there is no prior login

FEATURE_NAMES: tuple[str, ...] = (
    "user_login_count",
    "ip_seen_before",
    "asn_seen_before",
    "country_seen_before",
    "device_type_seen_before",
    "os_seen_before",
    "browser_seen_before",
    "hour_seen_before",
    "seconds_since_last_login",
    "failed_logins_last_24h",
)


def is_missing(value: Any) -> bool:
    """True for NaN/None/empty or the dataset's "-" placeholder."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in _MISSING_TOKENS


def to_epoch(ts: Any) -> float | None:
    """Convert a timestamp (datetime / pandas Timestamp / ISO string) to epoch seconds."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return None if (isinstance(ts, float) and math.isnan(ts)) else float(ts)
    if isinstance(ts, datetime):
        return ts.timestamp()
    # pandas Timestamp exposes .timestamp(); NaT raises -> treat as missing.
    ts_method = getattr(ts, "timestamp", None)
    if callable(ts_method):
        try:
            return float(ts_method())
        except (ValueError, OverflowError):
            return None
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except ValueError:
        return None


def _hour_of(ts: Any) -> int | None:
    if isinstance(ts, datetime):
        return ts.hour
    hour_attr = getattr(ts, "hour", None)
    return int(hour_attr) if hour_attr is not None else None


def _seen(value: Any, seen: set) -> int:
    return 0 if is_missing(value) else int(value in seen)


def compute_features(event: Mapping[str, Any], profile: ProfileState) -> dict[str, Any]:
    """Return the feature vector for `event` given the user's prior `profile`."""
    now = to_epoch(event.get(F_TS))
    hour = _hour_of(event.get(F_TS))

    if now is not None and profile.last_login_ts is not None:
        seconds_since = now - profile.last_login_ts
    else:
        seconds_since = _NO_PRIOR

    if now is None:
        failed_24h = 0
    else:
        cutoff = now - _WINDOW_SECONDS
        failed_24h = sum(1 for t in profile.failed_login_ts if t >= cutoff)

    return {
        "user_login_count": profile.login_count,
        "ip_seen_before": _seen(event.get(F_IP), profile.seen_ips),
        "asn_seen_before": _seen(event.get(F_ASN), profile.seen_asns),
        "country_seen_before": _seen(event.get(F_COUNTRY), profile.seen_countries),
        "device_type_seen_before": _seen(event.get(F_DEVICE), profile.seen_device_types),
        "os_seen_before": _seen(event.get(F_OS), profile.seen_os),
        "browser_seen_before": _seen(event.get(F_BROWSER), profile.seen_browsers),
        "hour_seen_before": int(hour in profile.seen_hours) if hour is not None else 0,
        "seconds_since_last_login": seconds_since,
        "failed_logins_last_24h": failed_24h,
    }


def _add(value: Any, seen: set) -> None:
    if not is_missing(value):
        seen.add(value)


def _freeman_value(feature: str, event: Mapping[str, Any]) -> str | None:
    """Value string as Freeman offline scoring would see it (`astype(str)`), or None to skip.

    Missing categoricals are skipped so they never inflate user counts (matches
    seen-set policy). `hour` is always the decimal hour string when timestamp parses.
    """
    if feature == "hour":
        hour = _hour_of(event.get(F_TS))
        return None if hour is None else str(int(hour))
    raw = event.get(feature)
    if is_missing(raw):
        return None
    return str(raw)


def _bump_freeman_counts(profile: ProfileState, event: Mapping[str, Any]) -> None:
    for feature in FREEMAN_COUNT_FEATURES:
        value = _freeman_value(feature, event)
        if value is None:
            continue
        bucket = profile.freeman_counts.setdefault(feature, {})
        bucket[value] = bucket.get(value, 0) + 1
        profile.freeman_totals[feature] = profile.freeman_totals.get(feature, 0) + 1


def update_profile(profile: ProfileState, event: Mapping[str, Any]) -> ProfileState:
    """Fold `event` into `profile` (mutates and returns it). Call AFTER compute_features.

    **Only a successful login establishes familiarity** (ADR-0027). A failed
    attempt contributes exactly one thing — a timestamp in `failed_login_ts` —
    and touches no seen-set, no Freeman count, no `last_login_ts`, and no
    `login_count`.

    Without that rule the failure counter is self-defeating: an attacker who
    submits wrong passwords from their own IP/country/device thereby teaches the
    profile that their context is normal, so the *next* attempt scores as
    familiar. Repeated failure would lower risk. It also matches what the
    travel anchors below have always done, and it costs little honest signal —
    a legitimate user who mistypes a password succeeds moments later from the
    same context, which establishes it then.

    A missing/None `login_successful` is treated as a success, as elsewhere.
    """
    success = event.get(F_SUCCESS)
    now = to_epoch(event.get(F_TS))

    if success is False:
        if now is not None:
            profile.failed_login_ts.append(now)
            profile.trim_failed()
        return profile

    hour = _hour_of(event.get(F_TS))

    _add(event.get(F_IP), profile.seen_ips)
    _add(event.get(F_ASN), profile.seen_asns)
    _add(event.get(F_COUNTRY), profile.seen_countries)
    _add(event.get(F_DEVICE), profile.seen_device_types)
    _add(event.get(F_OS), profile.seen_os)
    _add(event.get(F_BROWSER), profile.seen_browsers)
    if hour is not None:
        profile.seen_hours.add(hour)

    _bump_freeman_counts(profile, event)

    if now is not None:
        profile.last_login_ts = now

    # Travel anchors: non-missing country, not VPN/hosting (ADR-0022).
    from rba_features.travel import is_vpn_or_hosting, normalize_country

    country = normalize_country(event.get(F_COUNTRY))
    if country is not None and not is_vpn_or_hosting(event.get(F_ASN)):
        profile.last_login_country = country
        if now is not None:
            profile.last_success_login_ts = now

    profile.login_count += 1
    return profile
