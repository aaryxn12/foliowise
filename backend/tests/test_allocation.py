import pytest

from planner.allocation import (
    Allocation,
    ReturnAssumptions,
    RiskLevel,
    expected_return,
    risk_bucket,
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
