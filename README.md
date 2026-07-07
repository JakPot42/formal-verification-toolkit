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

## Status

Step 0 (guarden_fv's standalone `unsat_core` fix) and Step 1 (this
shared-core library) complete: 14 tests passing, no domain logic ported
yet. Step 2 (port `z3_contract`'s and `guarden_fv`'s real check logic onto
`fv_core.py`, wire up the `fv contract`/`fv uav` CLI) and Step 3
(distribute `fv_core.py` to `lease_translator`) haven't started yet.
