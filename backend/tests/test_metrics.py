import math

import pandas as pd
import pytest

from planner.metrics import (
    RISK_FREE_RATE,
    annualised_volatility,
    cagr,
    category_median,
    consistency,
    max_drawdown,
    month_end_navs,
    nav_series_from_mfapi,
    rolling_returns,
    sharpe_ratio,
    trailing_years,
)


def monthly_series(values, start="2015-01-31"):
    """NAVs on consecutive month-ends, starting at `start`."""
    dates = pd.date_range(start=start, periods=len(values), freq="ME")
    return pd.Series(values, index=dates, dtype=float)


def steady_growth(monthly_rate, months, start_nav=100.0, start="2015-01-31"):
    """A fund that grows by exactly `monthly_rate` every month."""
    return monthly_series(
        [start_nav * (1 + monthly_rate) ** i for i in range(months + 1)], start=start
    )


# --- Turning mfapi's JSON into a price series --------------------------------


def test_nav_series_from_mfapi_parses_and_sorts_oldest_first():
    """mfapi lists newest first, with dates as text and NAVs as strings."""
    payload = {
        "meta": {"scheme_code": 122639},
        "data": [
            {"date": "21-11-2026", "nav": "89.3600"},
            {"date": "20-11-2026", "nav": "89.1000"},
            {"date": "19-11-2026", "nav": "88.9000"},
        ],
    }
    navs = nav_series_from_mfapi(payload)

    assert list(navs.index) == list(
        pd.to_datetime(["2026-11-19", "2026-11-20", "2026-11-21"])
    )
    assert list(navs) == [88.9, 89.1, 89.36]
    assert navs.dtype == float


def test_month_end_navs_keeps_the_last_nav_of_each_month():
    daily = pd.Series(
        [100.0, 101.0, 102.0, 103.0, 104.0],
        index=pd.to_datetime(
            ["2026-01-05", "2026-01-30", "2026-02-02", "2026-02-27", "2026-03-31"]
        ),
    )
    monthly = month_end_navs(daily)
    assert list(monthly) == [101.0, 103.0, 104.0]


# --- Max drawdown: the worst fall from a previous peak ------------------------


def test_max_drawdown_finds_the_worst_peak_to_trough_fall():
    """Peaks at 120 then 130; the fall from 130 to 65 (-50%) is the worst."""
    navs = monthly_series([100, 120, 90, 130, 65, 140])
    assert max_drawdown(navs) == pytest.approx(-0.50)


def test_max_drawdown_of_a_fund_that_only_rises_is_zero():
    assert max_drawdown(monthly_series([100, 101, 105, 110])) == 0


# --- CAGR: compound annual growth rate ---------------------------------------


def test_cagr_doubling_in_ten_years():
    """100 → 200 in exactly 10 years is about 7.18% a year."""
    navs = monthly_series([100.0] + [150.0] * 119 + [200.0])
    assert cagr(navs) == pytest.approx(2 ** (1 / 10) - 1, abs=1e-4)


def test_cagr_of_steady_monthly_growth():
    """1% every month for 5 years compounds to 12.68% a year."""
    assert cagr(steady_growth(0.01, months=60)) == pytest.approx(1.01**12 - 1, abs=1e-4)


# --- Volatility: how much monthly returns swing, scaled to a year -------------


def test_volatility_of_steady_growth_is_zero():
    assert annualised_volatility(steady_growth(0.01, months=24)) == pytest.approx(0)


def test_volatility_of_alternating_returns():
    """Monthly returns of +10%, -10%, +10%, -10%: sample std 0.1155, x sqrt(12)."""
    navs = monthly_series([100, 110, 99, 108.9, 98.01])
    expected = 0.1 * math.sqrt(4 / 3) * math.sqrt(12)  # = 0.4
    assert annualised_volatility(navs) == pytest.approx(expected, abs=1e-6)


# --- Sharpe ratio: extra return per unit of risk -----------------------------


def test_sharpe_ratio():
    """(12% return - 6.5% risk-free) / 20% volatility = 0.275."""
    assert sharpe_ratio(0.12, 0.20, risk_free=0.065) == pytest.approx(0.275)


def test_sharpe_ratio_uses_the_default_risk_free_rate():
    assert sharpe_ratio(0.12, 0.20) == pytest.approx((0.12 - RISK_FREE_RATE) / 0.20)


def test_sharpe_ratio_with_zero_volatility_is_undefined():
    """No risk taken: the ratio would divide by zero, so it is NaN, not an error."""
    assert math.isnan(sharpe_ratio(0.07, 0.0))


# --- Rolling returns: the CAGR of every 5-year window -------------------------


def test_rolling_returns_of_steady_growth():
    """7 years of month-ends = 85 points; 5-year windows end at months 60..84."""
    rolling = rolling_returns(steady_growth(0.01, months=84), years=5)
    assert len(rolling) == 25
    assert rolling.iloc[0] == pytest.approx(1.01**12 - 1)
    assert rolling.index[0] == pd.Timestamp("2020-01-31")  # first window ends here


def test_rolling_returns_empty_when_history_is_shorter_than_the_window():
    assert rolling_returns(steady_growth(0.01, months=36), years=5).empty


# --- Consistency: share of windows where the fund beat its category median ----


def test_consistency_counts_windows_where_the_fund_beat_the_median():
    dates = pd.date_range("2021-01-31", periods=4, freq="ME")
    fund = pd.Series([0.12, 0.10, 0.15, 0.09], index=dates)
    median = pd.Series([0.11, 0.11, 0.11, 0.11], index=dates)
    assert consistency(fund, median) == pytest.approx(0.50)  # beat in 2 of 4


def test_consistency_a_tie_does_not_count_as_beating():
    dates = pd.date_range("2021-01-31", periods=2, freq="ME")
    fund = pd.Series([0.11, 0.12], index=dates)
    median = pd.Series([0.11, 0.11], index=dates)
    assert consistency(fund, median) == pytest.approx(0.50)


def test_consistency_only_compares_windows_both_series_have():
    """The fund's history starts later: only the shared month-ends count."""
    fund = pd.Series(
        [0.20, 0.20], index=pd.date_range("2021-03-31", periods=2, freq="ME")
    )
    median = pd.Series(
        [0.30, 0.30, 0.10, 0.30],
        index=pd.date_range("2021-01-31", periods=4, freq="ME"),
    )
    assert consistency(fund, median) == pytest.approx(0.50)  # shared: Mar, Apr


# --- Trailing window: the same recent period for every fund -------------------


def test_trailing_years_keeps_the_last_n_years_inclusive():
    """10 years of month-ends; the last 5 years run Jan 2020 to Jan 2025 = 61 points."""
    navs = steady_growth(0.01, months=120)  # Jan 2015 .. Jan 2025
    recent = trailing_years(navs, 5)
    assert len(recent) == 61
    assert recent.index[0] == pd.Timestamp("2020-01-31")
    assert recent.index[-1] == navs.index[-1]


# --- Category median: the "typical fund" for each window -----------------------


def test_category_median_per_date():
    dates = pd.date_range("2021-01-31", periods=2, freq="ME")
    rolling = {
        code: pd.Series(values, index=dates)
        for code, values in {
            1: [0.10, 0.20],
            2: [0.12, 0.18],
            3: [0.14, 0.16],
        }.items()
    }
    median = category_median(rolling, min_funds=3)
    assert list(median) == pytest.approx([0.12, 0.18])
    assert list(median.index) == list(dates)


def test_category_median_drops_dates_with_too_few_funds():
    """Fund 3 starts a month later, so January has only 2 funds and is dropped."""
    jan_feb = pd.date_range("2021-01-31", periods=2, freq="ME")
    rolling = {
        1: pd.Series([0.10, 0.10], index=jan_feb),
        2: pd.Series([0.20, 0.20], index=jan_feb),
        3: pd.Series([0.30], index=[pd.Timestamp("2021-02-28")]),
    }
    median = category_median(rolling, min_funds=3)
    assert list(median.index) == [pd.Timestamp("2021-02-28")]
    assert median.iloc[0] == pytest.approx(0.20)
