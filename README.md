# rba-features

Shared **feature library** for the risk-based authentication system. It is the
**one implementation** of every login-risk feature, imported by both offline
training (`rba-ml-training`) and online scoring (`rba-decision-service` /
`rba-profile-service`). A single implementation is what guarantees **train/serve
parity** — the top failure mode this project is designed to avoid.

Package version: **0.1.1**. Feature *schema* (names, types, order, version) is
frozen in sibling `rba-contracts` as `FEATURE_NAMES` / `FEATURE_SCHEMA_VERSION`
`1.0.0`. This repo implements the functions; contracts freeze the shape.

> Polyrepo: `github.com/roku-pfi`. Status: [`../docs/plans/status.md`](../docs/plans/status.md).
> AI orientation: [`AGENTS.md`](AGENTS.md).

## Layout

```
src/rba_features/
├── schema.py     # raw Wiefling CSV headers → canonical snake_case LoginEvent
├── profile.py    # ProfileState: per-user history + Freeman count buckets
├── features.py   # compute_features / update_profile + FEATURE_NAMES
└── replay.py     # offline driver: past-only vectors for one user's stream
tests/
└── test_parity.py  # offline replay vs online-style path — MUST stay green
```

## Core contract

Every feature is a pure function `f(current_event, profile_state) -> value`.

| Path | How history is obtained |
|---|---|
| **Offline** | Replay a user's events in timestamp order. For each event: compute, then update. |
| **Online** | Load materialised `ProfileState` from Redis, compute, then (async) update. |

Rules (do not break):

- `compute_features(event, profile)` reads **only** those two args — never
  wall-clock / global state.
- `update_profile(profile, event)` is called **after** compute, so the current
  event never leaks into its own vector.
- Offline and online paths **must** produce identical vectors. Any change here
  updates `tests/test_parity.py` and keeps it green.
- Missing values (`"-"`, NaN, empty, `"none"` / `"null"`) never count as
  “seen before” and are **not** added to a seen-set.

**Intentionally excluded** (EDA-justified — do not silently re-add):

- `rtt_deviation` — RTT is ~94% missing.
- Absolute geo distance / `impossible_travel` — geo is synthesised; region/city
  ~42% missing. Prefer `*_seen_before`.

## Feature set (`FEATURE_NAMES`)

| Feature | Type | Meaning |
|---|---|---|
| `user_login_count` | int | Prior logins already in the profile (0 on first login) |
| `ip_seen_before` | 0/1 | Current IP already in `seen_ips` |
| `asn_seen_before` | 0/1 | |
| `country_seen_before` | 0/1 | |
| `device_type_seen_before` | 0/1 | |
| `os_seen_before` | 0/1 | |
| `browser_seen_before` | 0/1 | |
| `hour_seen_before` | 0/1 | Local hour of `login_timestamp` already seen |
| `seconds_since_last_login` | float | Gap vs `last_login_ts`; **`-1.0`** if no prior login |
| `failed_logins_last_24h` | int | Failed attempts in the last 24h window |

Event fields the features read (canonical names from `schema.py`):
`login_timestamp`, `ip_address`, `asn`, `country`, `device_type`, `os`,
`browser`, `login_successful`.

The label `is_account_takeover` and leakage field `is_attack_ip` are **not**
feature inputs.

## `ProfileState`

Serializable accumulator of everything seen **before** the current attempt.
JSON snapshot via `profile_to_dict` / `profile_from_dict` (Redis payload).

- Seen-sets for the binary `*_seen_before` features.
- `failed_login_ts` (capped at 256) for the 24h burst count.
- `freeman_counts` / `freeman_totals` — per-value counts for online Freeman
  LLRs (`ip_address`, `asn`, `country`, `device_type`, `os`, `browser`, `hour`
  as a decimal string). Must stay aligned with `rba_contracts.FREEMAN_FEATURES`
  ([ADR-0009](../docs/decisions/0009-online-profile-freeman-serving.md)).

Redis key convention (owned by decision/profile services): `rba:profile:{user_id}`.

## Public API

```python
from rba_features.features import FEATURE_NAMES, compute_features, update_profile
from rba_features.profile import ProfileState, profile_from_dict, profile_to_dict
from rba_features.replay import replay_user

# Offline (one user, events already sorted by timestamp):
for vec in replay_user(events):
    ...

# Online:
profile = profile_from_dict(redis_json)
vec = compute_features(event, profile)   # score with this
update_profile(profile, event)           # persist after
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest        # parity suite
```

`rba-ml-training` installs this editable (`-e ../rba-features` in
`requirements.txt`). Decision-service and profile-service do the same.

Python ≥ 3.9 (runtime services use 3.12). Runtime dep: numpy. Dev: pytest, pandas.

## Status

Step 4 complete. Schema, `ProfileState`, the 10-feature compute/update path,
Freeman count buckets, replay driver, and parity tests are in production use
on the PDP path. Roadmap: `../docs/plans/status.md`.
