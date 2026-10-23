"""When a decision may teach the profile (ADR-0042)."""

from rba_features.features import learn_at_decision


def test_failed_password_is_recorded_at_once():
    assert learn_at_decision(False, "ALLOW")
    assert learn_at_decision(False, "BLOCK")


def test_allowed_login_is_learned_at_once():
    assert learn_at_decision(True, "ALLOW")
    assert learn_at_decision(None, "ALLOW")


def test_step_up_waits_for_confirmation_and_block_is_never_learned():
    for action in ("REQUIRE_MFA", "REAUTHENTICATE", "BLOCK"):
        assert not learn_at_decision(True, action)
