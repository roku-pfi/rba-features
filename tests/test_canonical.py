"""Browser / OS families and the population counters (ADR-0042)."""

from datetime import datetime, timezone

from rba_features.canonical import browser_family, canonical_event, os_family
from rba_features.features import compute_features, update_profile
from rba_features.population import TOTAL_FIELD, population_fields
from rba_features.profile import ProfileState


def test_training_strings_and_hosted_login_values_meet_at_the_family():
    for raw, family in [
        ("Chrome Mobile 81.0.4044.1925", "Chrome"),
        ("Chrome 73.0.3654", "Chrome"),
        ("Chrome Mobile WebView 85.0.4183", "Chrome"),
        ("Mobile Safari 13.1", "Safari"),
        ("Firefox 20.0.0.1610", "Firefox"),
        ("Opera Mobile 52.1.2254", "Opera"),
        ("Android 2.3.3.2660", "Android Browser"),
    ]:
        assert browser_family(raw) == family
        assert browser_family(family) == family  # idempotent
    for raw, family in [
        ("Mac OS X 10.14.6", "macOS"),
        ("iOS 13.4", "iOS"),
        ("Android 13.0", "Android"),
        ("Chrome OS 5978.98.0", "Chrome OS"),
        ("Ubuntu", "Linux"),
    ]:
        assert os_family(raw) == family
        assert os_family(family) == family
    assert browser_family(None) is None and os_family("-") == "-"


def _login(**kw):
    base = dict(
        login_timestamp=datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc),
        ip_address="203.0.113.10", asn="7303", country="AR",
        device_type="desktop", os="Mac OS X 10.14.6", browser="Chrome 130.0.6723",
        login_successful=True,
    )
    base.update(kw)
    return base


def test_a_new_version_of_the_same_browser_is_familiar():
    profile = update_profile(ProfileState(), _login())
    features = compute_features(_login(os="macOS", browser="Chrome 131.0.1"), profile)
    assert features["os_seen_before"] == features["browser_seen_before"] == 1
    assert profile.freeman_counts["browser"] == {"Chrome": 1}


def test_population_fields_use_families_and_skip_missing():
    fields = population_fields(_login(asn="-"))
    assert "browser=Chrome" in fields and "os=macOS" in fields and "hour=1" in fields
    assert not any(f.startswith("asn=") for f in fields)
    assert TOTAL_FIELD not in fields
