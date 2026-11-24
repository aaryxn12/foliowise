import pandas as pd
import pytest

from planner.expense_ratios import (
    DIRECT_TER,
    SCHEME_NAME,
    TER_DATE,
    latest_direct_ter,
    scheme_name_key,
)


def ter_rows(rows):
    """A small TER table in AMFI's layout: (scheme name, date, direct TER)."""
    return pd.DataFrame(
        [
            {SCHEME_NAME: name, TER_DATE: pd.Timestamp(day), DIRECT_TER: ter}
            for name, day, ter in rows
        ]
    )


# --- Name keys: both files' naming styles must meet in the middle --------------


@pytest.mark.parametrize(
    "universe_name, ter_name",
    [
        (
            "Aditya Birla Sun Life Corporate Bond Fund - Direct Plan - GROWTH",
            "Aditya Birla Sun Life Corporate Bond Fund",
        ),
        (
            "ICICI Prudential Flexi Cap fund - Direct Plan - Growth Option",
            "ICICI Prudential Flexi Cap Fund",
        ),
        ("BANDHAN Small Cap Fund - Direct Plan - Growth", "Bandhan Small Cap Fund"),
        (
            "Edelweiss Flexi Cap Fund. - Direct Plan - Growth",
            "Edelweiss Flexi Cap Fund",
        ),
    ],
)
def test_scheme_name_key_matches_both_naming_styles(universe_name, ter_name):
    assert scheme_name_key(universe_name) == scheme_name_key(ter_name)


def test_scheme_name_key_keeps_words_that_tell_funds_apart():
    assert scheme_name_key("UTI Nifty 50 Index Fund") != scheme_name_key(
        "UTI Nifty Next 50 Index Fund"
    )


# --- Latest TER per scheme -----------------------------------------------------


def test_latest_direct_ter_uses_the_most_recent_date():
    """Rows arrive out of order; the 20 Nov value must win."""
    ter = ter_rows(
        [
            ("Kotak Gold Fund", "2026-11-20", 0.15),
            ("Kotak Gold Fund", "2026-11-01", 0.20),
            ("Axis Gold Fund", "2026-11-05", 0.31),
        ]
    )
    assert latest_direct_ter(ter) == pytest.approx(
        {"kotak gold fund": 0.15, "axis gold fund": 0.31}
    )


def test_latest_direct_ter_skips_rows_without_a_name():
    ter = ter_rows(
        [("Kotak Gold Fund", "2026-11-20", 0.15), (None, "2026-11-20", 9.99)]
    )
    assert latest_direct_ter(ter) == pytest.approx({"kotak gold fund": 0.15})


def test_latest_direct_ter_rejects_two_schemes_with_the_same_key():
    """'Axis Gold Fund' and 'AXIS GOLD FUND.' both become 'axis gold fund'."""
    ter = ter_rows(
        [
            ("Axis Gold Fund", "2026-11-20", 0.31),
            ("AXIS GOLD FUND.", "2026-11-20", 0.50),
        ]
    )
    with pytest.raises(ValueError):
        latest_direct_ter(ter)
