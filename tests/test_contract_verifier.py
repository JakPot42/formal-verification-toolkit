"""
Tests for ContractVerifier (ported from z3_contract's test_encoder.py onto
the shared fv_core.Conflict.names field).

Two categories:
  - File-based: load the three example term sheets and assert expected outcomes
  - Unit: inline term sheet dicts exercising individual code paths
"""

import json
from pathlib import Path

from contract.verifier import ContractVerifier

EXAMPLES = Path(__file__).parent.parent / "contract" / "examples"


def _load(name: str) -> dict:
    with open(EXAMPLES / name, encoding="utf-8") as f:
        return json.load(f)


# --- File-based tests ---

def test_clean_sheet_passes():
    result = ContractVerifier().verify(_load("ts_01_clean.json"))
    assert result.status == "PASS"
    assert result.conflicts == []


def test_vesting_conflict_fails():
    result = ContractVerifier().verify(_load("ts_02_vesting_conflict.json"))
    assert result.status == "FAIL"
    assert len(result.conflicts) == 1


def test_vesting_conflict_names_both_clauses():
    result = ContractVerifier().verify(_load("ts_02_vesting_conflict.json"))
    names = result.conflicts[0].names
    assert any("Double-Trigger" in n or "double_trigger" in n.lower() for n in names)
    assert any("Board" in n or "board" in n.lower() for n in names)


def test_vesting_conflict_has_explanation():
    result = ContractVerifier().verify(_load("ts_02_vesting_conflict.json"))
    assert len(result.conflicts[0].explanation) > 20


def test_preference_conflict_fails():
    result = ContractVerifier().verify(_load("ts_03_preference_conflict.json"))
    assert result.status == "FAIL"
    assert len(result.conflicts) == 1


def test_preference_conflict_names_liquidation_clause():
    result = ContractVerifier().verify(_load("ts_03_preference_conflict.json"))
    names = result.conflicts[0].names
    assert any("Liquidation" in n or "liquidation" in n.lower() for n in names)


def test_preference_conflict_explanation_cites_dollar_amounts():
    result = ContractVerifier().verify(_load("ts_03_preference_conflict.json"))
    assert "$" in result.conflicts[0].explanation


def test_preference_conflict_no_vesting_conflict():
    # TS-003 board veto doesn't apply to double-trigger -- only one conflict total
    result = ContractVerifier().verify(_load("ts_03_preference_conflict.json"))
    assert len(result.conflicts) == 1


def test_clean_sheet_has_no_vesting_conflict():
    result = ContractVerifier().verify(_load("ts_01_clean.json"))
    assert not any("Double-Trigger" in c for conf in result.conflicts for c in conf.names)


def test_clean_sheet_liquidation_math_passes():
    # TS-001: 1x on $10M = $10M preferred, 30% of $15M = $4.5M common, total $14.5M <= $15M
    result = ContractVerifier().verify(_load("ts_01_clean.json"))
    assert result.status == "PASS"


# --- Unit tests (inline term sheets) ---

def _ts(clauses: dict) -> dict:
    return {"term_sheet_id": "unit", "description": "", "clauses": clauses}


def test_no_conflict_when_board_veto_not_for_double_trigger():
    ts = _ts({
        "double_trigger_acceleration": {
            "clause_name": "DTA", "enabled": True, "acceleration_is_automatic": True,
        },
        "board_veto": {
            "clause_name": "BV",
            "applies_to_all_acceleration": False,
            "applies_to_double_trigger": False,
        },
    })
    assert ContractVerifier().verify(ts).status == "PASS"


def test_conflict_when_board_veto_all_acceleration():
    ts = _ts({
        "double_trigger_acceleration": {
            "clause_name": "DTA", "enabled": True, "acceleration_is_automatic": True,
        },
        "board_veto": {
            "clause_name": "BV",
            "applies_to_all_acceleration": True,
            "applies_to_double_trigger": False,
        },
    })
    result = ContractVerifier().verify(ts)
    assert result.status == "FAIL"
    assert "DTA" in result.conflicts[0].names
    assert "BV" in result.conflicts[0].names


def test_conflict_when_board_veto_specifically_for_double_trigger():
    ts = _ts({
        "double_trigger_acceleration": {
            "clause_name": "DTA", "enabled": True, "acceleration_is_automatic": True,
        },
        "board_veto": {
            "clause_name": "BV",
            "applies_to_all_acceleration": False,
            "applies_to_double_trigger": True,
        },
    })
    result = ContractVerifier().verify(ts)
    assert result.status == "FAIL"


def test_no_conflict_when_dta_not_automatic():
    ts = _ts({
        "double_trigger_acceleration": {
            "clause_name": "DTA", "enabled": True, "acceleration_is_automatic": False,
        },
        "board_veto": {
            "clause_name": "BV",
            "applies_to_all_acceleration": True,
            "applies_to_double_trigger": True,
        },
    })
    assert ContractVerifier().verify(ts).status == "PASS"


def test_no_conflict_when_dta_disabled():
    ts = _ts({
        "double_trigger_acceleration": {
            "clause_name": "DTA", "enabled": False, "acceleration_is_automatic": True,
        },
        "board_veto": {
            "clause_name": "BV",
            "applies_to_all_acceleration": True,
            "applies_to_double_trigger": True,
        },
    })
    assert ContractVerifier().verify(ts).status == "PASS"


def test_liquidation_sat():
    # preferred_min = 1x5M = 5M, common_min = 20% of 10M = 2M, total 7M <= 10M
    ts = _ts({
        "liquidation_preference": {"clause_name": "LP", "investment_amount_usd": 5_000_000, "preference_multiple": 1},
        "common_minimum": {"clause_name": "CM", "minimum_pct": 20},
        "exit_terms": {"clause_name": "ET", "proceeds_usd": 10_000_000},
    })
    assert ContractVerifier().verify(ts).status == "PASS"


def test_liquidation_unsat():
    # preferred_min = 2x8M = 16M, common_min = 60% of 12M = 7.2M, total 23.2M > 12M
    ts = _ts({
        "liquidation_preference": {"clause_name": "LP", "investment_amount_usd": 8_000_000, "preference_multiple": 2},
        "common_minimum": {"clause_name": "CM", "minimum_pct": 60},
        "exit_terms": {"clause_name": "ET", "proceeds_usd": 12_000_000},
    })
    result = ContractVerifier().verify(ts)
    assert result.status == "FAIL"
    assert any("LP" in n for n in result.conflicts[0].names)


def test_liquidation_boundary_exactly_at_proceeds():
    # preferred_min = 1x6M = 6M, common_min = 40% of 10M = 4M, total exactly 10M = proceeds
    ts = _ts({
        "liquidation_preference": {"clause_name": "LP", "investment_amount_usd": 6_000_000, "preference_multiple": 1},
        "common_minimum": {"clause_name": "CM", "minimum_pct": 40},
        "exit_terms": {"clause_name": "ET", "proceeds_usd": 10_000_000},
    })
    # 6M + 4M = 10M exactly, SAT (p=6M, c=4M satisfies all constraints)
    assert ContractVerifier().verify(ts).status == "PASS"


def test_missing_clauses_no_error():
    assert ContractVerifier().verify({"term_sheet_id": "x", "description": "", "clauses": {}}).status == "PASS"


def test_partial_liquidation_clauses_skipped():
    # Only liquidation_preference present, no common_minimum or exit_terms -> skip check
    ts = _ts({"liquidation_preference": {"clause_name": "LP", "investment_amount_usd": 5_000_000, "preference_multiple": 2}})
    assert ContractVerifier().verify(ts).status == "PASS"
