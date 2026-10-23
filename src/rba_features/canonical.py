"""Browser and OS as families, the same on both sides of the model (ADR-0042).

The training data spells out versions ("Chrome Mobile 81.0.4044", "Mac OS X
10.14.6"); the hosted login sends a family ("Chrome", "macOS"); and live traffic
always brings versions the training data never saw. Comparing strings across
those three made every live browser and OS an unknown value, which Freeman reads
as "almost nobody uses this", so a familiar Chrome alone outweighed a new
country. Scoring families also ranks better offline (finding 2026-10-23).

Every function here is idempotent: a family maps to itself, so profiles written
before this change (which hold the hosted login's families) stay valid.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

_VERSION = re.compile(r"^\d")

# Version-stripped family → the family the hosted login reports.
_BROWSER = {
    "Chrome Mobile": "Chrome",
    "Chrome Mobile WebView": "Chrome",
    "Chrome Mobile iOS": "Chrome",
    "Chromium": "Chrome",
    "Mobile Safari": "Safari",
    "Mobile Safari UI/WKWebView": "Safari",
    "Firefox Mobile": "Firefox",
    "Firefox iOS": "Firefox",
    "Edge Mobile": "Edge",
    "Opera Mobile": "Opera",
    "Opera Mini": "Opera",
    "Android": "Android Browser",
}
_OS_LINUX = {"Ubuntu", "Fedora", "Debian"}


def _family(raw: Any) -> Any:
    """Leading words up to the first one that starts with a digit."""
    if not isinstance(raw, str):
        return raw
    words = []
    for word in raw.split():
        if _VERSION.match(word):
            break
        words.append(word)
    return " ".join(words) or raw


def browser_family(raw: Any) -> Any:
    family = _family(raw)
    return _BROWSER.get(family, family) if isinstance(family, str) else family


def os_family(raw: Any) -> Any:
    family = _family(raw)
    if not isinstance(family, str):
        return family
    if family.startswith("Mac OS X") or family == "macOS":
        return "macOS"
    if family in _OS_LINUX:
        return "Linux"
    return family


def canonical_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of `event` with browser and OS reduced to their families."""
    out = dict(event)
    if "browser" in out:
        out["browser"] = browser_family(out["browser"])
    if "os" in out:
        out["os"] = os_family(out["os"])
    return out
