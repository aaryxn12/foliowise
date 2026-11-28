"""Plan versions: what the user changed, what it did, and Undo.

Every what-if or lever adds a new version on top; Undo removes the latest one.
Histories are never edited in place: each change returns a new PlanHistory,
so an older version is always exactly as it was.
"""

from dataclasses import dataclass

from planner.inputs import PlanInput, with_changes
from planner.plan import FundPick, Plan, build_plan

MAX_VERSIONS = 20  # keep the history (and the session it is stored in) small


@dataclass(frozen=True)
class PlanVersion:
    """One version of the plan, and why it was made."""

    plan_input: PlanInput
    plan: Plan
    reason: str  # e.g. "Original plan" or "Retire at 58 instead of 50"


@dataclass(frozen=True)
class PlanHistory:
    """Every version so far, oldest first; the last one is the current plan."""

    versions: tuple[PlanVersion, ...]

    def __post_init__(self) -> None:
        # A saved chat comes back from the checkpointer with lists where tuples
        # were (its storage format has no tuples), so turn them back into one.
        object.__setattr__(self, "versions", tuple(self.versions))

    @property
    def current(self) -> PlanVersion:
        return self.versions[-1]

    @property
    def previous(self) -> PlanVersion | None:
        """The version before the current one, or None if there is only one."""
        return self.versions[-2] if len(self.versions) > 1 else None


@dataclass(frozen=True)
class GoalChange:
    """How one goal's monthly SIP moved between two versions."""

    goal: str
    old_sip: float
    new_sip: float


@dataclass(frozen=True)
class PlanChange:
    """What a change did to the plan: the "was Rs X" numbers for the dashboard."""

    goals: tuple[GoalChange, ...]
    old_total_sip: float
    new_total_sip: float
    now_affordable: bool
    monthly_budget: float | None  # None in lumpsum-only mode
    new_shortfall: float  # how much the new total exceeds the budget (0 if it fits)

    def __post_init__(self) -> None:
        # A checkpointer stores tuples as lists; turn them back (see PlanHistory).
        object.__setattr__(self, "goals", tuple(self.goals))


def start_history(
    plan_input: PlanInput, picks: dict[str, list[FundPick]] | None = None
) -> PlanHistory:
    """A new history holding just the original plan."""
    plan = build_plan(plan_input, picks)
    return PlanHistory((PlanVersion(plan_input, plan, "Original plan"),))


def apply_change(
    history: PlanHistory,
    reason: str,
    picks: dict[str, list[FundPick]] | None = None,
    **changes,
) -> PlanHistory:
    """A new history with one more version: the current form with `changes` applied.

    Raises pydantic.ValidationError if the change makes the form invalid.
    Keeps at most MAX_VERSIONS, dropping the oldest (the original stays first).
    """
    plan_input = with_changes(history.current.plan_input, **changes)
    version = PlanVersion(plan_input, build_plan(plan_input, picks), reason)
    versions = (*history.versions, version)
    if len(versions) > MAX_VERSIONS:
        versions = versions[:1] + versions[-(MAX_VERSIONS - 1) :]  # keep the original
    return PlanHistory(versions)


def undo(history: PlanHistory) -> PlanHistory:
    """The history without its latest version. The original plan can't be undone."""
    if history.previous is None:
        raise ValueError("Nothing to undo")
    return PlanHistory(history.versions[:-1])


def monthly_sips(plan: Plan) -> dict[str, float]:
    """Each goal's monthly SIP, keyed by goal name."""
    return {goal.target.name: goal.funding.monthly_sip for goal in plan.goals}


def compare(old: Plan, new: Plan) -> PlanChange:
    """What changed between two plans, goal by goal.

    A goal in only one of the plans (e.g. the big goal was removed) shows 0 on
    the side where it is missing.
    """
    old_sips, new_sips = monthly_sips(old), monthly_sips(new)
    names = list(old_sips) + [name for name in new_sips if name not in old_sips]
    goals = tuple(
        GoalChange(name, old_sips.get(name, 0.0), new_sips.get(name, 0.0))
        for name in names
    )
    return PlanChange(
        goals=goals,
        old_total_sip=sum(old_sips.values()),
        new_total_sip=sum(new_sips.values()),
        now_affordable=new.affordability is not None
        and new.affordability.is_affordable,
        monthly_budget=new.affordability.sip_affordable if new.affordability else None,
        new_shortfall=new.affordability.shortfall if new.affordability else 0.0,
    )


def last_change(history: PlanHistory) -> PlanChange | None:
    """What the latest version changed, or None if there is only the original."""
    if history.previous is None:
        return None
    return compare(history.previous.plan, history.current.plan)
