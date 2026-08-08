# rba-features

Shared **feature library** for the risk-based authentication system. It computes
login-risk features **identically** for offline training (`rba-ml-training`) and,
later, for online scoring (the decision service). A single implementation of every
feature is what guarantees **train/serve parity** — the top failure mode this
project is designed to avoid.

> Part of the RBA polyrepo. See `../docs/plans/status.md` for current status and
> `../docs/plans/development_plan.md` (sections 3–5) for the rationale. Orientation for
> AI tools: [`AGENTS.md`](AGENTS.md).

## Layout

```
src/rba_features/
├── schema.py     # canonical column names for the Wiefling dataset / LoginEvent
├── profile.py    # ProfileState: the per-user history accumulator
├── features.py   # the feature functions f(event, profile) -> value
└── replay.py     # offline replay driver (build past-only training vectors)
tests/
└── test_parity.py  # offline vs online feature-vector equality
```

## Core idea

Every feature is a pure function `f(current_event, profile_state) -> value`.

- **Offline:** replay a user's events in timestamp order, updating `ProfileState`
  as you go, calling the same `f`. This mechanically enforces "past-only"
  information and prevents leakage.
- **Online:** load the materialised `ProfileState` from Redis and call the same `f`.
- **Parity test:** N events through both paths must yield identical vectors.

## Install (editable, for local development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

`rba-ml-training` installs this package in editable mode from a sibling checkout
(`pip install -e ../rba-features`).

## Status

**Step 4 complete** — schema, `ProfileState`, the 10-feature `compute_features` /
`update_profile`, and the replay driver are implemented and covered by the parity
suite. See `../docs/plans/status.md` for overall project status.
