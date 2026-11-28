"""The user's form answers, validated before any planning maths runs.

Everything that builds a plan (the web form, the API, the chat agent's
what-ifs) produces a PlanInput, so bad values are caught in one place.
Amounts are in rupees; "today's rupees" means before inflation.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QuizAnswer = Annotated[int, Field(ge=1, le=4)]  # each risk-quiz answer is 1 to 4

MAX_RETIREMENT_AGE = 75

# Fund categories a user may rule out. Large cap index and debt are the core of
# every plan, so they always stay.
ExcludableCategory = Literal["flexi_cap", "mid_cap", "small_cap", "gold"]
RiskCap = Literal["conservative", "moderate"]
MAX_GOAL_YEARS = 40


class ExistingSavings(BaseModel):
    """Money already invested, by type (each grows at its own rate)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mutual_funds: float = Field(0, ge=0)
    fixed_deposits: float = Field(0, ge=0)
    ppf: float = Field(0, ge=0)
    epf: float = Field(0, ge=0)


class BigGoal(BaseModel):
    """One large expense besides retirement, e.g. a house down payment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["house", "car", "education", "other"]
    cost_today: float = Field(gt=0)  # today's rupees
    years_away: int = Field(ge=1, le=MAX_GOAL_YEARS)


class PlanInput(BaseModel):
    """Everything the plan builder needs, from the 5-step form."""

    # frozen: a what-if makes a changed copy instead of editing this one.
    # extra="forbid": a misspelt field is an error, not silently ignored.
    model_config = ConfigDict(frozen=True, extra="forbid")

    # About you
    age: int = Field(ge=18, le=70)
    dependents: int = Field(0, ge=0, le=10)
    spouse_earns: bool = False

    # Money (monthly)
    monthly_take_home: float = Field(gt=0)
    monthly_expenses: float = Field(gt=0)
    monthly_emis: float = Field(0, ge=0)
    emergency_fund: float = Field(0, ge=0)
    savings: ExistingSavings = Field(default_factory=ExistingSavings)

    # Goals
    retirement_age: int = Field(ge=30, le=MAX_RETIREMENT_AGE)
    retirement_monthly_expense: float = Field(gt=0)  # today's rupees
    big_goal: BigGoal | None = None

    # Risk quiz and how to invest
    quiz_answers: list[QuizAnswer] = Field(min_length=4, max_length=4)
    mode: Literal["sip", "lumpsum", "both"] = "sip"
    monthly_sip_budget: float = Field(0, ge=0)  # what the user can invest each month
    lumpsum: float = Field(0, ge=0)  # one-time amount available today
    notes: str = Field("", max_length=1000)  # free text; the agent turns it into the rules below

    # Rules from the notes (or a what-if): categories to leave out, and a risk ceiling.
    excluded_categories: list[ExcludableCategory] = Field(default_factory=list)
    max_risk: RiskCap | None = None  # never take more risk than this, whatever the quiz says

    @property
    def monthly_spare(self) -> float:
        """Take-home left after expenses and EMIs."""
        return self.monthly_take_home - self.monthly_expenses - self.monthly_emis

    @model_validator(mode="after")
    def retirement_is_in_the_future(self) -> "PlanInput":
        """Retirement age must be after the current age."""
        if self.retirement_age <= self.age:
            raise ValueError(
                f"Retirement age ({self.retirement_age}) must be after current age ({self.age})"
            )
        return self

    @model_validator(mode="after")
    def outgoings_fit_income(self) -> "PlanInput":
        """Expenses and EMIs must leave something over, and the budget must fit."""
        if self.monthly_spare <= 0:
            raise ValueError(
                "Monthly expenses and EMIs must be less than take-home pay"
            )
        if self.monthly_sip_budget > self.monthly_spare:
            raise ValueError(
                f"Monthly SIP budget ({self.monthly_sip_budget:,.0f}) is more than what is "
                f"left after expenses and EMIs ({self.monthly_spare:,.0f})"
            )
        return self

    @model_validator(mode="after")
    def mode_has_its_amounts(self) -> "PlanInput":
        """SIP modes need a monthly budget; lumpsum modes need a lumpsum."""
        if self.mode in ("sip", "both") and self.monthly_sip_budget <= 0:
            raise ValueError(f"Mode '{self.mode}' needs a monthly SIP budget")
        if self.mode in ("lumpsum", "both") and self.lumpsum <= 0:
            raise ValueError(f"Mode '{self.mode}' needs a lumpsum amount")
        return self


def with_changes(plan_input: PlanInput, **changes) -> PlanInput:
    """A copy of the form with some answers changed, validated again.

    Unlike plan_input.model_copy(update=...), this re-runs every check, so a
    what-if can't produce an impossible form (e.g. retiring before today's age).
    """
    return PlanInput.model_validate(plan_input.model_dump() | changes)
