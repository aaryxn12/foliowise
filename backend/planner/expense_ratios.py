"""Expense ratios (TER) from AMFI's disclosure file, matched to our funds by name.

AMFI's TER file has no AMFI scheme code or ISIN, only the scheme name (without
the plan), so both sides are reduced to the same name key before matching:
    "Aditya Birla Sun Life Corporate Bond Fund - Direct Plan - GROWTH"
    "Aditya Birla Sun Life Corporate Bond Fund"
both become "aditya birla sun life corporate bond fund".
"""

import re

import pandas as pd

# Column headings in AMFI's TER file.
SCHEME_NAME = "Scheme Name"
TER_DATE = "TER Date"
DIRECT_TER = "Direct Plan - Total TER (%)"

# Where the plan part of a fund name starts, e.g. " - Direct Plan - Growth".
PLAN_SUFFIX = re.compile(r"\s*-\s*direct|\s+direct plan")


def scheme_name_key(name: str) -> str:
    """A fund name reduced to lowercase words, without the plan or option."""
    name = PLAN_SUFFIX.split(name.lower())[0]
    name = re.sub(r"[^a-z0-9]+", " ", name)  # punctuation becomes a space
    return name.strip()


def latest_direct_ter(ter: pd.DataFrame) -> dict[str, float]:
    """Latest direct-plan TER (in %) for each scheme, keyed by scheme_name_key.

    Rows without a scheme name are skipped. Raises ValueError if two different
    schemes reduce to the same key, since either could then be matched wrongly.
    """
    named = ter.dropna(subset=[SCHEME_NAME])  # skip rows with a blank scheme name
    latest = (
        named.sort_values(TER_DATE)  # oldest first, so the last row is the latest
        .groupby(SCHEME_NAME)[DIRECT_TER]  # for each scheme, look at its direct TER
        .last()  # one value per scheme: from its most recent date
    )

    result = {}
    for name, value in latest.items():
        key = scheme_name_key(name)
        if key in result:
            raise ValueError(f"Two TER schemes reduce to the same name: {key!r}")
        result[key] = float(value)
    return result
