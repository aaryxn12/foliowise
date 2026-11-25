"""Build a complete plan from the user's form answers.

Each step is its own small function, so it can be tested and explained alone;
build_plan (coming next) calls them in order.
"""

from dataclasses import dataclass

from planner.allocation import (
    EmergencyFundStatus,
    RiskLevel,
    ability_level,
    emergency_fund_check,
    risk_bucket,
    willingness_from_quiz,
)
from planner.inputs import PlanInput


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
