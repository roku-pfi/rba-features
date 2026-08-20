"""Country-centroid travel rule — not a Freeman feature (ADR-0022)."""

from __future__ import annotations

from datetime import datetime, timedelta

from rba_features.features import compute_features, update_profile
from rba_features.profile import ProfileState, profile_from_dict, profile_to_dict
from rba_features.travel import (
    SPEED_KMH_THRESHOLD,
    compute_travel,
    haversine_km,
    is_vpn_or_hosting,
)


def _event(ts, *, country="AR", asn="7303", success=True, **extra):
    row = {
        "login_timestamp": ts,
        "ip_address": extra.get("ip", "203.0.113.10"),
        "asn": asn,
        "country": country,
        "device_type": "mobile",
        "os": "Android",
        "browser": "Chrome",
        "login_successful": success,
    }
    return row


def test_haversine_ar_jp_is_intercontinental():
    # Geographic centres in country_centroids.py — thousands of km, not city GPS.
    ar = (-38.42, -63.62)
    jp = (36.20, 138.25)
    km = haversine_km(*ar, *jp)
    assert km > 15000


def test_first_login_never_travels():
    ts = datetime(2020, 6, 1, 12, 0, 0)
    sig = compute_travel(_event(ts, country="JP"), ProfileState())
    assert sig.impossible_travel is False
    assert sig.vpn_or_hosting is False


def test_missing_country_never_fires():
    ts = datetime(2020, 6, 1, 12, 0, 0)
    profile = ProfileState()
    update_profile(profile, _event(ts, country="AR"))
    sig = compute_travel(
        _event(ts + timedelta(hours=1), country="-"),
        profile,
    )
    assert sig.impossible_travel is False


def test_same_country_never_fires():
    ts = datetime(2020, 6, 1, 12, 0, 0)
    profile = ProfileState()
    update_profile(profile, _event(ts, country="AR"))
    sig = compute_travel(_event(ts + timedelta(hours=1), country="AR"), profile)
    assert sig.impossible_travel is False
    assert profile.last_login_country == "AR"


def test_teleport_fires_above_speed_threshold():
    ts = datetime(2020, 6, 1, 12, 0, 0)
    profile = ProfileState()
    update_profile(profile, _event(ts, country="AR"))
    sig = compute_travel(_event(ts + timedelta(hours=1), country="JP"), profile)
    assert sig.impossible_travel is True
    assert sig.vpn_or_hosting is False
    assert sig.from_country == "AR"
    assert sig.to_country == "JP"
    assert sig.distance_km is not None and sig.distance_km > 15000
    assert sig.speed_kmh is not None and sig.speed_kmh > SPEED_KMH_THRESHOLD


def test_slow_intercontinental_does_not_fire():
    ts = datetime(2020, 6, 1, 12, 0, 0)
    profile = ProfileState()
    update_profile(profile, _event(ts, country="AR"))
    # ~18 000 km at 1000 km/h needs ~18h; two days is ordinary travel.
    sig = compute_travel(_event(ts + timedelta(days=2), country="JP"), profile)
    assert sig.impossible_travel is False
    assert sig.speed_kmh is not None and sig.speed_kmh < SPEED_KMH_THRESHOLD


def test_vpn_skips_teleport_and_does_not_move_home_anchor():
    ts = datetime(2020, 6, 1, 12, 0, 0)
    profile = ProfileState()
    update_profile(profile, _event(ts, country="AR", asn="7303"))
    assert profile.last_login_country == "AR"

    vpn = _event(ts + timedelta(hours=1), country="US", asn="13335")
    assert is_vpn_or_hosting("13335")
    sig = compute_travel(vpn, profile)
    assert sig.vpn_or_hosting is True
    assert sig.impossible_travel is False

    update_profile(profile, vpn)
    assert profile.last_login_country == "AR"
    assert profile.last_success_login_ts == ts.timestamp()


def test_failed_login_establishes_nothing():
    """ADR-0027: a failure moves no anchor, no clock, and no seen-set.

    Otherwise repeated failure from the attacker's own context would make that
    context familiar — the failure counter would lower risk instead of raising it.
    """
    ts = datetime(2020, 6, 1, 12, 0, 0)
    failed_at = ts + timedelta(hours=1)
    profile = ProfileState()
    update_profile(profile, _event(ts, country="AR"))
    update_profile(profile, _event(failed_at, country="JP", success=False))

    assert profile.last_login_country == "AR"
    assert profile.last_success_login_ts == ts.timestamp()
    assert profile.last_login_ts == ts.timestamp()
    assert profile.login_count == 1
    assert "JP" not in profile.seen_countries
    assert profile.freeman_count("country", "JP") == 0
    assert profile.failed_login_ts == [failed_at.timestamp()]


def test_travel_offline_online_parity():
    ts = datetime(2020, 6, 1, 12, 0, 0)
    events = [
        _event(ts, country="AR"),
        _event(ts + timedelta(hours=1), country="JP"),
        _event(ts + timedelta(hours=2), country="US", asn="13335"),
        _event(ts + timedelta(hours=3), country="-"),
    ]
    offline = []
    profile = ProfileState()
    for ev in events:
        offline.append(compute_travel(ev, profile))
        update_profile(profile, ev)

    online = []
    restored = profile_from_dict(None)
    for ev in events:
        online.append(compute_travel(ev, restored))
        update_profile(restored, ev)
        restored = profile_from_dict(profile_to_dict(restored))

    assert offline == online
    assert offline[0].impossible_travel is False
    assert offline[1].impossible_travel is True
    assert offline[2].vpn_or_hosting is True and offline[2].impossible_travel is False
    assert offline[3].impossible_travel is False


def test_compute_features_vector_excludes_travel_flags():
    """Travel must not leak into FEATURE_NAMES / Freeman (parity contract)."""
    from rba_features.features import FEATURE_NAMES

    ts = datetime(2020, 6, 1, 12, 0, 0)
    profile = ProfileState()
    update_profile(profile, _event(ts, country="AR"))
    vec = compute_features(_event(ts + timedelta(hours=1), country="JP"), profile)
    assert set(vec) == set(FEATURE_NAMES)
    assert "impossible_travel" not in vec
