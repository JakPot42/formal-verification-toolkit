"""
CLI-level tests for both `fv contract` and `fv uav` subcommand groups.

guarden_fv's own test suite already had CLI-level coverage (CliRunner);
z3_contract had none. This closes that gap for contract now that both
verifiers share one CLI.
"""
import json
from pathlib import Path

from click.testing import CliRunner

from cli import fv

CONTRACT_EXAMPLES = Path(__file__).parent.parent / "contract" / "examples"
UAV_RULE_SETS = Path(__file__).parent.parent / "uav" / "rule_sets"

runner = CliRunner()


# ---------------------------------------------------------------------------
# fv contract
# ---------------------------------------------------------------------------

def test_cli_contract_verify_clean_exits_0():
    r = runner.invoke(fv, ["contract", "verify", str(CONTRACT_EXAMPLES / "ts_01_clean.json")])
    assert r.exit_code == 0
    assert "PASS" in r.output


def test_cli_contract_verify_conflict_exits_1():
    r = runner.invoke(fv, ["contract", "verify", str(CONTRACT_EXAMPLES / "ts_02_vesting_conflict.json")])
    assert r.exit_code == 1
    assert "FAIL" in r.output


def test_cli_contract_verify_json_out_pass():
    r = runner.invoke(fv, ["contract", "verify", str(CONTRACT_EXAMPLES / "ts_01_clean.json"), "--json-out"])
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert data["status"] == "PASS"
    assert data["conflicts"] == []


def test_cli_contract_verify_json_out_fail():
    r = runner.invoke(fv, ["contract", "verify", str(CONTRACT_EXAMPLES / "ts_03_preference_conflict.json"), "--json-out"])
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert data["status"] == "FAIL"
    assert len(data["conflicts"]) == 1


def test_cli_contract_verify_names_conflicting_clauses():
    r = runner.invoke(fv, ["contract", "verify", str(CONTRACT_EXAMPLES / "ts_02_vesting_conflict.json")])
    assert "Double-Trigger" in r.output or "double_trigger" in r.output.lower()
    assert "Board" in r.output or "board" in r.output.lower()


def test_cli_contract_demo_reports_all_three():
    # Unlike the uav rule sets, the contract examples' term_sheet_id doesn't
    # match their filename (TS-001/TS-002/TS-003, not ts_01_clean etc.) --
    # the demo output correctly reports by term_sheet_id.
    r = runner.invoke(fv, ["contract", "demo"])
    assert "TS-001" in r.output
    assert "TS-002" in r.output
    assert "TS-003" in r.output


def test_cli_contract_demo_shows_pass_and_fail():
    r = runner.invoke(fv, ["contract", "demo"])
    assert "PASS" in r.output
    assert "FAIL" in r.output


# ---------------------------------------------------------------------------
# fv uav
# ---------------------------------------------------------------------------

def test_cli_uav_verify_clean_exits_0():
    r = runner.invoke(fv, ["uav", "verify", str(UAV_RULE_SETS / "rs_01_clean.json")])
    assert r.exit_code == 0
    assert "PASS" in r.output


def test_cli_uav_verify_conflict_exits_1():
    r = runner.invoke(fv, ["uav", "verify", str(UAV_RULE_SETS / "rs_02_emergency_conflict.json")])
    assert r.exit_code == 1
    assert "FAIL" in r.output


def test_cli_uav_verify_json_out_pass():
    r = runner.invoke(fv, ["uav", "verify", str(UAV_RULE_SETS / "rs_01_clean.json"), "--json-out"])
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert data["status"] == "PASS"
    assert data["conflicts"] == []


def test_cli_uav_verify_json_out_fail():
    r = runner.invoke(fv, ["uav", "verify", str(UAV_RULE_SETS / "rs_02_emergency_conflict.json"), "--json-out"])
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert data["status"] == "FAIL"
    assert len(data["conflicts"]) == 1


def test_cli_uav_demo_reports_all_three():
    r = runner.invoke(fv, ["uav", "demo"])
    assert "rs_01_clean" in r.output
    assert "rs_02_emergency_conflict" in r.output
    assert "rs_03_signal_conflict" in r.output


def test_cli_uav_demo_shows_pass_and_fail():
    r = runner.invoke(fv, ["uav", "demo"])
    assert "PASS" in r.output
    assert "FAIL" in r.output


def test_cli_uav_verify_names_conflicting_rules():
    r = runner.invoke(fv, ["uav", "verify", str(UAV_RULE_SETS / "rs_03_signal_conflict.json")])
    assert "Hold" in r.output or "HOLD" in r.output
    assert "Home" in r.output or "RTH" in r.output


# ---------------------------------------------------------------------------
# Top-level group structure
# ---------------------------------------------------------------------------

def test_fv_help_lists_both_subgroups():
    r = runner.invoke(fv, ["--help"])
    assert r.exit_code == 0
    assert "contract" in r.output
    assert "uav" in r.output
