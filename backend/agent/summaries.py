"""Planner results as short, display-ready data for the LLM to read.

Every number is formatted here, in Python, so the LLM only copies it: models
misread long numbers (e.g. 49893481 as "4.9 lakh" instead of "4.99 crore").
"""

import re

from planner.allocation import Allocation
from planner.formatting import format_percent, format_rupees
from planner.history import PlanChange
from planner.levers import Lever
from planner.plan import GoalPlan, Plan

PLAN_SUFFIX = re.compile(
    r"\s*-\s*direct.*$", re.IGNORECASE
)  # " - Direct Plan - Growth"


def short_fund_name(scheme_name: str) -> str:
    """A fund name without the plan and option, e.g. "Parag Parikh Flexi Cap Fund"."""
    return PLAN_SUFFIX.sub("", scheme_name)


def mix_summary(allocation: Allocation) -> str:
    """e.g. "70% equity / 25% debt / 5% gold"."""
    return f"{allocation.equity:.0%} equity / {allocation.debt:.0%} debt / {allocation.gold:.0%} gold"


def goal_summary(goal: GoalPlan, *, monthly: bool) -> dict:
    """One goal: what it costs, how it is invested, and what it still needs.

    `monthly` is False in lumpsum-only mode, where the goal shows the extra
    lumpsum it needs instead of a monthly SIP.
    """
    summary = {
        "goal": goal.target.name,
        "years_away": goal.target.years_away,
        "cost_then": format_rupees(goal.target.target_amount),
        "mix": mix_summary(goal.mix.allocation),
        "expected_return": format_percent(goal.mix.expected_return),
        "savings_counted": format_rupees(goal.savings_at_goal),
        "lumpsum_today": format_rupees(goal.lumpsum_today),
        "lumpsum_funds": [
            {
                "fund": short_fund_name(item.fund.scheme_name),
                "amount": format_rupees(item.amount),
            }
            for item in goal.lumpsum_funds
        ],
        "crash_test": (
            f"A severe crash after the first year could take "
            f"{format_rupees(goal.crash.value_before)} down to "
            f"{format_rupees(goal.crash.value_after)} ({goal.crash.loss_pct:.0f}% fall)"
        ),
    }
    if monthly:
        summary["monthly_sip"] = format_rupees(goal.funding.monthly_sip)
        summary["monthly_funds"] = [
            {
                "fund": short_fund_name(item.fund.scheme_name),
                "amount": format_rupees(item.amount),
            }
            for item in goal.sip_funds
        ]
    else:
        summary["extra_lumpsum_needed_today"] = format_rupees(
            goal.funding.lumpsum_needed_today
        )
    return summary


def plan_summary(plan: Plan) -> dict:
    """The whole plan: risk level, every goal, and whether it fits the budget."""
    summary = {
        "risk_level": plan.risk.bucket.name.lower(),
        "emergency_fund": (
            "adequate"
            if plan.risk.emergency_fund.is_adequate
            else f"short by {format_rupees(plan.risk.emergency_fund.shortfall)}"
        ),
        "goals": [
            goal_summary(goal, monthly=plan.affordability is not None)
            for goal in plan.goals
        ],
    }
    if plan.affordability is not None:
        affordability = plan.affordability
        summary["total_monthly_sip"] = format_rupees(affordability.sip_needed)
        summary["monthly_budget"] = format_rupees(affordability.sip_affordable)
        summary["fits_budget"] = affordability.is_affordable
        if not affordability.is_affordable:
            summary["monthly_shortfall"] = format_rupees(affordability.shortfall)
    return summary


def change_summary(reason: str, change: PlanChange) -> dict:
    """What a what-if did, goal by goal: the "now Rs X, was Rs Y" numbers."""
    return {
        "change": reason,
        "goals": [
            {
                "goal": goal.goal,
                "monthly_sip_now": format_rupees(goal.new_sip),
                "monthly_sip_before": format_rupees(goal.old_sip),
            }
            for goal in change.goals
        ],
        "total_now": format_rupees(change.new_total_sip),
        "total_before": format_rupees(change.old_total_sip),
        "fits_budget_now": change.now_affordable,
    }


def levers_summary(levers: list[Lever]) -> list[dict]:
    """Each way to close the shortfall, with the total SIP it leads to."""
    return [
        {
            "suggestion": lever.description,
            "total_monthly_sip": format_rupees(lever.monthly_sip),
        }
        for lever in levers
    ]
