"""Country-centroid impossible-travel rule (PDP escalate, not a Freeman input).

Pure ``f(event, profile)``. Same centroids offline and online (ADR-0022).
Missing country never fires. VPN/hosting ASNs skip the physics check.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from rba_features.country_centroids import COUNTRY_CENTROIDS
from rba_features.profile import ProfileState

# Implied speed above this (country centroid to centroid) is teleport.
SPEED_KMH_THRESHOLD = 1000.0
_EARTH_RADIUS_KM = 6371.0

# Thesis stand-in for commercial IP intel: well-known cloud / VPN / hosting ASNs.
# Compared as digit strings (optional "AS" prefix stripped).
VPN_HOSTING_ASNS: frozenset[str] = frozenset(
    {
        "13335",  # Cloudflare
        "16509",  # Amazon
        "14618",  # Amazon
        "15169",  # Google
        "8075",  # Microsoft
        "14061",  # DigitalOcean
        "16276",  # OVH
        "20473",  # Vultr / Choopa
        "63949",  # Linode / Akamai
        "24940",  # Hetzner
        "51167",  # Contabo
        "31898",  # Oracle
        "45102",  # Alibaba
        "132203",  # Tencent
        "21859",  # Zenlayer
        "9009",  # M247 (VPN)
        "60068",  # Datacamp / CDN77 (VPN)
        "212238",  # Datacamp
        "62240",  # Clouvider
        "209103",  # Proton
        "34927",  # Mullvad
        "136787",  # PacketHub (NordVPN)
        "40676",  # Psychz
        "36352",  # ColoCrossing
        "53667",  # PONYNET
    }
)


@dataclass(frozen=True)
class TravelSignals:
    """Rule outputs for the PDP. Not part of FEATURE_NAMES / Freeman."""

    impossible_travel: bool = False
    vpn_or_hosting: bool = False
    from_country: str | None = None
    to_country: str | None = None
    distance_km: float | None = None
    speed_kmh: float | None = None
    asn: str | None = None


def normalize_country(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip().upper()
    if not text or text in {"-", "NAN", "NONE", "NULL"}:
        return None
    return text


def normalize_asn(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip().upper()
    if not text or text in {"-", "NAN", "NONE", "NULL"}:
        return None
    if text.startswith("AS"):
        text = text[2:]
    text = text.strip()
    return text if text.isdigit() else None


def is_vpn_or_hosting(asn: Any) -> bool:
    key = normalize_asn(asn)
    return key is not None and key in VPN_HOSTING_ASNS


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def centroid_distance_km(from_country: str, to_country: str) -> float | None:
    a = COUNTRY_CENTROIDS.get(from_country)
    b = COUNTRY_CENTROIDS.get(to_country)
    if a is None or b is None:
        return None
    return haversine_km(a[0], a[1], b[0], b[1])


def compute_travel(event: Mapping[str, Any], profile: ProfileState) -> TravelSignals:
    """Physics check against the last *successful* residential login.

    Reads only ``event`` and ``profile``. VPN/hosting on the current ASN skips
    teleport and sets ``vpn_or_hosting``.
    """
    # Function-level import: features lazy-imports this module in update_profile.
    from rba_features.features import to_epoch

    to_country = normalize_country(event.get("country"))
    asn = normalize_asn(event.get("asn"))
    if is_vpn_or_hosting(asn):
        return TravelSignals(
            vpn_or_hosting=True,
            from_country=profile.last_login_country,
            to_country=to_country,
            asn=asn,
        )

    from_country = profile.last_login_country
    prev_ts = profile.last_success_login_ts
    now = to_epoch(event.get("login_timestamp"))
    if from_country is None or to_country is None or prev_ts is None or now is None:
        return TravelSignals(from_country=from_country, to_country=to_country, asn=asn)
    if from_country == to_country:
        return TravelSignals(
            from_country=from_country, to_country=to_country, asn=asn
        )

    distance = centroid_distance_km(from_country, to_country)
    if distance is None:
        return TravelSignals(
            from_country=from_country, to_country=to_country, asn=asn
        )

    hours = (now - prev_ts) / 3600.0
    if hours <= 0:
        speed = math.inf if distance > 0 else 0.0
    else:
        speed = distance / hours
    fired = distance > 0 and speed > SPEED_KMH_THRESHOLD
    return TravelSignals(
        impossible_travel=fired,
        from_country=from_country,
        to_country=to_country,
        distance_km=distance,
        speed_kmh=speed if math.isfinite(speed) else None,
        asn=asn,
    )
