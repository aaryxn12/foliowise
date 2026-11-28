"""What the agent carries from step to step (and, later, between visits)."""

from langgraph.graph import MessagesState

from planner.history import PlanHistory


class AgentState(MessagesState):
    """The chat so far ("messages", from MessagesState) plus every plan version."""

    history: PlanHistory
