"""Offline event-replay driver.

Turns a chronologically ordered stream of a user's login events into training
rows by, for each event: (1) computing features against the current ProfileState,
then (2) folding the event into that state. This is the exact same feature code
the online service uses, which is what guarantees train/serve parity.

Implemented in Step 4.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator, Mapping

from rba_features.features import compute_features, update_profile
from rba_features.profile import ProfileState


def replay_user(events: Iterable[Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield one feature vector per event, in order, using past-only history.

    `events` MUST be sorted by login timestamp ascending for a single user.
    Implemented in Step 4.
    """
    profile = ProfileState()
    for event in events:
        features = compute_features(event, profile)
        profile = update_profile(profile, event)
        yield features
