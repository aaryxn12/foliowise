"""Ways to close a shortfall: what the user could change so the plan fits the budget.

Each lever re-runs build_plan on a changed copy of the form and finds the
smallest change that makes the total SIP fit the monthly budget.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from planner.formatting import format_rupees
from planner.inputs import MAX_GOAL_YEARS, MAX_RETIREMENT_AGE, PlanInput, with_changes
from planner.plan import FundPick, build_plan, load_fund_picks

MAX_GOAL_DELAY_YEARS = (
    10  # beyond this, "delay the goal" stops being a useful suggestion
)
RETIREMENT_SPEND_STEP = 1_000  # suggest monthly retirement spending in Rs1,000 steps
GOAL_COST_STEP = 10_000  # suggest big-goal costs in Rs10,000 steps


@dataclass(frozen=True)
class Lever:
    """One change that makes the plan affordable."""

    kind: str  # "retire_later", "spend_less_in_retirement", "delay_big_goal", "cheaper_big_goal"
    description: str  # e.g. "Retire at 56 instead of 50"
    plan_input: (
        PlanInput  # the changed form; build_plan(lever.plan_input) shows the new plan
    )
    monthly_sip: float  # total SIP needed after the change


def fits_budget(plan_input: PlanInput, picks: dict[str, list[FundPick]]) -> bool:
    """Whether every goal's SIP together fits the monthly budget."""
    return build_plan(plan_input, picks).affordability.is_affordable


def make_lever(
    kind: str, description: str, plan_input: PlanInput, picks: dict[str, list[FundPick]]
) -> Lever:
    """A Lever, with the total SIP of the changed plan filled in."""
    monthly_sip = build_plan(plan_input, picks).affordability.sip_needed
    return Lever(kind, description, plan_input, monthly_sip)


def largest_that_fits(
    low: float, high: float, fits: Callable[[float], bool], step: float
) -> float | None:
    """The largest multiple of `step` between `low` and `high` for which `fits` is True.

    Binary search: assumes `fits` is True for small values and turns False past
    some point (e.g. "does the plan fit if retirement costs this much?").
    Returns None if even `low` doesn't fit.
    """
    lowest, highest = math.ceil(low / step), math.floor(high / step)  # in whole steps
    if lowest > highest or not fits(lowest * step):
        return None
    while lowest < highest:  # fits(lowest * step) is always True here
        middle = (lowest + highest + 1) // 2
        if fits(middle * step):
            lowest = middle  # the answer is at least middle
        else:
            highest = middle - 1  # the answer is below middle
    return lowest * step


def retire_later(
    plan_input: PlanInput, picks: dict[str, list[FundPick]]
) -> Lever | None:
    """The earliest retirement age, after the current choice, at which the plan fits."""
    for age in range(plan_input.retirement_age + 1, MAX_RETIREMENT_AGE + 1):
        changed = with_changes(plan_input, retirement_age=age)
        if fits_budget(changed, picks):
            description = f"Retire at {age} instead of {plan_input.retirement_age}"
            return make_lever("retire_later", description, changed, picks)
    return None  # even retiring at MAX_RETIREMENT_AGE doesn't fit


def delay_big_goal(
    plan_input: PlanInput, picks: dict[str, list[FundPick]]
) -> Lever | None:
    """The fewest extra years of waiting for the big goal that make the plan fit."""
    goal = plan_input.big_goal
    if goal is None:
        return None
    last = min(goal.years_away + MAX_GOAL_DELAY_YEARS, MAX_GOAL_YEARS)
    for years in range(goal.years_away + 1, last + 1):
        changed = with_changes(
            plan_input, big_goal=goal.model_dump() | {"years_away": years}
        )
        if fits_budget(changed, picks):
            return make_lever(
                "delay_big_goal",
                f"Buy the {goal.kind} in {years} years instead of {goal.years_away}",
                changed,
                picks,
            )
    return None


def spend_less_in_retirement(
    plan_input: PlanInput, picks: dict[str, list[FundPick]]
) -> Lever | None:
    """The highest monthly retirement spending (in today's rupees) at which the plan fits."""
    current = plan_input.retirement_monthly_expense

    def fits(spend: float) -> bool:
        return fits_budget(
            with_changes(plan_input, retirement_monthly_expense=spend), picks
        )

    spend = largest_that_fits(
        RETIREMENT_SPEND_STEP, current, fits, RETIREMENT_SPEND_STEP
    )
    if spend is None or spend >= current:
        return None
    return make_lever(
        "spend_less_in_retirement",
        f"Plan to spend {format_rupees(spend)} a month in retirement instead of {format_rupees(current)}",
        with_changes(plan_input, retirement_monthly_expense=spend),
        picks,
    )


def cheaper_big_goal(
    plan_input: PlanInput, picks: dict[str, list[FundPick]]
) -> Lever | None:
    """The highest cost today for the big goal at which the plan fits."""
    goal = plan_input.big_goal
    if goal is None:
        return None

    def changed(cost: float) -> PlanInput:
        return with_changes(
            plan_input, big_goal=goal.model_dump() | {"cost_today": cost}
        )

    cost = largest_that_fits(
        GOAL_COST_STEP,
        goal.cost_today,
        lambda c: fits_budget(changed(c), picks),
        GOAL_COST_STEP,
    )
    if cost is None or cost >= goal.cost_today:
        return None
    return make_lever(
        "cheaper_big_goal",
        f"Aim for a {goal.kind} costing {format_rupees(cost)} today instead of {format_rupees(goal.cost_today)}",
        changed(cost),
        picks,
    )


def shortfall_levers(
    plan_input: PlanInput, picks: dict[str, list[FundPick]] | None = None
) -> list[Lever]:
    """Every lever that makes an unaffordable SIP plan fit; empty if it already fits.

    Lumpsum-only plans have no monthly budget, so they get no levers here.
    """
    if picks is None:
        picks = load_fund_picks()
    if plan_input.mode == "lumpsum" or fits_budget(plan_input, picks):
        return []
    candidates = [
        retire_later(plan_input, picks),
        spend_less_in_retirement(plan_input, picks),
        delay_big_goal(plan_input, picks),
        cheaper_big_goal(plan_input, picks),
    ]
    return [lever for lever in candidates if lever is not None]
