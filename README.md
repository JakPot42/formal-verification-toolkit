# Formal Verification Toolkit (Phase 6, Cluster 4)

Merger of the "Claude extracts, Z3 decides" cluster: `z3-contract`,
`guarden-fv`, and `lease-translator`. Architecture-first session, same
discipline as Arbor, Analyst's Desk, and Cleared Facility Suite.

## The premise didn't hold as originally framed

All three source projects were assumed to be CLI tools. Checked directly
against the real code, not assumed:

- **`z3_contract`** and **`guarden_fv`** are genuinely CLI-only (Click,
  single-shot `verify <file>`, zero web layer, zero Claude integration
  despite their own docstrings aspirationally mentioning it).
- **`lease_translator`** is a live FastAPI web app (SQLAlchemy DB, Jinja2
  templates, its own Render deployment) with a real Claude
  extract-then-confirm-then-verify pipeline — the *only* one of the three
  that actually calls Claude.

So "merge" means two different things here, not one Arbor-style shape:

1. **`z3_contract` + `guarden_fv` merge into one CLI** with subcommands
   (`fv contract verify <file>`, `fv uav verify <file>`) — both are
   stateless, single-file, argument-in/result-out verifiers with no reason
   to stay separate processes.
2. **`lease_translator` stays fully standalone** (its own repo, its own
   Render deployment) — merging a stateful web app with a real Claude
   pipeline into a CLI would mean gutting its actual product. It receives
   the shared `fv_core.py` as a Step 3 consistency-pass distribution
   instead, same pattern as `facility_risk_indicator` in Cleared Facility
   Suite.

## What's genuinely shareable (and how it had already drifted, 3-for-3)

All three independently reimplemented the same scaffolding: a
`_safe_name()` helper, a `Conflict` dataclass, a `VerificationResult`
dataclass, and the `assert_and_track` → `check()` → map `unsat_core()`
back to names pattern. Every copy had drifted:

- `_safe_name()`: `z3_contract` and `lease_translator` stripped trailing
  underscores and fell back to `"clause"` on empty; `guarden_fv`'s was a
  bare regex substitution with neither.
- `VerificationResult.to_dict()`: present in `guarden_fv` and
  `lease_translator`, absent from `z3_contract` (its CLI built the JSON
  dict inline instead).
- **Real correctness gap, not just style drift**: `guarden_fv` never
  called `s.unsat_core()` at all — every one of its 3 checks tracked
  exactly 2 constraints and hardcoded both names as "the conflict"
  whenever `check()` returned `unsat`. This produced byte-identical output
  to the real answer for every check that existed (a 2-constraint UNSAT
  can't drop either side without becoming SAT again), but was never
  verified in code — only true by luck of the checks' shape. **Fixed
  standalone in `guarden_fv`'s own repo first** (own commit, own push, own
  regression test — see its commit history), proven with a constructed
  3-constraint case showing the hardcoded approach would have wrongly
  implicated an unrelated tracked constraint that the real `unsat_core()`
  correctly excludes.

## `fv_core.py`

The one canonical version of that scaffolding:

- **`safe_name(name)`** — the corrected version (strip + fallback).
- **`Conflict`** / **`VerificationResult`** — one shape, with `to_dict()`.
- **`TrackedSolver`** — wraps `Solver()` + `assert_and_track()` +
  `check()` + real `unsat_core()`-to-name resolution in one place, so every
  future check (in this repo or in `lease_translator`) gets the corrected
  behavior by construction instead of re-deriving it. Directly tested with
  the same 3-constraint regression case proven in `guarden_fv`'s own fix.

## The unified CLI

```
python cli.py contract verify <file> [--json-out]
python cli.py contract demo
python cli.py uav verify <file> [--json-out]
python cli.py uav demo
```

`z3_contract`'s and `guarden_fv`'s real domain-check logic (`contract/verifier.py`,
`uav/verifier.py`) ported unchanged onto `TrackedSolver` -- only the Z3
scaffolding changed, not the vesting/liquidation/altitude/emergency/
signal-loss logic itself. `z3_contract` had zero CLI-level test coverage
before this merge (only its engine was tested); `fv contract` now has the
same CLI test coverage `fv uav` already carried over from `guarden_fv`.

**Real, ASCII-safety bug found and fixed while verifying end-to-end, not
by inspection:** both projects' bundled example data use a legal/
regulatory-citation style clause naming convention (`"§4.3 Double-Trigger
Acceleration"`, `"§1 FAA Part 107 Altitude Ceiling"`) plus em-dashes in
descriptions and CLI output strings -- all of which render as `�` on a
real Windows cp1252 console, the same "ASCII-safe output" gotcha this
portfolio has hit before (citegraph, entity-graph, media_provenance).
Caught only by actually running `python cli.py contract verify` and
`uav verify` against every bundled example over a real terminal, not by
the test suite (which never asserts on exact byte content, only Python
string equality, so the mis-encoding was invisible to `pytest`). Fixed by
replacing the section sign with `"Sec. "` and em-dashes with `--` across
`cli.py`, `contract/verifier.py`, and all 6 bundled example/rule-set JSON
files.

## Status

Steps 0-2 complete: shared-core library, both verifiers' real domain
logic ported, and the unified `fv contract`/`fv uav` CLI wired up. 76
tests passing (14 `fv_core` + 20 `contract` + 26 `uav` + 16 CLI). Verified
end-to-end with real CLI invocations -- every bundled demo scenario run
directly as `python cli.py ...` (not just `CliRunner`), all matching
their documented expected PASS/FAIL outcomes, output clean on a real
Windows console.

Step 3 (distribute `fv_core.py` to `lease_translator`) hasn't started yet.
