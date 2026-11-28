"""The agent as a graph: the LLM node and the tools node, looping until it answers.

    START -> agent -> (asked for a tool?) -> tools -> agent -> ... -> END
"""

from langchain_core.messages import SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.llm import chat_model
from agent.prompts import SYSTEM_PROMPT
from agent.state import AgentState
from agent.tools import TOOLS

# The only types a saved chat may contain besides LangChain's own: our planner
# objects. A checkpoint loader that rebuilt any type would let a tampered save
# create arbitrary objects, so LangGraph asks for an explicit list.
SAVED_TYPES = [
    ("planner.inputs", "PlanInput"),
    ("planner.inputs", "ExistingSavings"),
    ("planner.inputs", "BigGoal"),
    ("planner.allocation", "RiskLevel"),
    ("planner.allocation", "Allocation"),
    ("planner.allocation", "EmergencyFundStatus"),
    ("planner.allocation", "CrashTestResult"),
    ("planner.sip", "GoalFunding"),
    ("planner.sip", "Affordability"),
    ("planner.plan", "RiskProfile"),
    ("planner.plan", "GoalTarget"),
    ("planner.plan", "GoalMix"),
    ("planner.plan", "FundPick"),
    ("planner.plan", "FundAmount"),
    ("planner.plan", "GoalPlan"),
    ("planner.plan", "Plan"),
    ("planner.history", "PlanVersion"),
    ("planner.history", "PlanHistory"),
]


def default_checkpointer() -> InMemorySaver:
    """Chats saved in memory (lost on restart); DynamoDB replaces this in milestone 9."""
    return InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=SAVED_TYPES))


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """The compiled agent. `checkpointer` saves each chat's state between messages."""
    model = chat_model().bind_tools(TOOLS)  # the LLM now knows each tool's schema

    def agent(state: AgentState) -> dict:
        """Ask the LLM what to do next: answer, or call one or more tools."""
        messages = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [model.invoke(messages)]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer or default_checkpointer())
