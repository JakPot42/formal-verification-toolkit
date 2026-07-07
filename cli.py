"""
CLI entry point for the Formal Verification Toolkit.

Usage:
    python cli.py contract verify contract/examples/ts_01_clean.json
    python cli.py contract demo
    python cli.py uav verify uav/rule_sets/rs_01_clean.json
    python cli.py uav demo
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from contract.verifier import ContractVerifier
from uav.verifier import GuardenVerifier, load_rule_set

CONTRACT_EXAMPLES_DIR = Path(__file__).parent / "contract" / "examples"
UAV_RULE_SETS_DIR = Path(__file__).parent / "uav" / "rule_sets"

_CONTRACT_DEMO_FILES = [
    CONTRACT_EXAMPLES_DIR / "ts_01_clean.json",
    CONTRACT_EXAMPLES_DIR / "ts_02_vesting_conflict.json",
    CONTRACT_EXAMPLES_DIR / "ts_03_preference_conflict.json",
]

_UAV_DEMO_FILES = [
    UAV_RULE_SETS_DIR / "rs_01_clean.json",
    UAV_RULE_SETS_DIR / "rs_02_emergency_conflict.json",
    UAV_RULE_SETS_DIR / "rs_03_signal_conflict.json",
]


@click.group()
def fv() -> None:
    """Formal Verification Toolkit -- Z3-based logical contradiction checking.

    Two verifiers, one shared scaffolding (fv_core.py):
      fv contract  -- contract term sheets (vesting/board veto, liquidation math)
      fv uav       -- UAV geofencing rule sets (altitude, emergency descent, signal loss)
    """


def _print_verify_result(result, json_out: bool, item_id: str, description: str, label: str) -> None:
    if json_out:
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        sys.exit(0 if result.status == "PASS" else 1)

    click.echo("")
    click.echo(f"  {label}: {item_id}")
    if description:
        click.echo(f"  Description: {description}")
    click.echo("")

    if result.status == "PASS":
        click.secho("  PASS -- No logical contradictions found.", fg="green", bold=True)
    else:
        click.secho(
            f"  FAIL -- {len(result.conflicts)} contradiction(s) found.", fg="red", bold=True
        )
        for i, conflict in enumerate(result.conflicts, 1):
            click.echo(f"\n  Conflict {i}:")
            click.echo(f"    Names  : {' + '.join(conflict.names)}")
            click.echo(f"    Detail : {conflict.explanation}")

    click.echo("")
    sys.exit(0 if result.status == "PASS" else 1)


def _print_demo_results(files: list[Path], verify_fn, id_key: str) -> None:
    exit_code = 0
    for path in files:
        if not path.exists():
            click.secho(f"  SKIP  {path.name} not found", fg="yellow")
            continue

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        result = verify_fn(data)
        label = data.get(id_key, path.stem)

        if result.status == "PASS":
            click.secho(f"  PASS  {label}", fg="green")
        else:
            click.secho(f"  FAIL  {label}", fg="red")
            for conflict in result.conflicts:
                click.echo(f"        -> {' + '.join(conflict.names)}")
            exit_code = 1

    click.echo()
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# fv contract
# ---------------------------------------------------------------------------

@fv.group()
def contract() -> None:
    """Verify contract term sheets for logical contradictions."""


@contract.command("verify")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--json-out", is_flag=True, help="Emit result as JSON instead of human-readable text")
def contract_verify(file: Path, json_out: bool) -> None:
    """Verify a term sheet JSON FILE for logical contradictions using Z3."""
    with open(file, encoding="utf-8") as f:
        term_sheet = json.load(f)

    result = ContractVerifier().verify(term_sheet)
    _print_verify_result(
        result,
        json_out,
        term_sheet.get("term_sheet_id", file.stem),
        term_sheet.get("description", ""),
        "Term Sheet",
    )


@contract.command("demo")
def contract_demo() -> None:
    """Run all three demo term sheets and report results."""
    click.echo("\nFormal Verification Toolkit  |  Contract Demo -- 3 Term Sheets")
    click.echo("=" * 60)
    verifier = ContractVerifier()
    _print_demo_results(_CONTRACT_DEMO_FILES, verifier.verify, "term_sheet_id")


# ---------------------------------------------------------------------------
# fv uav
# ---------------------------------------------------------------------------

@fv.group()
def uav() -> None:
    """Verify UAV geofencing rule sets for logical contradictions."""


@uav.command("verify")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--json-out", is_flag=True, help="Emit result as JSON instead of human-readable text")
def uav_verify(file: Path, json_out: bool) -> None:
    """Verify a UAV rule set JSON FILE for logical conflicts."""
    rule_set = load_rule_set(file)
    result = GuardenVerifier().verify(rule_set)
    _print_verify_result(
        result,
        json_out,
        rule_set.get("rule_set_id", file.stem),
        rule_set.get("description", ""),
        "Rule Set",
    )


@uav.command("demo")
def uav_demo() -> None:
    """Run all three demo rule sets and report results."""
    click.echo("\nFormal Verification Toolkit  |  UAV Demo -- 3 Rule Sets")
    click.echo("=" * 60)
    verifier = GuardenVerifier()
    _print_demo_results(_UAV_DEMO_FILES, verifier.verify, "rule_set_id")


if __name__ == "__main__":
    fv()
