"""Planner functions the LLM can ask to run.

Each tool's docstring and argument descriptions are what the LLM reads to
decide when and how to call it, so they are written for the model.
Tools receive the agent's state through InjectedState: LangGraph fills it in,
and it is hidden from the LLM, which can only request a tool, never edit the plan.
"""

import json
from functools import cache
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field, ValidationError

from agent.state import AgentState
from agent.summaries import change_summary, levers_summary, plan_summary
from planner.history import apply_change, compare, last_change, undo
from planner.levers import shortfall_levers
from planner.plan import FundPick, load_fund_picks


@cache
def fund_picks() -> dict[str, list[FundPick]]:
    """The scored fund shortlist, read from disk once and then reused."""
    return load_fund_picks()


def to_json(data) -> str:
    """Tool results go back to the LLM as JSON text, keeping the ₹ sign readable."""
    return json.dumps(data, ensure_ascii=False)


class WhatIfChanges(BaseModel):
    """The form answers a what-if may change. Leave out anything not mentioned."""

    retirement_age: int | None = Field(None, description="Age at which to retire, e.g. 55")
    retirement_monthly_expense: float | None = Field(
        None, description="Monthly spending in retirement, in today's rupees"
    )
    monthly_sip_budget: float | None = Field(None, description="Rupees the user can invest each month")
    lumpsum: float | None = Field(None, description="One-time amount available to invest today")
    big_goal_cost_today: float | None = Field(None, description="Cost of the big goal in today's rupees")
    big_goal_years_away: int | None = Field(None, description="Years until the big goal")


def form_changes(changes: WhatIfChanges, current_big_goal) -> dict:
    """WhatIfChanges as keyword arguments for with_changes (big goal fields nested)."""
    flat = changes.model_dump(exclude_none=True)
    goal_updates = {
        field: flat.pop(f"big_goal_{field}")
        for field in ("cost_today", "years_away")
        if f"big_goal_{field}" in flat
    }
    if goal_updates:
        if current_big_goal is None:
            raise ValueError("The user has no big goal to change")
        flat["big_goal"] = current_big_goal.model_dump() | goal_updates
    return flat


@tool
def show_plan(state: Annotated[AgentState, InjectedState]) -> str:
    """Show the user's current plan: risk level, emergency fund, and for each goal
    its cost, investment mix, expected return, monthly SIP, funds and crash test,
    plus whether the total fits the monthly budget. Use it to answer any question
    about the plan; never work out these numbers yourself."""
    current = state["history"].current
    return to_json(plan_summary(current.plan, current.plan_input))


@tool
def try_what_if(
    changes: WhatIfChanges,
    reason: Annotated[str, "Short description of the change, e.g. 'Retire at 55 instead of 50'"],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Change one or more of the user's answers, rebuild the plan, and report each
    goal's monthly SIP now versus before. The change is kept (it can be undone)."""
    history = state["history"]
    try:
        kwargs = form_changes(changes, history.current.plan_input.big_goal)
        if not kwargs:
            raise ValueError("No change was given")
        new_history = apply_change(history, reason, fund_picks(), **kwargs)
    except (ValidationError, ValueError) as error:
        # Report the problem to the LLM instead of crashing; the plan is unchanged.
        message = f"Change not applied: {error}"
        return Command(update={"messages": [ToolMessage(message, tool_call_id=tool_call_id)]})
    result = to_json(
        change_summary(
            reason,
            last_change(new_history),
            before=history.current.plan_input,
            after=new_history.current.plan_input,
        )
    )
    return Command(
        update={
            "history": new_history,
            "messages": [ToolMessage(result, tool_call_id=tool_call_id)],
        }
    )


@tool
def suggest_fixes(state: Annotated[AgentState, InjectedState]) -> str:
    """If the plan's monthly SIPs are more than the budget, list the smallest single
    changes that would make it fit (retire later, spend less in retirement, delay or
    shrink the big goal), each with the total SIP it leads to."""
    levers = shortfall_levers(state["history"].current.plan_input, fund_picks())
    if not levers:
        return to_json({"message": "The plan already fits the budget"})
    return to_json(levers_summary(levers))


@tool
def undo_last_change(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Undo the most recent what-if, going back to the previous plan. Reports the
    answers and each goal's monthly SIP after undoing versus before."""
    history = state["history"]
    try:
        new_history = undo(history)
    except ValueError:
        message = "Nothing to undo: this is the original plan."
        return Command(update={"messages": [ToolMessage(message, tool_call_id=tool_call_id)]})
    summary = change_summary(
        f"Undid '{history.current.reason}'; back to '{new_history.current.reason}'",
        compare(history.current.plan, new_history.current.plan),
        before=history.current.plan_input,
        after=new_history.current.plan_input,
    )
    message = to_json(summary)
    return Command(
        update={
            "history": new_history,
            "messages": [ToolMessage(message, tool_call_id=tool_call_id)],
        }
    )


TOOLS = [show_plan, try_what_if, suggest_fixes, undo_last_change]
