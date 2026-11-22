"""Investment policy: risk level, asset allocation and expected return per goal."""

import math
from dataclasses import dataclass
from enum import Enum, IntEnum

from planner.sip import future_value_lumpsum


class RiskLevel(IntEnum):
    """Ordered risk levels, so min() and < work."""

    CONSERVATIVE = 1
    MODERATE = 2
    AGGRESSIVE = 3


# Equity share by years-to-goal band and risk level.
# Bands are checked from the longest down; the first one the goal reaches wins.
EQUITY_BY_BAND = {
    10: {
        RiskLevel.CONSERVATIVE: 0.50,
        RiskLevel.MODERATE: 0.70,
        RiskLevel.AGGRESSIVE: 0.85,
    },
    5: {
        RiskLevel.CONSERVATIVE: 0.35,
        RiskLevel.MODERATE: 0.50,
        RiskLevel.AGGRESSIVE: 0.65,
    },
    3: {
        RiskLevel.CONSERVATIVE: 0.15,
        RiskLevel.MODERATE: 0.30,
        RiskLevel.AGGRESSIVE: 0.40,
    },
    0: {
        RiskLevel.CONSERVATIVE: 0.00,
        RiskLevel.MODERATE: 0.05,
        RiskLevel.AGGRESSIVE: 0.10,
    },
}
GOLD_SHARE = 0.05
GOLD_MIN_YEARS = 3


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


# Starting values for the dashboard's return sliders.
DEFAULT_RETURN_ASSUMPTIONS = ReturnAssumptions(equity=0.12, debt=0.07, gold=0.08)


@dataclass(frozen=True)
class EquitySplit:
    """Share of a goal's EQUITY money in each fund category. Shares add up to 1."""

    large_cap: float
    flexi_cap: float
    mid_cap: float
    small_cap: float

    def __post_init__(self) -> None:
        weights = (self.large_cap, self.flexi_cap, self.mid_cap, self.small_cap)
        if any(weight < 0 for weight in weights):
            raise ValueError(f"Weights cannot be negative: {weights}")
        if not math.isclose(sum(weights), 1.0):
            raise ValueError(f"Weights must add up to 1, got {sum(weights):.4f}")


# How the equity part of a goal is divided across fund categories, by risk level.
EQUITY_SPLIT_BY_RISK = {
    RiskLevel.CONSERVATIVE: EquitySplit(
        large_cap=0.60, flexi_cap=0.30, mid_cap=0.10, small_cap=0.00
    ),
    RiskLevel.MODERATE: EquitySplit(
        large_cap=0.40, flexi_cap=0.30, mid_cap=0.20, small_cap=0.10
    ),
    RiskLevel.AGGRESSIVE: EquitySplit(
        large_cap=0.30, flexi_cap=0.25, mid_cap=0.25, small_cap=0.20
    ),
}


def equity_split(bucket: RiskLevel) -> EquitySplit:
    """How the equity part of a goal is divided across fund categories."""
    return EQUITY_SPLIT_BY_RISK[bucket]


def expected_return(allocation: Allocation, assumptions: ReturnAssumptions) -> float:
    """Weighted average return for this mix, e.g. 85/10/5 at 12/7/8% → 11.3%."""
    return (
        (allocation.equity * assumptions.equity)
        + (allocation.debt * assumptions.debt)
        + (allocation.gold * assumptions.gold)
    )


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
    """Equity/debt/gold split for one goal from the policy table.

    The band is the longest one the goal reaches, so as a goal gets closer it
    drops into lower-equity bands: that is the glide path.
    Moderate, 20 years → 70/25/5. Moderate, 7 years → 50/45/5.
    """
    if years_to_goal < 0:
        raise ValueError(f"years_to_goal cannot be negative, got {years_to_goal}")

    # Keys are 10, 5, 3, 0 (longest first); 0 always matches, so a band is found.
    for band in EQUITY_BY_BAND:
        if years_to_goal >= band:
            break

    equity = EQUITY_BY_BAND[band][bucket]
    gold = GOLD_SHARE if years_to_goal >= GOLD_MIN_YEARS else 0.0
    return Allocation(equity=equity, debt=1 - equity - gold, gold=gold)


class InvestmentType(Enum):
    """Kinds of existing savings the form asks about (unordered, so not IntEnum)."""

    MUTUAL_FUNDS = "mutual_funds"
    EPF = "epf"
    PPF = "ppf"
    FD = "fd"


# Yearly growth assumed for each kind of existing savings.
EXISTING_INVESTMENT_RETURNS = {
    InvestmentType.MUTUAL_FUNDS: 0.12,
    InvestmentType.EPF: 0.0825,
    InvestmentType.PPF: 0.071,
    InvestmentType.FD: 0.07,
}


def grow_existing_investments(
    holdings: dict[InvestmentType, float], years: int
) -> float:
    """Total value of existing savings after `years`, each type at its own rate.

    Growing EPF, PPF and FDs at the equity rate would overstate the savings and
    make the SIP the user needs look smaller than it really is.
    """
    if years < 0:
        raise ValueError(f"years cannot be negative, got {years}")

    return sum(
        future_value_lumpsum(amount, EXISTING_INVESTMENT_RETURNS[kind], years)
        for kind, amount in holdings.items()
    )
