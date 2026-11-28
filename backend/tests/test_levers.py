import pytest
from pydantic import ValidationError

from planner.inputs import with_changes
from planner.levers import (
    cheaper_big_goal,
    delay_big_goal,
    fits_budget,
    largest_that_fits,
    retire_later,
    shortfall_levers,
    spend_less_in_retirement,
)
from planner.plan import fund_picks
from tests.sample_forms import priya
from tests.test_plan import tiny_metrics

PICKS = fund_picks(tiny_metrics())  # levers depend on SIPs, not on which funds


# --- Changing the form safely -----------------------------------------------------


def test_with_changes_validates_the_copy():
    """model_copy would accept retiring at 25 when aged 30; with_changes refuses."""
    assert with_changes(priya(), retirement_age=55).retirement_age == 55
    with pytest.raises(ValidationError):
        with_changes(priya(), retirement_age=25)


def test_with_changes_leaves_the_original_alone():
    original = priya()
    with_changes(original, retirement_age=55)
    assert original.retirement_age == 50


# --- Binary search ------------------------------------------------------------------


@pytest.mark.parametrize(
    "limit, expected",
    [(37_400, 37_000), (50_000, 50_000), (1_000, 1_000), (999, None)],
)
def test_largest_that_fits(limit, expected):
    calls = []

    def fits(value):
        calls.append(value)
        return value <= limit

    assert largest_that_fits(1_000, 50_000, fits, 1_000) == expected
    assert len(calls) <= 7  # 50 possible steps, found in about log2(50) tries


# --- Each lever finds the smallest change that fits -----------------------------------


def test_priya_does_not_fit_her_budget_today():
    assert not fits_budget(priya(), PICKS)


def test_retire_later_finds_the_earliest_age_that_fits():
    lever = retire_later(priya(), PICKS)
    age = lever.plan_input.retirement_age
    assert lever.kind == "retire_later"
    assert age > 50
    assert fits_budget(lever.plan_input, PICKS)
    assert not fits_budget(with_changes(priya(), retirement_age=age - 1), PICKS)
    assert lever.monthly_sip <= 40_000
    assert lever.description == f"Retire at {age} instead of 50"


def test_spend_less_finds_the_highest_spending_that_fits():
    lever = spend_less_in_retirement(priya(), PICKS)
    spend = lever.plan_input.retirement_monthly_expense
    assert spend < 50_000 and spend % 1_000 == 0
    assert fits_budget(lever.plan_input, PICKS)
    assert not fits_budget(
        with_changes(priya(), retirement_monthly_expense=spend + 1_000), PICKS
    )


def test_delay_and_cheaper_goal_cannot_close_a_gap_this_big():
    """Retirement alone needs ~Rs62,000, more than the Rs40,000 budget, so no change
    to the house can make the plan fit."""
    assert delay_big_goal(priya(), PICKS) is None
    assert cheaper_big_goal(priya(), PICKS) is None


def test_house_levers_work_when_the_house_is_the_problem():
    """Retire on Rs20,000/month instead: retirement gets cheap, the house tips it over."""
    form = priya(retirement_monthly_expense=20_000, monthly_sip_budget=30_000)
    assert not fits_budget(form, PICKS)
    delayed = delay_big_goal(form, PICKS)
    cheaper = cheaper_big_goal(form, PICKS)
    assert delayed.plan_input.big_goal.years_away > 7
    assert cheaper.plan_input.big_goal.cost_today < 20_00_000
    assert fits_budget(delayed.plan_input, PICKS) and fits_budget(
        cheaper.plan_input, PICKS
    )


# --- All levers together ---------------------------------------------------------------


def test_an_affordable_plan_needs_no_levers():
    assert (
        shortfall_levers(priya(retirement_monthly_expense=10_000, big_goal=None), PICKS)
        == []
    )


def test_lumpsum_only_plans_get_no_levers():
    assert shortfall_levers(priya(mode="lumpsum", monthly_sip_budget=0), PICKS) == []


def test_priya_gets_the_retirement_levers():
    kinds = [lever.kind for lever in shortfall_levers(priya(), PICKS)]
    assert kinds == ["retire_later", "spend_less_in_retirement"]
