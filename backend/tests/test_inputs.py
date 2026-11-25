import pytest
from pydantic import ValidationError

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


# --- A valid form -----------------------------------------------------------------


def test_valid_form_builds_with_nested_models():
    plan_input = priya()
    assert plan_input.savings.epf == 3_00_000
    assert plan_input.big_goal.years_away == 7
    assert plan_input.monthly_spare == 55_000


def test_optional_fields_have_safe_defaults():
    plan_input = priya(savings={}, big_goal=None, notes="")
    assert plan_input.savings.mutual_funds == 0
    assert plan_input.big_goal is None


def test_form_can_be_read_from_json():
    """The API will receive the form as JSON."""
    json_text = priya().model_dump_json()
    assert PlanInput.model_validate_json(json_text) == priya()


# --- Single-field rules -------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"age": 17},
        {"monthly_take_home": 0},
        {"emergency_fund": -1},
        {"quiz_answers": [4, 3, 5, 3]},  # answers run 1 to 4
        {"quiz_answers": [4, 3, 4]},  # exactly 4 answers
        {"mode": "weekly"},
        {"big_goal": {"kind": "yacht", "cost_today": 1, "years_away": 5}},
        {"big_goal": {"kind": "car", "cost_today": 5_00_000, "years_away": 0}},
    ],
)
def test_out_of_range_values_are_rejected(changes):
    with pytest.raises(ValidationError):
        priya(**changes)


def test_unknown_fields_are_rejected():
    """A typo like 'retirment_age' must fail, not be silently ignored."""
    with pytest.raises(ValidationError):
        priya(retirment_age=55)


def test_form_cannot_be_edited_after_validation():
    """What-ifs make a changed copy (model_copy) instead of editing in place."""
    plan_input = priya()
    with pytest.raises(ValidationError):
        plan_input.age = 40
    assert plan_input.model_copy(update={"retirement_age": 55}).retirement_age == 55


# --- Rules across several fields ------------------------------------------------------


@pytest.mark.parametrize("retirement_age", [45, 42])  # same as, or before, age 45
def test_retirement_must_be_after_current_age(retirement_age):
    with pytest.raises(ValidationError, match="must be after"):
        priya(age=45, retirement_age=retirement_age)


def test_outgoings_must_be_less_than_take_home():
    with pytest.raises(ValidationError, match="less than take-home"):
        priya(monthly_expenses=1_05_000)  # 1,05,000 + 15,000 EMIs = all of 1,20,000


def test_sip_budget_must_fit_what_is_left():
    with pytest.raises(ValidationError, match="SIP budget"):
        priya(monthly_sip_budget=60_000)  # only 55,000 is left


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "both", "lumpsum": 0},
        {"mode": "lumpsum", "lumpsum": 0},
        {"mode": "sip", "monthly_sip_budget": 0},
    ],
)
def test_each_mode_needs_its_amounts(changes):
    with pytest.raises(ValidationError, match="needs"):
        priya(**changes)


def test_lumpsum_only_mode_needs_no_monthly_budget():
    assert priya(mode="lumpsum", monthly_sip_budget=0).mode == "lumpsum"
