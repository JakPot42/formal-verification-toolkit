"""
Z3 contract term-sheet verifier -- ported from z3_contract's z3_encoder.py
onto the shared fv_core.TrackedSolver scaffolding.

Doctrine: Claude (or a human) fills in the JSON schema. This module encodes
the schema as Z3 SMT constraints and reports UNSAT cores as named
conflicting clause pairs -- the deterministic logic decides.
"""

from __future__ import annotations

from typing import Optional

from z3 import Int, Real

from fv_core import Conflict, TrackedSolver, VerificationResult


class ContractVerifier:
    """
    Encodes contract clause terms as Z3 constraints and checks for UNSAT.

    Each check corresponds to one clause pair or clause group. If Z3 returns
    UNSAT, the unsat core names the specific clauses in conflict.
    """

    def verify(self, term_sheet: dict) -> VerificationResult:
        clauses = term_sheet.get("clauses", {})
        conflicts: list[Conflict] = []

        result = self._check_vesting_board_conflict(clauses)
        if result:
            conflicts.append(result)

        result = self._check_liquidation_math(clauses)
        if result:
            conflicts.append(result)

        return VerificationResult(
            status="FAIL" if conflicts else "PASS",
            conflicts=conflicts,
        )

    # ------------------------------------------------------------------
    # Check 1: Double-trigger automatic acceleration vs. board veto
    #
    # Model: let n = number of preconditions before acceleration fires.
    #
    #   DTA clause says acceleration_is_automatic=True
    #   -> asserts n == 0  (fires without any further step)
    #
    #   Board veto clause says it applies to this acceleration
    #   -> asserts n > 0   (at least one approval step required)
    #
    # These two constraints are UNSAT.
    # ------------------------------------------------------------------

    def _check_vesting_board_conflict(self, clauses: dict) -> Optional[Conflict]:
        dta = clauses.get("double_trigger_acceleration") or {}
        bv = clauses.get("board_veto") or {}

        if not dta.get("enabled"):
            return None
        if not dta.get("acceleration_is_automatic"):
            return None
        if not (bv.get("applies_to_all_acceleration") or bv.get("applies_to_double_trigger")):
            return None

        dta_name = dta.get("clause_name", "double_trigger_acceleration")
        bv_name = bv.get("clause_name", "board_veto")

        s = TrackedSolver()
        n = Int("acceleration_preconditions")
        s.track(n == 0, dta_name)
        s.track(n > 0, bv_name)

        names = s.check_conflict()
        if names is not None:
            return Conflict(
                names=names,
                explanation=(
                    f'"{dta_name}" grants automatic acceleration -- no further preconditions. '
                    f'"{bv_name}" requires board approval before any acceleration takes effect. '
                    "An obligation that fires automatically cannot simultaneously require prior approval."
                ),
            )
        return None

    # ------------------------------------------------------------------
    # Check 2: Liquidation preference math
    #
    # Let p = preferred payout, c = common payout (both Reals).
    #
    #   LP clause  -> p >= investment * multiple
    #   CM clause  -> c >= proceeds * (minimum_pct / 100)
    #   Exit clause -> p + c <= proceeds
    #
    # If investment*multiple + proceeds*(pct/100) > proceeds, UNSAT.
    # ------------------------------------------------------------------

    def _check_liquidation_math(self, clauses: dict) -> Optional[Conflict]:
        lp = clauses.get("liquidation_preference") or {}
        cm = clauses.get("common_minimum") or {}
        et = clauses.get("exit_terms") or {}

        investment = lp.get("investment_amount_usd")
        multiple = lp.get("preference_multiple")
        common_min_pct = cm.get("minimum_pct")
        proceeds = et.get("proceeds_usd")

        if None in (investment, multiple, common_min_pct, proceeds):
            return None

        preferred_min = float(investment) * float(multiple)
        common_min = float(proceeds) * (float(common_min_pct) / 100.0)

        lp_name = lp.get("clause_name", "liquidation_preference")
        cm_name = cm.get("clause_name", "common_minimum")
        et_name = et.get("clause_name", "exit_terms")

        s = TrackedSolver()
        p = Real("preferred_payout")
        c = Real("common_payout")
        s.track(p >= preferred_min, lp_name)
        s.track(c >= common_min, cm_name)
        s.track(p + c <= proceeds, et_name)

        names = s.check_conflict()
        if names is not None:
            shortfall = preferred_min + common_min - proceeds
            return Conflict(
                names=names,
                explanation=(
                    f'"{lp_name}" requires preferred payout >= ${preferred_min:,.0f} '
                    f"({multiple}x on ${investment:,.0f}). "
                    f'"{cm_name}" requires common payout >= ${common_min:,.0f} '
                    f"({common_min_pct}% of ${proceeds:,.0f}). "
                    f"Combined floor ${preferred_min + common_min:,.0f} exceeds "
                    f"exit proceeds ${proceeds:,.0f} by ${shortfall:,.0f}."
                ),
            )
        return None
