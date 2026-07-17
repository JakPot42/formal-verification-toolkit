# Formal Verification Toolkit

**Formal Verification Toolkit is a command-line tool that uses a theorem prover to catch logical contradictions in rule sets — and names the exact rules that conflict.** It applies the Z3 SMT solver to two domains: contract term sheets and drone (UAV) geofencing rules. In both, the idea is the same — take a set of rules that are supposed to be internally consistent, and prove whether any combination of them contradicts.

## What it does

Two verifiers under one CLI:

- **`fv contract`** — encodes a contract term sheet's arithmetic and logical terms (vesting triggers, liquidation-preference math, board-veto thresholds) as constraints and reports whether they can all hold at once. If not, it names the specific conflicting clauses.
- **`fv uav`** — does the same for a set of UAV geofencing rules (altitude ceilings, emergency overrides, signal-loss behavior), catching cases like an emergency-descent rule that contradicts a hard altitude floor.

When the rules are contradictory, the tool doesn't just say "unsatisfiable" — it reports the minimal set of rules that clash, so you can see exactly what to fix.

## How it works

The doctrine is "Claude extracts, Z3 decides": where natural-language input is involved, an AI turns it into the structured rule schema, but the contradiction-finding itself is done entirely by the Z3 solver — deterministic and provable, never a judgment call. It verifies discrete logical rule sets only; it does not model physical flight dynamics or give real-world safety guarantees.

## Usage

```bash
pip install -r requirements.txt
python cli.py contract verify <file>     # check a contract term sheet
python cli.py contract demo
python cli.py uav verify <file>          # check a UAV geofencing rule set
python cli.py uav demo
```

Add `--json-out` for machine-readable output.

## About

Formal Verification Toolkit combines two independently-built verifiers — z3-contract and guarden-fv — into one CLI on shared solver scaffolding. A third, related tool, Lease Translator, applies the same technique to lease clauses and remains a standalone web app. This is part of a portfolio of national-security and defense-compliance software.
