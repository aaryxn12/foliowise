"""Investment policy: risk level, asset allocation and expected return per goal."""

import math
from dataclasses import dataclass
from enum import IntEnum


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