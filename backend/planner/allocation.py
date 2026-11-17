"""Investment policy: risk level, asset allocation and expected return per goal."""

import math
from dataclasses import dataclass
from enum import IntEnum

# Equity share by years-to-goal band: (conservative, moderate, aggressive).
# Bands are checked from the longest down; the first one the goal reaches wins.

EQUITY_BY_BAND = {
    10: (0.50, 0.70, 0.85),
    5: (0.35, 0.50, 0.65),
    3: (0.15, 0.30, 0.40),
    0: (0.00, 0.05, 0.10),
}
GOLD_SHARE = 0.05
GOLD_MIN_YEARS = 3

class RiskLevel(IntEnum):
    """Ordered risk levels, so min() and < work."""
    CONSERVATIVE = 1
    MODERATE = 2
    AGGRESSIVE = 3


def risk_bucket(willingness: RiskLevel, ability: RiskLevel) -> RiskLevel:
    """Final risk level: the lower of willingness and ability (CFA IPS rule)."""
    return min(willingness, ability)


@dataclass(frozen=True)
class Allocation:
    """Share of a goal's money in each asset class. Weights add up to 1."""

    equity: float
    debt: float
    gold: float

    def __post_init__(self) -> None:
        weights = (self.equity, self.debt, self.gold)
        if any(weight < 0 for weight in weights):
            raise ValueError(f"Weights cannot be negative: {weights}")
        if not math.isclose(sum(weights), 1.0):
            raise ValueError(f"Weights must add up to 1, got {sum(weights):.4f}")


@dataclass(frozen=True)
class ReturnAssumptions:
    """Expected yearly return of each asset class."""

    equity: float
    debt: float
    gold: float


def expected_return(allocation: Allocation, assumptions: ReturnAssumptions) -> float:
    """Weighted average return for this mix, e.g. 85/10/5 at 12/7/8% → 11.3%."""
    return (allocation.equity * assumptions.equity) + (allocation.debt * assumptions.debt) + (allocation.gold * assumptions.gold)

# Ability thresholds: each one crossed is a warning sign.
MIN_EMERGENCY_MONTHS = 3
MAX_EMI_TO_INCOME = 0.40


def willingness_from_quiz(answers: list[int]) -> RiskLevel:
    """Risk the user is comfortable with, from 4 quiz answers scored 1-4."""
    if len(answers) != 4:
        raise ValueError(f"Expected 4 answers, got {len(answers)}")
    if any(not 1 <= answer <= 4 for answer in answers):
        raise ValueError(f"Each answer must be between 1 and 4, got {answers}")

    total = sum(answers)
    if total <= 8:
        return RiskLevel.CONSERVATIVE
    elif total <= 12:
        return RiskLevel.MODERATE
    else:
        return RiskLevel.AGGRESSIVE


def ability_level(
    *,
    emergency_months: float,
    dependents: int,
    spouse_earns: bool,
    emi_to_income: float,
) -> RiskLevel:
    """Risk the user can afford: start at AGGRESSIVE, step down per warning sign.

    Warning signs: emergency fund under 3 months of outgoings; 2+ dependents
    with no second income; EMIs above 40% of take-home pay. Time horizon is
    left out on purpose: goal_allocation applies it per goal.
    """
    warning_signs = 0
    if emergency_months < MIN_EMERGENCY_MONTHS:
        warning_signs += 1
    if dependents >= 2 and not spouse_earns:
        warning_signs += 1
    if emi_to_income > MAX_EMI_TO_INCOME:
        warning_signs += 1

    level = max(RiskLevel.CONSERVATIVE, RiskLevel.AGGRESSIVE - warning_signs)
    return RiskLevel(level)


def goal_allocation(bucket: RiskLevel, years_to_goal: int) -> Allocation:
    """Equity/debt/gold split for one goal from the policy table."""
    if years_to_goal <= 0:
        raise ValueError("Years to goal should be greater than 0")
    