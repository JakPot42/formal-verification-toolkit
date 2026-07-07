"""Tests for fv_core.py -- no real Z3 domain logic here, just the scaffolding."""
from __future__ import annotations

from z3 import Int, Real

from fv_core import Conflict, TrackedSolver, VerificationResult, safe_name


# ---------------------------------------------------------------------------
# safe_name()
# ---------------------------------------------------------------------------

class TestSafeName:
    def test_alphanumeric_passthrough(self):
        assert safe_name("clause1") == "clause1"

    def test_strips_special_characters(self):
        # Each disallowed character is substituted individually, not collapsed --
        # the two spaces and two dashes around "--" each become their own underscore.
        assert safe_name("Late Fee -- percentage sub-clause") == "Late_Fee____percentage_sub_clause"

    def test_strips_leading_and_trailing_underscores(self):
        assert safe_name("--Board Veto--") == "Board_Veto"

    def test_empty_after_sanitization_falls_back_to_clause(self):
        assert safe_name("---") == "clause"

    def test_empty_string_falls_back_to_clause(self):
        assert safe_name("") == "clause"

    def test_preserves_digits_and_underscores(self):
        assert safe_name("rule_2_v3") == "rule_2_v3"


# ---------------------------------------------------------------------------
# Conflict / VerificationResult
# ---------------------------------------------------------------------------

class TestVerificationResult:
    def test_to_dict_pass(self):
        result = VerificationResult(status="PASS", conflicts=[])
        d = result.to_dict()
        assert d == {"status": "PASS", "conflicts": []}

    def test_to_dict_fail_with_conflicts(self):
        result = VerificationResult(
            status="FAIL",
            conflicts=[Conflict(names=["Rule A", "Rule B"], explanation="They conflict.")],
        )
        d = result.to_dict()
        assert d["status"] == "FAIL"
        assert d["conflicts"] == [{"names": ["Rule A", "Rule B"], "explanation": "They conflict."}]

    def test_conflicts_default_to_empty_list(self):
        assert VerificationResult(status="PASS").conflicts == []


# ---------------------------------------------------------------------------
# TrackedSolver
# ---------------------------------------------------------------------------

class TestTrackedSolver:
    def test_satisfiable_returns_none(self):
        s = TrackedSolver()
        alt = Int("altitude_m")
        s.track(alt <= 100, "Max Altitude")
        s.track(alt >= 10, "Min Altitude")
        assert s.check_conflict() is None

    def test_unsat_two_constraints_returns_both_names(self):
        s = TrackedSolver()
        alt = Int("altitude_m")
        s.track(alt <= 10, "Ceiling Rule")
        s.track(alt >= 30, "Floor Rule")
        names = s.check_conflict()
        assert names is not None
        assert set(names) == {"Ceiling Rule", "Floor Rule"}

    def test_unsat_excludes_unrelated_tracked_constraint(self):
        """
        The actual point of TrackedSolver: it must report only the names Z3's
        real unsat_core() says are necessary for the contradiction, not every
        constraint that happened to be tracked in the same solver -- the
        exact bug fixed standalone in guarden_fv's own rule_engine.py before
        this library existed.
        """
        s = TrackedSolver()
        x = Int("x")
        y = Int("y")
        s.track(x <= 10, "Low Rule")
        s.track(x >= 20, "High Rule")       # Low + High alone are already UNSAT
        s.track(y == 5, "Unrelated Rule")   # always satisfiable, irrelevant

        names = s.check_conflict()
        assert names is not None
        assert "Low Rule" in names
        assert "High Rule" in names
        assert "Unrelated Rule" not in names

    def test_uses_real_typed_constraints_not_just_ints(self):
        s = TrackedSolver()
        p = Real("preferred_payout")
        c = Real("common_payout")
        s.track(p >= 2_000_000, "Liquidation Preference")
        s.track(c >= 500_000, "Common Minimum")
        s.track(p + c <= 2_000_000, "Exit Terms")
        names = s.check_conflict()
        assert names is not None
        assert set(names) == {"Liquidation Preference", "Common Minimum", "Exit Terms"}

    def test_names_with_special_characters_resolve_correctly(self):
        """clause_name strings in real term sheets/leases contain spaces and
        punctuation -- safe_name() sanitizes for Z3, but check_conflict()
        must still report the original human-readable name back."""
        s = TrackedSolver()
        alt = Int("altitude_m")
        s.track(alt <= 10, "Late Fee -- percentage sub-clause")
        s.track(alt >= 30, "Late Fee -- cap sub-clause")
        names = s.check_conflict()
        assert names is not None
        assert "Late Fee -- percentage sub-clause" in names
        assert "Late Fee -- cap sub-clause" in names
