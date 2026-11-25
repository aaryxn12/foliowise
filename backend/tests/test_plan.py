import pytest

from planner.allocation import RiskLevel
from planner.plan import risk_profile
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
