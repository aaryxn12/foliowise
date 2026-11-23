from itertools import pairwise

import pytest

from planner.allocation import (
    DEFAULT_RETURN_ASSUMPTIONS,
    SEVERE_CRASH,
    Allocation,
    EquitySplit,
    InvestmentType,
    ReturnAssumptions,
    RiskLevel,
    ability_level,
    crash_test,
    emergency_fund_check,
    equity_split,
    expected_return,
    goal_allocation,
    grow_existing_investments,
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
    bucket = risk_bucket(
        willingness=RiskLevel.CONSERVATIVE, ability=RiskLevel.AGGRESSIVE
    )
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


# --- Equity split: how the equity share divides across fund categories -------
# Share of the EQUITY part (not of the whole goal), by risk level:
#                 large cap index  flexi  mid   small
#   conservative       60%          30%   10%    0%
#   moderate           40%          30%   20%   10%
#   aggressive         30%          25%   25%   20%


def test_equity_split_moderate():
    split = equity_split(RiskLevel.MODERATE)
    assert split.large_cap == pytest.approx(0.40)
    assert split.flexi_cap == pytest.approx(0.30)
    assert split.mid_cap == pytest.approx(0.20)
    assert split.small_cap == pytest.approx(0.10)


def test_equity_split_conservative_has_no_small_cap():
    assert equity_split(RiskLevel.CONSERVATIVE).small_cap == 0


def test_equity_split_aggressive_small_cap_is_capped_at_20_percent():
    assert equity_split(RiskLevel.AGGRESSIVE).small_cap == pytest.approx(0.20)


@pytest.mark.parametrize("bucket", list(RiskLevel))
def test_more_risk_never_means_less_small_cap(bucket):
    """Small cap share must rise (or stay) as the risk level rises."""
    if bucket == RiskLevel.AGGRESSIVE:
        return
    higher = RiskLevel(bucket + 1)
    assert equity_split(higher).small_cap >= equity_split(bucket).small_cap


def test_equity_split_rejects_shares_that_do_not_sum_to_one():
    with pytest.raises(ValueError):
        EquitySplit(large_cap=0.50, flexi_cap=0.50, mid_cap=0.50, small_cap=0.0)


def test_equity_split_rejects_negative_shares():
    with pytest.raises(ValueError):
        EquitySplit(large_cap=1.10, flexi_cap=0.0, mid_cap=0.0, small_cap=-0.10)


# --- Default return assumptions (the dashboard sliders start here) ------------


def test_default_return_assumptions():
    assert DEFAULT_RETURN_ASSUMPTIONS.equity == pytest.approx(0.12)
    assert DEFAULT_RETURN_ASSUMPTIONS.debt == pytest.approx(0.07)
    assert DEFAULT_RETURN_ASSUMPTIONS.gold == pytest.approx(0.08)


# --- Existing investments: each type grows at its own rate --------------------
# EPF 8.25%, PPF 7.1%, FD 7%, mutual funds 12% (treated as equity-heavy).


def test_epf_grows_at_its_own_rate():
    total = grow_existing_investments({InvestmentType.EPF: 1_00_000}, years=10)
    assert total == pytest.approx(1_00_000 * 1.0825**10)


def test_mixed_holdings_grow_separately_then_add_up():
    """₹16.7L split across four types: each grows at its own rate."""
    holdings = {
        InvestmentType.MUTUAL_FUNDS: 8_00_000,
        InvestmentType.EPF: 5_00_000,
        InvestmentType.PPF: 2_50_000,
        InvestmentType.FD: 1_20_000,
    }
    expected = (
        8_00_000 * 1.12**20
        + 5_00_000 * 1.0825**20
        + 2_50_000 * 1.071**20
        + 1_20_000 * 1.07**20
    )
    assert grow_existing_investments(holdings, years=20) == pytest.approx(expected)


def test_mixed_holdings_grow_less_than_if_all_were_equity():
    """The bug this prevents: growing EPF/PPF/FD at the equity rate overstates them."""
    holdings = {InvestmentType.PPF: 5_00_000, InvestmentType.FD: 5_00_000}
    assert grow_existing_investments(holdings, years=20) < 10_00_000 * 1.12**20


def test_no_existing_investments_grow_to_zero():
    assert grow_existing_investments({}, years=20) == 0


def test_existing_investments_reject_negative_years():
    with pytest.raises(ValueError):
        grow_existing_investments({InvestmentType.FD: 1_00_000}, years=-1)


# --- Emergency fund check -----------------------------------------------------
# Recommended: 6 months of outgoings (expenses + EMIs) set aside before investing.
# (Separate from ability_level's 3-month warning sign: 3 months lowers the risk
# level; 6 months is the target the dashboard recommends.)


def test_emergency_fund_short_of_six_months():
    """The design's example: ₹3.3L saved, ₹55k expenses + ₹12k EMIs a month."""
    status = emergency_fund_check(
        emergency_fund=3_30_000, monthly_expenses=55_000, monthly_emis=12_000
    )
    assert status.months_covered == pytest.approx(4.93, abs=0.01)
    assert status.target == 4_02_000  # 6 x ₹67,000
    assert status.shortfall == 72_000
    assert status.is_adequate is False


def test_emergency_fund_that_covers_six_months():
    status = emergency_fund_check(
        emergency_fund=5_00_000, monthly_expenses=55_000, monthly_emis=12_000
    )
    assert status.shortfall == 0
    assert status.is_adequate is True


def test_emergency_fund_exactly_six_months_is_adequate():
    status = emergency_fund_check(
        emergency_fund=6_00_000, monthly_expenses=1_00_000, monthly_emis=0
    )
    assert status.is_adequate is True


def test_emergency_fund_rejects_zero_outgoings():
    """No outgoings would mean dividing by zero; treat it as invalid input."""
    with pytest.raises(ValueError):
        emergency_fund_check(
            emergency_fund=1_00_000, monthly_expenses=0, monthly_emis=0
        )


# --- Crash test: what a 2008-style crash would do to the user's actual money --
# Illustrative one-year shocks: large cap -35%, flexi -38%, mid -45%,
# small -55%, debt +3%, gold +10%.


def test_crash_test_aggressive_long_goal():
    """85/10/5 with a 30/25/25/20 equity split: about -35%, ₹10L → ~₹6.49L."""
    result = crash_test(
        amount=10_00_000,
        allocation=Allocation(equity=0.85, debt=0.10, gold=0.05),
        split=equity_split(RiskLevel.AGGRESSIVE),
    )
    assert result.value_before == 10_00_000
    assert result.value_after == pytest.approx(6_48_875, abs=1)
    assert result.loss == pytest.approx(3_51_125, abs=1)
    assert result.loss_pct == pytest.approx(35.11, abs=0.01)


def test_crash_test_moderate_retirement():
    """Priya: 70/25/5 with a 40/30/20/10 split loses about 26.7%."""
    result = crash_test(
        amount=10_00_000,
        allocation=goal_allocation(RiskLevel.MODERATE, years_to_goal=20),
        split=equity_split(RiskLevel.MODERATE),
    )
    assert result.loss_pct == pytest.approx(26.68, abs=0.01)


def test_crash_test_all_debt_gains_slightly():
    result = crash_test(
        amount=10_00_000,
        allocation=Allocation(equity=0.0, debt=1.0, gold=0.0),
        split=equity_split(RiskLevel.CONSERVATIVE),
    )
    assert result.value_after == pytest.approx(10_30_000)
    assert result.loss == pytest.approx(-30_000)  # negative loss = a gain


def test_crash_hurts_aggressive_more_than_conservative():
    def loss_for(bucket):
        return crash_test(
            amount=10_00_000,
            allocation=goal_allocation(bucket, years_to_goal=20),
            split=equity_split(bucket),
        ).loss

    assert loss_for(RiskLevel.AGGRESSIVE) > loss_for(RiskLevel.MODERATE)
    assert loss_for(RiskLevel.MODERATE) > loss_for(RiskLevel.CONSERVATIVE)


def test_crash_test_with_no_money_loses_nothing():
    result = crash_test(
        amount=0,
        allocation=Allocation(equity=0.85, debt=0.10, gold=0.05),
        split=equity_split(RiskLevel.AGGRESSIVE),
    )
    assert result.loss == 0
    assert result.loss_pct == 0


def test_crash_test_rejects_negative_amount():
    with pytest.raises(ValueError):
        crash_test(
            amount=-1,
            allocation=Allocation(equity=0.85, debt=0.10, gold=0.05),
            split=equity_split(RiskLevel.AGGRESSIVE),
        )


def test_severe_crash_scenario_values():
    assert SEVERE_CRASH.small_cap == pytest.approx(-0.55)
    assert SEVERE_CRASH.gold == pytest.approx(0.10)
