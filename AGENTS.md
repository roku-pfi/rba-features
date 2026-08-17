# AGENTS.md — rba-features

Shared **feature library** for a risk-based authentication (RBA) thesis project. It is
the ONE implementation of every login-risk feature, imported by offline training
(`rba-ml-training`) and, later, the online decision service — this is what guarantees
**train/serve parity**, the top failure mode the project is designed to avoid. Portable
orientation for any AI coding tool. (Cursor users also get `../.cursor/rules/`.)

## Where we are / where things are stated

**Polyrepo**: `rba-features`, `rba-contracts`, `rba-ml-training`, `docs` are separate
git repos cloned side-by-side (org `github.com/roku-pfi`). The feature *schema*
(names/order/version) is frozen in `../rba-contracts`; this repo is the
implementation. Roadmap/status/decisions live in the **`docs`** repo (sibling
checkout `../docs`):

- **Current status & step checklist → `../docs/plans/status.md`** (single source of truth).
- Phase roadmap & rationale → `../docs/plans/development_plan.md` (§3–5 cover this lib).
- Narrative progress → `../docs/devlog.md` (newest on top).
- Decisions → `../docs/decisions/` (ADRs). Numbers → `../docs/findings/`.

## Layout

```
src/rba_features/
├── schema.py     # canonical column names for the Wiefling dataset / LoginEvent
├── profile.py    # ProfileState: the per-user history accumulator
├── features.py   # feature functions f(event, profile) -> value  (+ FEATURE_NAMES)
├── travel.py     # country-centroid impossible_travel + VPN skip (PDP rule)
└── replay.py     # offline replay driver (build past-only training vectors)
tests/test_parity.py   # offline vs online feature-vector equality — MUST stay green
```

## The parity contract (do not break)

- Every feature is a **pure function `f(current_event, profile_state) -> value`**. It
  reads ONLY its two args — never global/current-time state.
- `compute_features(event, profile)` runs FIRST; `update_profile(profile, event)` runs
  AFTER, so the current event never leaks into its own vector.
- Offline (replay) and online (materialised profile) paths MUST produce identical
  vectors. Any change here requires updating `tests/test_parity.py` and keeping it green.
- Missing values (`"-"`, NaN, empty) must NEVER count as "seen before" nor be added to a
  seen-set.
- Excluded on purpose (EDA-justified): `rtt_deviation` (~94% missing), GPS / city
  GeoIP as Freeman inputs. Country-centroid `impossible_travel` is a **PDP
  escalate** in `travel.py` (ADR-0022), not a Freeman feature. Don't silently
  re-add RTT or city GPS to FEATURE_NAMES.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest        # runs the parity suite
```

Only commit when explicitly asked; Conventional Commits; never commit secrets.
