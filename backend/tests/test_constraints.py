"""Rules from the free-text box: excluded categories and a risk ceiling."""

import pytest
from pydantic import ValidationError

from planner.allocation import Allocation, EquitySplit, RiskLevel, equity_split
from planner.plan import (
    build_plan,
    cap_risk,
    fund_picks,
    risk_profile,
    without_equity_categories,
    without_gold,
)
from tests.sample_forms import priya
from tests.test_plan import tiny_metrics

PICKS = fund_picks(tiny_metrics())


def categories_in(goal) -> set[str]:
    return {item.category for item in goal.sip_funds}


# --- The rules are validated like any other answer -----------------------------------


def test_rules_default_to_none():
    form = priya()
    assert form.excluded_categories == [] and form.max_risk is None


@pytest.mark.parametrize("category", ["large_cap_index", "debt", "crypto"])
def test_core_or_unknown_categories_cannot_be_excluded(category):
    with pytest.raises(ValidationError):
        priya(excluded_categories=[category])


def test_risk_ceiling_must_be_a_lower_level():
    with pytest.raises(ValidationError):
        priya(max_risk="aggressive")  # a ceiling of "aggressive" would change nothing


# --- Risk ceiling ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "bucket, ceiling, expected",
    [
        (RiskLevel.MODERATE, None, RiskLevel.MODERATE),  # no ceiling
        (RiskLevel.AGGRESSIVE, "moderate", RiskLevel.MODERATE),  # lowered
        (RiskLevel.MODERATE, "conservative", RiskLevel.CONSERVATIVE),  # lowered
        (RiskLevel.CONSERVATIVE, "moderate", RiskLevel.CONSERVATIVE),  # already lower: kept
    ],
)
def test_cap_risk_never_raises_the_bucket(bucket, ceiling, expected):
    assert cap_risk(bucket, ceiling) == expected


def test_priya_asking_to_play_safe_becomes_conservative():
    assert risk_profile(priya(max_risk="conservative")).bucket == RiskLevel.CONSERVATIVE


# --- Excluding categories -----------------------------------------------------------------


def test_without_gold_moves_gold_to_debt():
    assert without_gold(Allocation(equity=0.70, debt=0.25, gold=0.05)) == Allocation(
        equity=0.70, debt=0.30, gold=0.0
    )


def test_excluded_equity_spreads_over_the_rest_in_proportion():
    """Moderate 40/30/20/10 without small caps: 40/30/20 scaled up to total 1."""
    split = without_equity_categories(equity_split(RiskLevel.MODERATE), ["small_cap"])
    assert (split.large_cap, split.flexi_cap, split.mid_cap, split.small_cap) == pytest.approx(
        (0.40 / 0.9, 0.30 / 0.9, 0.20 / 0.9, 0.0)
    )


def test_only_index_funds_puts_all_equity_in_large_cap():
    split = without_equity_categories(
        equity_split(RiskLevel.AGGRESSIVE), ["flexi_cap", "mid_cap", "small_cap"]
    )
    assert split == EquitySplit(large_cap=1.0, flexi_cap=0.0, mid_cap=0.0, small_cap=0.0)


def test_no_gold_and_no_small_caps_in_priyas_plan():
    plan = build_plan(priya(excluded_categories=["gold", "small_cap"]), PICKS)
    for goal in plan.goals:
        assert "gold" not in categories_in(goal) and "small_cap" not in categories_in(goal)
        assert goal.mix.allocation.gold == 0


def test_dropping_gold_lowers_the_expected_return_so_the_sip_rises():
    """Gold's assumed 8% becomes debt's 7%, so each goal needs a little more."""
    normal = build_plan(priya(), PICKS)
    no_gold = build_plan(priya(excluded_categories=["gold"]), PICKS)
    for before, after in zip(normal.goals, no_gold.goals):
        assert after.mix.expected_return < before.mix.expected_return
        assert after.funding.monthly_sip > before.funding.monthly_sip
