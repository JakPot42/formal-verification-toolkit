"""
Tests for GuardenVerifier (ported from guarden_fv's test_rule_engine.py onto
the shared fv_core.Conflict.names field).
"""
from pathlib import Path

from uav.verifier import GuardenVerifier, load_rule_set

RULE_SETS = Path(__file__).parent.parent / "uav" / "rule_sets"

verifier = GuardenVerifier()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rs(rules: dict) -> dict:
    return {"rule_set_id": "test", "description": "unit test", "rules": rules}


def _max(name: str, alt: int, enabled: bool = True) -> dict:
    return {"rule_name": name, "max_altitude_m": alt, "enabled": enabled}


def _min(name: str, alt: int, absolute: bool = False, enabled: bool = True) -> dict:
    return {"rule_name": name, "min_altitude_m": alt, "is_absolute": absolute, "enabled": enabled}


def _emg(name: str, target: int, overrides: bool, enabled: bool = True) -> dict:
    return {
        "rule_name": name,
        "descent_target_altitude_m": target,
        "overrides_min_altitude": overrides,
        "enabled": enabled,
    }


def _hold(name: str, enabled: bool) -> dict:
    return {"rule_name": name, "trigger": "signal_loss", "action": "HOLD", "enabled": enabled}


def _rth(name: str, enabled: bool) -> dict:
    return {"rule_name": name, "trigger": "signal_loss", "action": "RTH", "enabled": enabled}


# ---------------------------------------------------------------------------
# File-based tests
# ---------------------------------------------------------------------------

def test_rs01_clean_passes():
    rs = load_rule_set(RULE_SETS / "rs_01_clean.json")
    result = verifier.verify(rs)
    assert result.status == "PASS"
    assert result.conflicts == []


def test_rs02_emergency_conflict_fails():
    rs = load_rule_set(RULE_SETS / "rs_02_emergency_conflict.json")
    result = verifier.verify(rs)
    assert result.status == "FAIL"
    assert len(result.conflicts) == 1


def test_rs02_emergency_conflict_names_rules():
    rs = load_rule_set(RULE_SETS / "rs_02_emergency_conflict.json")
    result = verifier.verify(rs)
    conflict = result.conflicts[0]
    assert any("Emergency" in r for r in conflict.names)
    assert any("Absolute Minimum" in r or "Pedestrian" in r for r in conflict.names)


def test_rs02_emergency_conflict_mentions_altitudes():
    rs = load_rule_set(RULE_SETS / "rs_02_emergency_conflict.json")
    result = verifier.verify(rs)
    explanation = result.conflicts[0].explanation
    assert "0m" in explanation or "30m" in explanation


def test_rs03_signal_conflict_fails():
    rs = load_rule_set(RULE_SETS / "rs_03_signal_conflict.json")
    result = verifier.verify(rs)
    assert result.status == "FAIL"
    assert len(result.conflicts) == 1


def test_rs03_signal_conflict_names_rules():
    rs = load_rule_set(RULE_SETS / "rs_03_signal_conflict.json")
    result = verifier.verify(rs)
    conflict = result.conflicts[0]
    assert any("Hold" in r or "HOLD" in r or "hold" in r.lower() for r in conflict.names)
    assert any("Home" in r or "RTH" in r or "rth" in r.lower() for r in conflict.names)


# ---------------------------------------------------------------------------
# Check 1: Altitude range feasibility
# ---------------------------------------------------------------------------

def test_altitude_range_clean_passes():
    rs = _rs({"max_altitude": _max("MaxAlt", 120), "min_altitude": _min("MinAlt", 10)})
    assert verifier.verify(rs).status == "PASS"


def test_altitude_range_equal_boundaries_passes():
    rs = _rs({"max_altitude": _max("MaxAlt", 30), "min_altitude": _min("MinAlt", 30)})
    assert verifier.verify(rs).status == "PASS"


def test_altitude_range_max_below_min_fails():
    rs = _rs({"max_altitude": _max("MaxAlt", 10), "min_altitude": _min("MinAlt", 30)})
    result = verifier.verify(rs)
    assert result.status == "FAIL"
    assert len(result.conflicts) == 1


def test_altitude_range_fail_names_both_rules():
    rs = _rs({"max_altitude": _max("Ceiling Rule", 10), "min_altitude": _min("Floor Rule", 30)})
    conflict = verifier.verify(rs).conflicts[0]
    assert "Ceiling Rule" in conflict.names
    assert "Floor Rule" in conflict.names


def test_altitude_range_disabled_max_skips():
    rs = _rs({
        "max_altitude": _max("MaxAlt", 10, enabled=False),
        "min_altitude": _min("MinAlt", 30),
    })
    assert verifier.verify(rs).status == "PASS"


def test_altitude_range_disabled_min_skips():
    rs = _rs({
        "max_altitude": _max("MaxAlt", 10),
        "min_altitude": _min("MinAlt", 30, enabled=False),
    })
    assert verifier.verify(rs).status == "PASS"


def test_altitude_range_missing_fields_skips():
    rs = _rs({"max_altitude": {"rule_name": "MaxAlt", "enabled": True}})
    assert verifier.verify(rs).status == "PASS"


# ---------------------------------------------------------------------------
# Check 2: Emergency descent vs. absolute minimum
# ---------------------------------------------------------------------------

def test_emergency_overrides_false_skips():
    rs = _rs({
        "min_altitude": _min("AbsMin", 30, absolute=True),
        "emergency_descent": _emg("EmgDescent", 0, overrides=False),
    })
    assert verifier.verify(rs).status == "PASS"


def test_emergency_min_not_absolute_skips():
    rs = _rs({
        "min_altitude": _min("SoftMin", 30, absolute=False),
        "emergency_descent": _emg("EmgDescent", 0, overrides=True),
    })
    assert verifier.verify(rs).status == "PASS"


def test_emergency_conflict_detected():
    rs = _rs({
        "min_altitude": _min("AbsMin", 30, absolute=True),
        "emergency_descent": _emg("EmgDescent", 0, overrides=True),
    })
    result = verifier.verify(rs)
    assert result.status == "FAIL"


def test_emergency_conflict_names_rules():
    rs = _rs({
        "min_altitude": _min("Absolute Floor", 30, absolute=True),
        "emergency_descent": _emg("Emergency Override", 0, overrides=True),
    })
    conflict = verifier.verify(rs).conflicts[0]
    assert "Emergency Override" in conflict.names
    assert "Absolute Floor" in conflict.names


def test_emergency_target_at_min_boundary_passes():
    # descent_target == min_alt -> alt <= 30 AND alt >= 30 -> alt == 30 (SAT)
    rs = _rs({
        "min_altitude": _min("AbsMin", 30, absolute=True),
        "emergency_descent": _emg("EmgDescent", 30, overrides=True),
    })
    assert verifier.verify(rs).status == "PASS"


def test_emergency_target_above_min_passes():
    # descent_target > min_alt -> feasible range exists (SAT)
    rs = _rs({
        "min_altitude": _min("AbsMin", 30, absolute=True),
        "emergency_descent": _emg("EmgDescent", 50, overrides=True),
    })
    assert verifier.verify(rs).status == "PASS"


def test_emergency_disabled_skips():
    rs = _rs({
        "min_altitude": _min("AbsMin", 30, absolute=True),
        "emergency_descent": _emg("EmgDescent", 0, overrides=True, enabled=False),
    })
    assert verifier.verify(rs).status == "PASS"


# ---------------------------------------------------------------------------
# Check 3: Signal-loss dual-action
# ---------------------------------------------------------------------------

def test_signal_loss_both_disabled_passes():
    rs = _rs({
        "signal_loss_hold": _hold("Hold", enabled=False),
        "signal_loss_rth": _rth("RTH", enabled=False),
    })
    assert verifier.verify(rs).status == "PASS"


def test_signal_loss_only_hold_passes():
    rs = _rs({
        "signal_loss_hold": _hold("Hold", enabled=True),
        "signal_loss_rth": _rth("RTH", enabled=False),
    })
    assert verifier.verify(rs).status == "PASS"


def test_signal_loss_only_rth_passes():
    rs = _rs({
        "signal_loss_hold": _hold("Hold", enabled=False),
        "signal_loss_rth": _rth("RTH", enabled=True),
    })
    assert verifier.verify(rs).status == "PASS"


def test_signal_loss_both_enabled_fails():
    rs = _rs({
        "signal_loss_hold": _hold("Hold Policy", enabled=True),
        "signal_loss_rth": _rth("RTH Policy", enabled=True),
    })
    result = verifier.verify(rs)
    assert result.status == "FAIL"
    assert len(result.conflicts) == 1


def test_signal_loss_conflict_names_both_rules():
    rs = _rs({
        "signal_loss_hold": _hold("Hold Position Rule", enabled=True),
        "signal_loss_rth": _rth("Return to Home Rule", enabled=True),
    })
    conflict = verifier.verify(rs).conflicts[0]
    assert "Hold Position Rule" in conflict.names
    assert "Return to Home Rule" in conflict.names


# ---------------------------------------------------------------------------
# Structural / edge cases
# ---------------------------------------------------------------------------

def test_verify_empty_rules_passes():
    result = verifier.verify({"rule_set_id": "empty", "rules": {}})
    assert result.status == "PASS"
    assert result.conflicts == []


def test_verify_returns_verification_result():
    from fv_core import VerificationResult
    result = verifier.verify({"rules": {}})
    assert isinstance(result, VerificationResult)
