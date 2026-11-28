"""Build a complete plan from the user's form answers.

Each step is its own small function, so it can be tested and explained alone;
build_plan (coming next) calls them in order.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from planner.allocation import (
    DEFAULT_RETURN_ASSUMPTIONS,
    Allocation,
    CrashTestResult,
    EmergencyFundStatus,
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
from planner.inputs import BigGoal, ExistingSavings, PlanInput
from planner.rupee_split import split_amount
from planner.scoring import score_funds, shortlist
from planner.sip import (
    Affordability,
    GoalFunding,
    check_affordability,
    future_cost,
    future_value_lumpsum,
    lumpsum_needed,
    retirement_corpus,
    sip_needed,
)

# Planning assumptions (not asked in the form; the dashboard can change them later).
INFLATION = 0.06  # yearly rise in prices
LIFE_EXPECTANCY = 85  # plan retirement income up to this age
POST_RETIREMENT_RETURN = 0.08  # a safer mix once retired

METRICS_FILE = Path(__file__).resolve().parent.parent / "data" / "fund_metrics.csv"


@dataclass(frozen=True)
class RiskProfile:
    """How much risk the user wants, can afford, and will take."""

    willingness: RiskLevel  # from the quiz: how much risk they want
    ability: RiskLevel  # from their finances: how much risk they can afford
    bucket: RiskLevel  # the lower of the two; used for every goal
    emergency_fund: EmergencyFundStatus


def risk_profile(plan_input: PlanInput) -> RiskProfile:
    """Work out the user's risk bucket and emergency fund status."""

    emergency = emergency_fund_check(
        plan_input.emergency_fund, plan_input.monthly_expenses, plan_input.monthly_emis
    )
    willingness = willingness_from_quiz(plan_input.quiz_answers)
    ability = ability_level(
        emergency_months=emergency.months_covered,
        dependents=plan_input.dependents,
        spouse_earns=plan_input.spouse_earns,
        emi_to_income=plan_input.monthly_emis / plan_input.monthly_take_home,
    )
    bucket = risk_bucket(willingness, ability)
    return RiskProfile(
        willingness=willingness,
        ability=ability,
        bucket=bucket,
        emergency_fund=emergency,
    )


@dataclass(frozen=True)
class GoalTarget:
    """What a goal will cost on the day it arrives."""

    name: str  # "retirement", or the big goal's kind, e.g. "house"
    years_away: int
    target_amount: float  # rupees needed then, after inflation


def big_goal_target(goal: BigGoal) -> GoalTarget:
    """The big goal's cost after inflation, e.g. a Rs20L house in 7 years -> ~Rs30L."""
    name = goal.kind
    years_away = goal.years_away
    target_amount = future_cost(goal.cost_today, INFLATION, years_away)
    return GoalTarget(name=name, years_away=years_away, target_amount=target_amount)


def retirement_target(plan_input: PlanInput) -> GoalTarget:
    """Money needed on retirement day to pay expenses up to LIFE_EXPECTANCY."""
    years_to_retire = plan_input.retirement_age - plan_input.age
    first_year_expense = future_cost(
        12 * plan_input.retirement_monthly_expense, INFLATION, years_to_retire
    )
    corpus = retirement_corpus(
        first_year_expense=first_year_expense,
        years_in_retirement=LIFE_EXPECTANCY - plan_input.retirement_age,
        inflation=INFLATION,
        post_retirement_return=POST_RETIREMENT_RETURN,
    )
    return GoalTarget(
        name="retirement", years_away=years_to_retire, target_amount=corpus
    )


@dataclass(frozen=True)
class GoalMix:
    """How a goal's money is invested, and the yearly return that mix assumes."""

    allocation: Allocation  # equity / debt / gold shares
    expected_return: float  # e.g. 0.1055 for 10.55% a year


def goal_mix(
    bucket: RiskLevel,
    years_away: int,
    assumptions: ReturnAssumptions = DEFAULT_RETURN_ASSUMPTIONS,
) -> GoalMix:
    """The mix for a goal this far away, at this risk level, and its expected return."""
    allocation = goal_allocation(bucket, years_away)
    return GoalMix(
        allocation=allocation, expected_return=expected_return(allocation, assumptions)
    )


def split_savings(
    savings: ExistingSavings,
    *,
    big_goal: GoalTarget | None,
    retirement: GoalTarget,
    retirement_return: float,
) -> tuple[float, float]:
    """Existing savings each goal can count on, valued on that goal's own date.

    Returns (big goal's share, retirement's share). Savings stay where they are
    and grow at their own rates: EPF and PPF go to retirement (locked until
    then anyway); mutual funds and FDs go to the big goal. If they grow to more
    than the big goal costs, the extra keeps growing at retirement's expected
    return and joins retirement. With no big goal, everything goes to retirement.
    """
    locked = {InvestmentType.EPF: savings.epf, InvestmentType.PPF: savings.ppf}
    liquid = {
        InvestmentType.MUTUAL_FUNDS: savings.mutual_funds,
        InvestmentType.FD: savings.fixed_deposits,
    }
    for_retirement = grow_existing_investments(locked, retirement.years_away)

    if big_goal is None:
        return 0.0, for_retirement + grow_existing_investments(
            liquid, retirement.years_away
        )

    liquid_at_goal = grow_existing_investments(liquid, big_goal.years_away)
    for_big_goal = min(liquid_at_goal, big_goal.target_amount)
    extra = liquid_at_goal - for_big_goal  # 0 unless savings exceed the goal

    years_between = retirement.years_away - big_goal.years_away
    if (
        years_between >= 0
    ):  # big goal comes first: the extra can still grow into retirement
        for_retirement += future_value_lumpsum(extra, retirement_return, years_between)
    return for_big_goal, for_retirement


def split_lumpsum(lumpsum: float, big_goal_need_today: float) -> tuple[float, float]:
    """Share out a new lumpsum: the big goal first, the rest to retirement.

    `big_goal_need_today` is what the big goal still lacks, as a lumpsum today.
    Returns (to big goal, to retirement), both in today's rupees.
    """
    to_big_goal = min(lumpsum, big_goal_need_today)
    return to_big_goal, lumpsum - to_big_goal


def goal_funding(
    target: GoalTarget, mix: GoalMix, *, savings_at_goal: float, lumpsum_today: float
) -> GoalFunding:
    """Monthly SIP a goal still needs after its savings and lumpsum.

    `savings_at_goal` is valued on the goal date (from split_savings);
    `lumpsum_today` is new money invested in the goal's mix today.
    """
    still_needed = max(0.0, target.target_amount - savings_at_goal)
    return sip_needed(
        still_needed,
        mix.expected_return,
        target.years_away,
        existing_lumpsum=lumpsum_today,
    )


def plan_affordability(
    fundings: list[GoalFunding], monthly_budget: float
) -> Affordability:
    """The SIPs of all goals together, compared with what the user can invest monthly."""
    total_sip = sum(funding.monthly_sip for funding in fundings)
    return check_affordability(total_sip, monthly_budget)


def category_shares(allocation: Allocation, split: EquitySplit) -> dict[str, float]:
    """Share of a goal's money in each fund category; the shares add up to 1.

    The equity part is divided by the risk level's equity split, e.g. 70% equity
    with 40% of equity in large caps puts 28% of the goal in large caps.
    Keys match the categories in fund_metrics.csv.
    """
    return {
        "large_cap_index": allocation.equity * split.large_cap,
        "flexi_cap": allocation.equity * split.flexi_cap,
        "mid_cap": allocation.equity * split.mid_cap,
        "small_cap": allocation.equity * split.small_cap,
        "debt": allocation.debt,
        "gold": allocation.gold,
    }


@dataclass(frozen=True)
class FundPick:
    """A recommended fund and its score within its category."""

    scheme_code: int
    scheme_name: str
    category: str
    score: float  # 0-100, from scoring.score_funds


@dataclass(frozen=True)
class FundAmount:
    """Rupees going into one fund, plus the alternatives in its category."""

    category: str
    amount: int  # rupees, a multiple of rupee_split.STEP
    fund: FundPick
    alternatives: tuple[FundPick, ...]  # the next best funds in the same category

    def __post_init__(self) -> None:
        # A checkpointer stores tuples as lists; turn them back (see PlanHistory).
        object.__setattr__(self, "alternatives", tuple(self.alternatives))


def fund_picks(metrics: pd.DataFrame) -> dict[str, list[FundPick]]:
    """Each category's shortlisted funds, best first, from fund_metrics.csv data."""
    top = shortlist(score_funds(metrics))
    picks: dict[str, list[FundPick]] = {}
    for row in top.itertuples():  # already sorted by category, then rank
        pick = FundPick(
            int(row.scheme_code), row.scheme_name, row.category, float(row.score)
        )
        picks.setdefault(row.category, []).append(pick)
    return picks


def load_fund_picks(path: Path = METRICS_FILE) -> dict[str, list[FundPick]]:
    """fund_picks for the metrics file written by scripts/compute_metrics.py."""
    return fund_picks(pd.read_csv(path))


def fund_amounts(
    amount: float, shares: dict[str, float], picks: dict[str, list[FundPick]]
) -> list[FundAmount]:
    """Split an amount (a monthly SIP or a lumpsum) into rupees per fund."""
    if amount <= 0:
        return []
    return [
        FundAmount(
            category=category,
            amount=rupees,
            fund=picks[category][0],
            alternatives=tuple(picks[category][1:]),
        )
        for category, rupees in split_amount(amount, shares).items()
    ]


# --- Putting it together ----------------------------------------------------------


@dataclass(frozen=True)
class GoalPlan:
    """Everything the dashboard shows for one goal."""

    target: GoalTarget
    mix: GoalMix
    savings_at_goal: float  # existing savings counted for this goal, on its date
    lumpsum_today: float  # new lumpsum invested for this goal today
    funding: GoalFunding  # monthly SIP (or extra lumpsum) still needed
    sip_funds: tuple[FundAmount, ...]  # the monthly SIP, fund by fund
    lumpsum_funds: tuple[FundAmount, ...]  # the lumpsum, fund by fund
    crash: CrashTestResult  # a severe crash on this goal's first year of investing

    def __post_init__(self) -> None:
        # A checkpointer stores tuples as lists; turn them back (see PlanHistory).
        object.__setattr__(self, "sip_funds", tuple(self.sip_funds))
        object.__setattr__(self, "lumpsum_funds", tuple(self.lumpsum_funds))


@dataclass(frozen=True)
class Plan:
    """A complete plan: risk profile, each goal, and whether the SIPs fit the budget."""

    risk: RiskProfile
    goals: tuple[GoalPlan, ...]  # the big goal first (if any), then retirement
    affordability: Affordability | None  # None in lumpsum-only mode (no monthly budget)

    def __post_init__(self) -> None:
        # A checkpointer stores tuples as lists; turn them back (see PlanHistory).
        object.__setattr__(self, "goals", tuple(self.goals))


def lumpsum_for_plan(plan_input: PlanInput) -> float:
    """The lumpsum the plan may use: none in SIP-only mode, even if one was typed."""
    return 0.0 if plan_input.mode == "sip" else plan_input.lumpsum


def goal_plan(
    target: GoalTarget,
    mix: GoalMix,
    split: EquitySplit,
    *,
    savings_at_goal: float,
    lumpsum_today: float,
    invest_monthly: bool,
    picks: dict[str, list[FundPick]],
) -> GoalPlan:
    """One goal's funding, funds and crash test."""
    funding = goal_funding(
        target, mix, savings_at_goal=savings_at_goal, lumpsum_today=lumpsum_today
    )
    shares = category_shares(mix.allocation, split)
    monthly_sip = funding.monthly_sip if invest_monthly else 0.0
    return GoalPlan(
        target=target,
        mix=mix,
        savings_at_goal=savings_at_goal,
        lumpsum_today=lumpsum_today,
        funding=funding,
        sip_funds=tuple(fund_amounts(monthly_sip, shares, picks)),
        lumpsum_funds=tuple(fund_amounts(lumpsum_today, shares, picks)),
        crash=crash_test(lumpsum_today + 12 * monthly_sip, mix.allocation, split),
    )


def build_plan(
    plan_input: PlanInput, picks: dict[str, list[FundPick]] | None = None
) -> Plan:
    """The complete plan for a validated form.

    `picks` defaults to the funds in data/fund_metrics.csv; tests pass their own.
    """
    if picks is None:
        picks = load_fund_picks()
    invest_monthly = plan_input.mode != "lumpsum"

    # 1. How much risk, and how equity is divided across categories.
    risk = risk_profile(plan_input)
    split = equity_split(risk.bucket)

    # 2. What each goal costs, and how each is invested.
    retirement = retirement_target(plan_input)
    retirement_mix = goal_mix(risk.bucket, retirement.years_away)
    big_goal = big_goal_target(plan_input.big_goal) if plan_input.big_goal else None
    big_goal_mix = goal_mix(risk.bucket, big_goal.years_away) if big_goal else None

    # 3. Existing savings by type, then the lumpsum: the big goal first.
    savings_big, savings_retirement = split_savings(
        plan_input.savings,
        big_goal=big_goal,
        retirement=retirement,
        retirement_return=retirement_mix.expected_return,
    )
    lumpsum = lumpsum_for_plan(plan_input)
    if big_goal:
        big_goal_need_today = lumpsum_needed(
            max(0.0, big_goal.target_amount - savings_big),
            big_goal_mix.expected_return,
            big_goal.years_away,
        )
        lumpsum_big, lumpsum_retirement = split_lumpsum(lumpsum, big_goal_need_today)
    else:
        lumpsum_big, lumpsum_retirement = 0.0, lumpsum

    # 4. Each goal's SIP, funds and crash test.
    goals = []
    if big_goal:
        goals.append(
            goal_plan(
                big_goal,
                big_goal_mix,
                split,
                savings_at_goal=savings_big,
                lumpsum_today=lumpsum_big,
                invest_monthly=invest_monthly,
                picks=picks,
            )
        )
    goals.append(
        goal_plan(
            retirement,
            retirement_mix,
            split,
            savings_at_goal=savings_retirement,
            lumpsum_today=lumpsum_retirement,
            invest_monthly=invest_monthly,
            picks=picks,
        )
    )

    # 5. Do all the SIPs together fit the monthly budget?
    affordability = (
        plan_affordability(
            [goal.funding for goal in goals], plan_input.monthly_sip_budget
        )
        if invest_monthly
        else None
    )
    return Plan(risk=risk, goals=tuple(goals), affordability=affordability)
