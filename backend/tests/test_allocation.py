from itertools import pairwise

import pytest

from planner.allocation import (
    Allocation,
    ReturnAssumptions,
    RiskLevel,
    ability_level,
    expected_return,
    goal_allocation,
    risk_bucket,
    willingness_from_quiz,
)

# --- Risk bucket: the lower of willingness and ability (CFA IPS rule) --------


def test_risk_levels_are_ordered():
    assert RiskLevel.CONSERVATIVE < RiskLevel.MODERATE < RiskLevel.AGGRESSIVE


def test_risk_bucket_uses_ability_when_it_is_lower():
    """Keen to take risk, but can't afford to: ability wins."""
    bucket = risk_bucket(willingness=RiskLevel.AGGRESSIVE, ability=RiskLevel.MODERATE)
    assert bucket == RiskLevel.MODERATE


def test_risk_bucket_uses_willingness_when_it_is_lower():
    """Could afford risk, but doesn't want it: the plan respects that."""
    bucket = risk_bucket(willingness=RiskLevel.CONSERVATIVE, ability=RiskLevel.AGGRESSIVE)
    assert bucket == RiskLevel.CONSERVATIVE


def test_risk_bucket_when_both_agree():
    bucket = risk_bucket(willingness=RiskLevel.AGGRESSIVE, ability=RiskLevel.AGGRESSIVE)
    assert bucket == RiskLevel.AGGRESSIVE


# --- Allocation: weights must add up to 100% ---------------------------------


def test_allocation_accepts_weights_that_sum_to_one():
    allocation = Allocation(equity=0.85, debt=0.10, gold=0.05)
    assert allocation.equity == 0.85


def test_allocation_rejects_weights_that_do_not_sum_to_one():
    with pytest.raises(ValueError):
        Allocation(equity=0.80, debt=0.10, gold=0.05)  # only 95%


def test_allocation_rejects_negative_weights():
    with pytest.raises(ValueError):
        Allocation(equity=1.10, debt=-0.10, gold=0.0)


# --- Expected return: weighted average of asset-class returns ---------------

ASSUMPTIONS = ReturnAssumptions(equity=0.12, debt=0.07, gold=0.08)


def test_expected_return_for_aggressive_retirement_mix():
    """85% x 12% + 10% x 7% + 5% x 8% = 11.3%, not the 12% the mockup assumed."""
    allocation = Allocation(equity=0.85, debt=0.10, gold=0.05)
    assert expected_return(allocation, ASSUMPTIONS) == pytest.approx(0.113)


def test_expected_return_for_all_debt():
    allocation = Allocation(equity=0.0, debt=1.0, gold=0.0)
    assert expected_return(allocation, ASSUMPTIONS) == pytest.approx(0.07)


# --- Willingness: from the 4 behaviour questions in the risk quiz ------------
# Each answer is scored 1 (most cautious, e.g. "sell everything")
# to 4 (most risk-seeking, e.g. "invest more"). Total 4-16:
# 4-8 conservative, 9-12 moderate, 13-16 aggressive.


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        ([1, 1, 1, 1], RiskLevel.CONSERVATIVE),
        ([2, 2, 2, 2], RiskLevel.CONSERVATIVE),  # total 8: top of conservative
        ([3, 2, 2, 2], RiskLevel.MODERATE),  # total 9: bottom of moderate
        ([3, 3, 3, 3], RiskLevel.MODERATE),  # total 12: top of moderate
        ([4, 3, 3, 3], RiskLevel.AGGRESSIVE),  # total 13: bottom of aggressive
        ([4, 4, 4, 4], RiskLevel.AGGRESSIVE),
    ],
)
def test_willingness_from_quiz(answers, expected):
    assert willingness_from_quiz(answers) == expected


def test_willingness_rejects_wrong_number_of_answers():
    with pytest.raises(ValueError):
        willingness_from_quiz([4, 4, 4])


def test_willingness_rejects_answers_out_of_range():
    with pytest.raises(ValueError):
        willingness_from_quiz([4, 4, 4, 5])


# --- Ability: from the user's financial situation ----------------------------
# Start at AGGRESSIVE and step down one level for each warning sign:
#   - emergency fund covers less than 3 months of outgoings
#   - 2+ dependents and no earning spouse
#   - EMIs take more than 40% of take-home pay
# Never below CONSERVATIVE. Time horizon is NOT part of ability here:
# it is applied per goal in goal_allocation, so counting it twice would
# punish long goals for short ones.


def test_ability_with_no_warning_signs_is_aggressive():
    level = ability_level(
        emergency_months=8, dependents=0, spouse_earns=False, emi_to_income=0.10
    )
    assert level == RiskLevel.AGGRESSIVE


def test_ability_steps_down_for_dependents_without_second_income():
    """Priya: 2 dependents, no second income, 3 months of savings."""
    level = ability_level(
        emergency_months=3, dependents=2, spouse_earns=False, emi_to_income=0.10
    )
    assert level == RiskLevel.MODERATE


def test_ability_ignores_dependents_when_spouse_earns():
    level = ability_level(
        emergency_months=8, dependents=2, spouse_earns=True, emi_to_income=0.10
    )
    assert level == RiskLevel.AGGRESSIVE


def test_ability_steps_down_for_a_thin_emergency_fund():
    level = ability_level(
        emergency_months=2, dependents=0, spouse_earns=False, emi_to_income=0.10
    )
    assert level == RiskLevel.MODERATE


def test_ability_steps_down_for_heavy_emis():
    level = ability_level(
        emergency_months=8, dependents=0, spouse_earns=False, emi_to_income=0.45
    )
    assert level == RiskLevel.MODERATE


def test_ability_never_goes_below_conservative():
    """Three warning signs would be 3 steps down; it stops at the floor."""
    level = ability_level(
        emergency_months=1, dependents=3, spouse_earns=False, emi_to_income=0.50
    )
    assert level == RiskLevel.CONSERVATIVE


# --- Goal allocation: the policy table ---------------------------------------
# Equity share by years to goal (rows) and risk level (columns):
#   years >= 10 : 50% / 70% / 85%
#   5 to 9      : 35% / 50% / 65%
#   3 to 4      : 15% / 30% / 40%
#   under 3     :  0% /  5% / 10%
# Gold is 5% for goals 3+ years away, 0% for shorter ones. Debt is the rest.


def test_goal_allocation_priya_retirement():
    allocation = goal_allocation(RiskLevel.MODERATE, years_to_goal=20)
    assert allocation.equity == pytest.approx(0.70)
    assert allocation.debt == pytest.approx(0.25)
    assert allocation.gold == pytest.approx(0.05)


def test_goal_allocation_priya_house():
    allocation = goal_allocation(RiskLevel.MODERATE, years_to_goal=7)
    assert allocation.equity == pytest.approx(0.50)
    assert allocation.debt == pytest.approx(0.45)
    assert allocation.gold == pytest.approx(0.05)


def test_goal_allocation_short_goal_has_no_gold():
    allocation = goal_allocation(RiskLevel.CONSERVATIVE, years_to_goal=2)
    assert allocation.equity == pytest.approx(0.0)
    assert allocation.debt == pytest.approx(1.0)
    assert allocation.gold == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("years", "expected_equity"),
    [
        (10, 0.85),  # exactly 10 years is the long band
        (9, 0.65),
        (5, 0.65),  # exactly 5 years is the 5-9 band
        (4, 0.40),
        (3, 0.40),  # exactly 3 years is the 3-4 band
        (2, 0.10),
        (0, 0.10),  # goal is due now
    ],
)
def test_goal_allocation_band_edges(years, expected_equity):
    allocation = goal_allocation(RiskLevel.AGGRESSIVE, years_to_goal=years)
    assert allocation.equity == pytest.approx(expected_equity)


@pytest.mark.parametrize("bucket", list(RiskLevel))
def test_glide_path_never_adds_equity_as_the_goal_gets_closer(bucket):
    """As years to the goal fall, the equity share must never go up."""
    equities = [goal_allocation(bucket, years).equity for years in range(30, -1, -1)]
    assert all(later <= earlier for earlier, later in pairwise(equities))


def test_goal_allocation_rejects_negative_years():
    with pytest.raises(ValueError):
        goal_allocation(RiskLevel.MODERATE, years_to_goal=-1)
