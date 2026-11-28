import pytest
from pydantic import ValidationError

from planner.history import (
    MAX_VERSIONS,
    PlanHistory,
    apply_change,
    compare,
    last_change,
    start_history,
    undo,
)
from planner.plan import build_plan, fund_picks
from tests.sample_forms import priya
from tests.test_plan import tiny_metrics

PICKS = fund_picks(tiny_metrics())


def test_a_new_history_holds_only_the_original_plan():
    history = start_history(priya(), PICKS)
    assert len(history.versions) == 1
    assert history.current.reason == "Original plan"
    assert history.previous is None
    assert last_change(history) is None


def test_a_change_adds_a_version_and_keeps_the_old_one():
    original = start_history(priya(), PICKS)
    changed = apply_change(
        original, "Retire at 58 instead of 50", PICKS, retirement_age=58
    )
    assert len(changed.versions) == 2
    assert changed.current.plan_input.retirement_age == 58
    assert changed.previous.plan_input.retirement_age == 50
    assert len(original.versions) == 1  # the old history is untouched


def test_changes_build_on_the_current_version():
    history = start_history(priya(), PICKS)
    history = apply_change(history, "Retire at 58", PICKS, retirement_age=58)
    history = apply_change(
        history, "Spend less", PICKS, retirement_monthly_expense=40_000
    )
    assert history.current.plan_input.retirement_age == 58  # the first change is kept
    assert history.current.plan_input.retirement_monthly_expense == 40_000


def test_an_invalid_change_is_refused():
    with pytest.raises(ValidationError):
        apply_change(
            start_history(priya(), PICKS), "Too early", PICKS, retirement_age=25
        )


def test_retiring_later_lowers_the_retirement_sip_only():
    history = apply_change(
        start_history(priya(), PICKS),
        "Retire at 58 instead of 50",
        PICKS,
        retirement_age=58,
    )
    change = last_change(history)
    house, retirement = change.goals
    assert house.goal == "house" and house.new_sip == pytest.approx(house.old_sip)
    assert retirement.goal == "retirement" and retirement.new_sip < retirement.old_sip
    assert change.new_total_sip < change.old_total_sip
    assert change.old_total_sip == pytest.approx(79_059, abs=2)
    assert change.monthly_budget == 40_000
    assert change.new_shortfall == pytest.approx(change.new_total_sip - 40_000)


def test_compare_shows_zero_for_a_removed_goal():
    with_house = build_plan(priya(), PICKS)
    without_house = build_plan(priya(big_goal=None), PICKS)
    house = compare(with_house, without_house).goals[0]
    assert house.goal == "house" and house.new_sip == 0


def test_history_is_capped_but_keeps_the_original():
    history = start_history(priya(), PICKS)
    for step in range(MAX_VERSIONS + 5):
        history = apply_change(
            history, f"Change {step}", PICKS, monthly_sip_budget=30_000 + step
        )
    assert len(history.versions) == MAX_VERSIONS
    assert history.versions[0].reason == "Original plan"
    assert history.current.reason == f"Change {MAX_VERSIONS + 4}"


# --- Undo ------------------------------------------------------------------------------


def test_undo_goes_back_one_version():
    history = start_history(priya(), PICKS)
    changed = apply_change(history, "Retire at 58", PICKS, retirement_age=58)
    back = undo(changed)
    assert back.current.plan_input.retirement_age == 50
    assert len(back.versions) == 1


def test_undo_twice_after_two_changes():
    history = start_history(priya(), PICKS)
    history = apply_change(history, "Retire at 58", PICKS, retirement_age=58)
    history = apply_change(
        history, "Spend less", PICKS, retirement_monthly_expense=40_000
    )
    assert undo(history).current.reason == "Retire at 58"
    assert undo(undo(history)).current.reason == "Original plan"


def test_the_original_plan_cannot_be_undone():
    with pytest.raises(ValueError, match="Nothing to undo"):
        undo(start_history(priya(), PICKS))


def test_history_loaded_with_a_list_still_works():
    """A checkpointer stores tuples as lists; a history rebuilt from one must still
    take new changes and undo."""
    original = start_history(priya(), PICKS)
    loaded = PlanHistory(list(original.versions))  # what a save -> load gives back
    assert isinstance(loaded.versions, tuple)
    changed = apply_change(loaded, "Retire at 58", PICKS, retirement_age=58)
    assert len(changed.versions) == 2
    assert undo(changed).current.reason == "Original plan"
