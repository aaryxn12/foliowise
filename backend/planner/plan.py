"""Build a complete plan from the user's form answers.

Each step is its own small function, so it can be tested and explained alone;
build_plan (coming next) calls them in order.
"""

from dataclasses import dataclass

from planner.allocation import (
    DEFAULT_RETURN_ASSUMPTIONS,
    Allocation,
    EmergencyFundStatus,
    InvestmentType,
    ReturnAssumptions,
    RiskLevel,
    ability_level,
    emergency_fund_check,
    expected_return,
    goal_allocation,
    grow_existing_investments,
    risk_bucket,
    willingness_from_quiz,
)
from planner.inputs import BigGoal, ExistingSavings, PlanInput
from planner.sip import future_cost, future_value_lumpsum, retirement_corpus

# Planning assumptions (not asked in the form; the dashboard can change them later).
INFLATION = 0.06  # yearly rise in prices
LIFE_EXPECTANCY = 85  # plan retirement income up to this age
POST_RETIREMENT_RETURN = 0.08  # a safer mix once retired


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
        return 0.0, for_retirement + grow_existing_investments(liquid, retirement.years_away)

    liquid_at_goal = grow_existing_investments(liquid, big_goal.years_away)
    for_big_goal = min(liquid_at_goal, big_goal.target_amount)
    extra = liquid_at_goal - for_big_goal  # 0 unless savings exceed the goal

    years_between = retirement.years_away - big_goal.years_away
    if years_between >= 0:  # big goal comes first: the extra can still grow into retirement
        for_retirement += future_value_lumpsum(extra, retirement_return, years_between)
    return for_big_goal, for_retirement


def split_lumpsum(lumpsum: float, big_goal_need_today: float) -> tuple[float, float]:
    """Share out a new lumpsum: the big goal first, the rest to retirement.

    `big_goal_need_today` is what the big goal still lacks, as a lumpsum today.
    Returns (to big goal, to retirement), both in today's rupees.
    """
    to_big_goal = min(lumpsum, big_goal_need_today)
    return to_big_goal, lumpsum - to_big_goal
