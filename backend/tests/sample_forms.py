"""Sample form answers shared by the tests."""

from planner.inputs import PlanInput


def priya(**changes):
    """A valid form: Priya, 30, two dependents, house in 7 years, retiring at 50."""
    answers = {
        "age": 30,
        "dependents": 2,
        "spouse_earns": False,
        "monthly_take_home": 1_20_000,
        "monthly_expenses": 50_000,
        "monthly_emis": 15_000,
        "emergency_fund": 3_00_000,
        "savings": {
            "mutual_funds": 2_00_000,
            "fixed_deposits": 1_00_000,
            "ppf": 1_50_000,
            "epf": 3_00_000,
        },
        "retirement_age": 50,
        "retirement_monthly_expense": 50_000,
        "big_goal": {"kind": "house", "cost_today": 20_00_000, "years_away": 7},
        "quiz_answers": [4, 3, 4, 3],
        "mode": "both",
        "monthly_sip_budget": 40_000,
        "lumpsum": 2_00_000,
    }
    answers.update(changes)
    return PlanInput(**answers)
