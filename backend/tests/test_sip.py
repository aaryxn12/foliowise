import pytest

from planner.sip import (
    annual_to_monthly_rate,
    future_cost,
    future_value_lumpsum,
    lumpsum_needed,
    sip_needed,
)

HOUSE_GOAL = 30_07_261  # ₹20L today at 6% inflation for 7 years


def test_future_cost_house_goal():
    assert future_cost(20_00_000, 0.06, 7) == pytest.approx(HOUSE_GOAL, abs=1)


def test_annual_to_monthly_rate():
    assert annual_to_monthly_rate(0.12) == pytest.approx(0.009489, abs=1e-6)


def test_future_value_lumpsum():
    assert future_value_lumpsum(5_00_000, 0.10, 7) == pytest.approx(9_74_359, abs=1)


def test_lumpsum_needed():
    assert lumpsum_needed(HOUSE_GOAL, 0.10, 7) == pytest.approx(15_43_200, abs=1)


def test_sip_needed_house_goal():
    result = sip_needed(HOUSE_GOAL, 0.10, 7)
    assert result.monthly_sip == pytest.approx(25_077, abs=1)
    assert result.lumpsum_needed_today == pytest.approx(15_43_200, abs=1)
    assert result.surplus_today == 0


def test_sip_needed_with_existing_lumpsum():
    result = sip_needed(HOUSE_GOAL, 0.10, 7, existing_lumpsum=5_00_000)
    assert result.monthly_sip == pytest.approx(16_952, abs=1)
    assert result.lumpsum_needed_today == pytest.approx(10_43_200, abs=1)
    assert result.surplus_today == 0


def test_sip_needed_surplus_when_lumpsum_covers_goal():
    result = sip_needed(HOUSE_GOAL, 0.10, 7, existing_lumpsum=20_00_000)
    assert result.monthly_sip == 0
    assert result.lumpsum_needed_today == 0
    assert result.surplus_today == pytest.approx(4_56_800, abs=1)


def test_sip_actually_reaches_goal_month_by_month():
    """Independent check: simulate every month instead of using the formula."""
    result = sip_needed(HOUSE_GOAL, 0.10, 7, existing_lumpsum=5_00_000)
    monthly_rate = annual_to_monthly_rate(0.10)

    balance = 5_00_000.0
    for _ in range(7 * 12):
        balance += result.monthly_sip  # paid at the start of the month
        balance *= 1 + monthly_rate  # then grows for the month

    assert balance == pytest.approx(HOUSE_GOAL, abs=1)
