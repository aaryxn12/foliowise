import pytest

from planner.sip import (
    annual_to_monthly_rate,
    check_affordability,
    future_cost,
    future_value_lumpsum,
    lumpsum_needed,
    retirement_corpus,
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


# --- Retirement corpus -------------------------------------------------------

# ₹50k/month today, retiring in 20 years at 6% inflation.
FIRST_YEAR_EXPENSE = future_cost(6_00_000, 0.06, 20)  # ~₹19,24,281 a year at 50


def test_retirement_corpus():
    result = retirement_corpus(
        first_year_expense=FIRST_YEAR_EXPENSE,
        years_in_retirement=35,
        inflation=0.06,
        post_retirement_return=0.08,
    )
    assert result == pytest.approx(4_98_93_481, abs=1)


def test_retirement_corpus_when_return_equals_inflation():
    """Growth and discounting cancel out, so every year costs the same in
    retirement-day money: the corpus is simply years x first-year expense."""
    result = retirement_corpus(
        first_year_expense=FIRST_YEAR_EXPENSE,
        years_in_retirement=35,
        inflation=0.06,
        post_retirement_return=0.06,
    )
    assert result == pytest.approx(35 * FIRST_YEAR_EXPENSE, abs=1)


def test_retirement_corpus_matches_closed_form():
    """Independent check against the growing-annuity-due formula."""
    r, g, n = 0.08, 0.06, 35
    closed_form = (
        FIRST_YEAR_EXPENSE * (1 - ((1 + g) / (1 + r)) ** n) / (r - g) * (1 + r)
    )

    result = retirement_corpus(FIRST_YEAR_EXPENSE, n, g, r)
    assert result == pytest.approx(closed_form, rel=1e-9)


def test_retirement_corpus_when_return_below_inflation():
    """Negative real return is allowed; it just needs more than years x expense."""
    result = retirement_corpus(
        FIRST_YEAR_EXPENSE, 35, inflation=0.06, post_retirement_return=0.04
    )
    assert result > 35 * FIRST_YEAR_EXPENSE


def test_retirement_corpus_rejects_negative_years():
    with pytest.raises(ValueError):
        retirement_corpus(FIRST_YEAR_EXPENSE, -1, 0.06, 0.08)


# --- Affordability -----------------------------------------------------------


def test_check_affordability_shortfall():
    result = check_affordability(sip_needed=78_500, sip_affordable=50_000)
    assert result.is_affordable is False
    assert result.shortfall == 28_500
    assert result.surplus == 0
    assert result.coverage_pct == pytest.approx(63.69, abs=0.01)


def test_check_affordability_with_room_to_spare():
    result = check_affordability(sip_needed=45_000, sip_affordable=50_000)
    assert result.is_affordable is True
    assert result.shortfall == 0
    assert result.surplus == 5_000
    assert result.coverage_pct == 100


def test_check_affordability_when_nothing_is_needed():
    """A lumpsum already covers the goals: no division by zero, fully covered."""
    result = check_affordability(sip_needed=0, sip_affordable=50_000)
    assert result.is_affordable is True
    assert result.coverage_pct == 100
