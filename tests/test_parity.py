"""Feature + train/serve parity tests.

The parity test is the insurance policy of the whole project: the same events
pushed through the offline replay path and an independent online-style path
(materialise profile, then score the next event) must produce identical feature
vectors.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from rba_features.features import FEATURE_NAMES, compute_features, update_profile
from rba_features.profile import ProfileState
from rba_features.replay import replay_user


def _event(ts, ip="1.1.1.1", asn="100", country="NO", device="mobile",
           os_="iOS 13.4", browser="Firefox 20", success=True):
    return {
        "login_timestamp": ts,
        "ip_address": ip,
        "asn": asn,
        "country": country,
        "device_type": device,
        "os": os_,
        "browser": browser,
        "login_successful": success,
    }


def _sequence():
    base = datetime(2020, 2, 3, 12, 0, 0)
    return [
        _event(base),                                            # first login: all new
        _event(base + timedelta(hours=1)),                       # same everything, 1h later
        _event(base + timedelta(days=1), ip="9.9.9.9", country="US"),  # new ip + country
        _event(base + timedelta(days=1, minutes=5), success=False),    # failed
        _event(base + timedelta(days=1, minutes=10), success=False),   # failed
    ]


def test_first_login_everything_is_new():
    vec = compute_features(_sequence()[0], ProfileState())
    assert vec["user_login_count"] == 0
    assert vec["ip_seen_before"] == 0
    assert vec["country_seen_before"] == 0
    assert vec["hour_seen_before"] == 0
    assert vec["seconds_since_last_login"] == -1.0
    assert vec["failed_logins_last_24h"] == 0


def test_seen_before_and_time_gap():
    events = _sequence()
    vecs = list(replay_user(events))
    # Second login: same ip/country/hour as the first -> seen before; 3600s gap.
    assert vecs[1]["ip_seen_before"] == 1
    assert vecs[1]["country_seen_before"] == 1
    assert vecs[1]["user_login_count"] == 1
    assert vecs[1]["seconds_since_last_login"] == 3600.0
    # Third login: new ip + new country.
    assert vecs[2]["ip_seen_before"] == 0
    assert vecs[2]["country_seen_before"] == 0


def test_failed_logins_windowed():
    events = _sequence()
    vecs = list(replay_user(events))
    # The 5th event is preceded by exactly one prior failed login (the 4th),
    # both within 24h.
    assert vecs[4]["failed_logins_last_24h"] == 1


def test_missing_values_not_counted_as_seen():
    base = datetime(2020, 2, 3, 12, 0, 0)
    events = [
        _event(base, country="-"),                       # missing country
        _event(base + timedelta(hours=1), country="-"),  # missing again
    ]
    vecs = list(replay_user(events))
    # A missing ("-") country must never count as "seen before".
    assert vecs[1]["country_seen_before"] == 0


def test_offline_online_parity():
    """Independent online-style reconstruction must equal offline replay output."""
    events = _sequence()
    offline = list(replay_user(events))

    online = []
    profile = ProfileState()
    for ev in events:
        online.append(compute_features(ev, profile))
        update_profile(profile, ev)

    assert offline == online
    for vec in offline:
        assert set(vec) == set(FEATURE_NAMES)
