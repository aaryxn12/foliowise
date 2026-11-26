import pytest

from planner.allocation import RiskLevel
from planner.inputs import BigGoal, ExistingSavings
from planner.plan import (
    GoalTarget,
    big_goal_target,
    goal_mix,
    retirement_target,
    risk_profile,
    split_lumpsum,
    split_savings,
)
from tests.sample_forms import priya

# --- Piece 1: risk profile --------------------------------------------------------


def test_priya_wants_aggressive_but_can_afford_moderate():
    """Quiz 4+3+4+3 = 14 -> aggressive. Two dependents, no second income -> one
    warning sign -> moderate. The lower one wins."""
    profile = risk_profile(priya())
    assert profile.willingness == RiskLevel.AGGRESSIVE
    assert profile.ability == RiskLevel.MODERATE
    assert profile.bucket == RiskLevel.MODERATE


def test_emergency_fund_status_is_included():
    """3,00,000 covers 4.6 months of 65,000 outgoings; 6 months would be 3,90,000."""
    emergency = risk_profile(priya()).emergency_fund
    assert emergency.months_covered == pytest.approx(3_00_000 / 65_000)
    assert emergency.shortfall == pytest.approx(90_000)
    assert not emergency.is_adequate


def test_high_emis_lower_ability():
    """EMIs of 50,000 on 1,20,000 take-home is 42%, above the 40% limit: a second
    warning sign, so ability drops to conservative."""
    profile = risk_profile(priya(monthly_emis=50_000, monthly_sip_budget=10_000))
    assert profile.ability == RiskLevel.CONSERVATIVE
    assert profile.bucket == RiskLevel.CONSERVATIVE


def test_a_cautious_quiz_wins_even_with_strong_finances():
    """Single, no EMIs, big emergency fund (aggressive ability), but a cautious quiz."""
    profile = risk_profile(
        priya(dependents=0, monthly_emis=0, quiz_answers=[1, 2, 1, 2])
    )
    assert profile.ability == RiskLevel.AGGRESSIVE
    assert profile.willingness == RiskLevel.CONSERVATIVE
    assert profile.bucket == RiskLevel.CONSERVATIVE


# --- Piece 2: what each goal will cost --------------------------------------------


def test_house_cost_after_seven_years_of_inflation():
    """Rs20L today at 6% for 7 years = 20L x 1.06^7, about Rs30,07,260."""
    target = big_goal_target(BigGoal(kind="house", cost_today=20_00_000, years_away=7))
    assert target.name == "house"
    assert target.years_away == 7
    assert target.target_amount == pytest.approx(20_00_000 * 1.06**7)


def test_priya_needs_about_five_crore_at_fifty():
    """Rs50,000/month today -> Rs19,24,281 a year at 50; paid for 35 years
    (50 to 85) with 6% inflation and 8% return -> Rs4,98,93,481."""
    target = retirement_target(priya())
    assert target.name == "retirement"
    assert target.years_away == 20
    assert target.target_amount == pytest.approx(4_98_93_481, rel=1e-6)


def test_retiring_later_needs_a_bigger_yearly_amount_but_fewer_years():
    """Retiring at 55 instead of 50: 5 more years of inflation on each year's
    expense, but 5 fewer years to pay for. Here the inflation effect wins."""
    at_50 = retirement_target(priya()).target_amount
    at_55 = retirement_target(priya(retirement_age=55)).target_amount
    assert retirement_target(priya(retirement_age=55)).years_away == 25
    assert at_55 > at_50


# --- Piece 3a: how each goal is invested -------------------------------------------


def test_retirement_twenty_years_away_is_mostly_equity():
    """Moderate, 20 years: 70/25/5 -> 0.70 x 12% + 0.25 x 7% + 0.05 x 8% = 10.55%."""
    mix = goal_mix(RiskLevel.MODERATE, 20)
    assert (
        mix.allocation.equity,
        mix.allocation.debt,
        mix.allocation.gold,
    ) == pytest.approx((0.70, 0.25, 0.05))
    assert mix.expected_return == pytest.approx(0.1055)


def test_house_seven_years_away_is_safer():
    """Moderate, 7 years: 50/45/5 -> 9.55%."""
    mix = goal_mix(RiskLevel.MODERATE, 7)
    assert mix.allocation.equity == pytest.approx(0.50)
    assert mix.expected_return == pytest.approx(0.0955)


def test_goal_two_years_away_is_nearly_all_debt():
    """Moderate, under 3 years: 5% equity, no gold, 95% debt -> 7.25%."""
    mix = goal_mix(RiskLevel.MODERATE, 2)
    assert mix.allocation.gold == 0
    assert mix.expected_return == pytest.approx(0.0725)


# --- Piece 3b: savings and lumpsum to goals -------------------------------------------

HOUSE = GoalTarget(name="house", years_away=7, target_amount=30_00_000)
RETIREMENT = GoalTarget(name="retirement", years_away=20, target_amount=5_00_00_000)
PRIYA_SAVINGS = ExistingSavings(
    mutual_funds=2_00_000, fixed_deposits=1_00_000, ppf=1_50_000, epf=3_00_000
)


def test_priya_savings_split_by_type():
    """MF + FD grow for 7 years towards the house; EPF + PPF for 20 years towards
    retirement, each at its own rate."""
    for_house, for_retirement = split_savings(
        PRIYA_SAVINGS, big_goal=HOUSE, retirement=RETIREMENT, retirement_return=0.1055
    )
    assert for_house == pytest.approx(2_00_000 * 1.12**7 + 1_00_000 * 1.07**7)
    assert for_retirement == pytest.approx(3_00_000 * 1.0825**20 + 1_50_000 * 1.071**20)


def test_savings_beyond_the_big_goal_spill_into_retirement():
    """Rs50L of mutual funds grows past the Rs30L house; the extra keeps growing at
    retirement's 10.55% for the 13 years between the two goals."""
    rich = ExistingSavings(mutual_funds=50_00_000)
    for_house, for_retirement = split_savings(
        rich, big_goal=HOUSE, retirement=RETIREMENT, retirement_return=0.1055
    )
    extra_at_house = 50_00_000 * 1.12**7 - 30_00_000
    assert for_house == pytest.approx(30_00_000)
    assert for_retirement == pytest.approx(extra_at_house * 1.1055**13)


def test_with_no_big_goal_all_savings_go_to_retirement():
    for_house, for_retirement = split_savings(
        PRIYA_SAVINGS, big_goal=None, retirement=RETIREMENT, retirement_return=0.1055
    )
    assert for_house == 0
    assert for_retirement == pytest.approx(
        2_00_000 * 1.12**20 + 1_00_000 * 1.07**20 + 3_00_000 * 1.0825**20 + 1_50_000 * 1.071**20
    )


def test_extra_from_a_goal_after_retirement_is_not_counted_for_retirement():
    """A goal 25 years away arrives after retiring in 20: its extra can't help."""
    late_goal = GoalTarget(name="other", years_away=25, target_amount=1_00_000)
    _, for_retirement = split_savings(
        ExistingSavings(mutual_funds=5_00_000),
        big_goal=late_goal,
        retirement=RETIREMENT,
        retirement_return=0.1055,
    )
    assert for_retirement == 0


@pytest.mark.parametrize(
    "lumpsum, need, expected",
    [
        (2_00_000, 12_70_000, (2_00_000, 0)),  # Priya: all of it to the house
        (20_00_000, 12_70_000, (12_70_000, 7_30_000)),  # house filled, rest to retirement
        (5_00_000, 0, (0, 5_00_000)),  # house already covered
        (0, 12_70_000, (0, 0)),  # no lumpsum at all
    ],
)
def test_split_lumpsum_fills_the_big_goal_first(lumpsum, need, expected):
    assert split_lumpsum(lumpsum, need) == pytest.approx(expected)
