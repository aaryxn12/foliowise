import pytest

from planner.allocation import RiskLevel
from planner.inputs import BigGoal
from planner.plan import big_goal_target, goal_mix, retirement_target, risk_profile
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
