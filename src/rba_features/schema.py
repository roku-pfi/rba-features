"""Canonical schema for the Wiefling RBA dataset and the internal LoginEvent.

The raw dataset ships with verbose, space-containing column names. We map them
once, here, to stable snake_case identifiers so the rest of the codebase (and any
synthetic generator) never depends on the raw header strings.

Reference: "Login Data Set for Risk-Based Authentication" (Wiefling et al.),
Zenodo record 6782156 / Kaggle dasgroup/rba-dataset.
"""

from __future__ import annotations

# Raw CSV header -> internal field name.
RAW_TO_FIELD: dict[str, str] = {
    "index": "index",
    "Login Timestamp": "login_timestamp",
    "User ID": "user_id",
    "Round-Trip Time [ms]": "rtt_ms",
    "IP Address": "ip_address",
    "Country": "country",
    "Region": "region",
    "City": "city",
    "ASN": "asn",
    "User Agent String": "user_agent",
    "Browser Name and Version": "browser",
    "OS Name and Version": "os",
    "Device Type": "device_type",
    "Login Successful": "login_successful",
    "Is Attack IP": "is_attack_ip",
    "Is Account Takeover": "is_account_takeover",
}

FIELDS: list[str] = list(RAW_TO_FIELD.values())

# The prediction target.
LABEL: str = "is_account_takeover"

# Leakage-sensitive field: present in the raw data but excluded from the honest
# ("Variant B") model. See plans/development_plan.md section 6.
LEAKAGE_SENSITIVE_FIELDS: tuple[str, ...] = ("is_attack_ip",)

# Marks each row as coming from the real dataset or the synthetic generator so
# metrics can be reported per source (see plans section 7.3).
SOURCE_FIELD: str = "data_source"
SOURCE_REAL: str = "real"
SOURCE_SYNTHETIC: str = "synthetic"
