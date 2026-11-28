"""Chat with FolioWise in the terminal, using Priya's sample form.

Run from the backend folder (needs internet and GROQ_API_KEY in backend/.env):
    python -m scripts.chat
Type "quit" to stop. Tool calls are printed so you can see what the agent did.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import build_graph
from agent.tools import fund_picks
from planner.history import start_history
from tests.sample_forms import priya

THREAD = {"configurable": {"thread_id": "terminal-chat"}}  # one saved conversation


def main() -> None:
    graph = build_graph()
    first_turn = True
    print("FolioWise: Hi! Your plan is ready. Ask me about it, or try a what-if.")
    while (text := input("\nYou: ").strip()).lower() != "quit":
        if not text:
            continue
        update = {"messages": [HumanMessage(text)]}
        if first_turn:  # the plan goes into the saved state once, at the start
            update["history"] = start_history(priya(), fund_picks())
            first_turn = False
        result = graph.invoke(update, THREAD)
        for message in new_messages(result["messages"], text):
            if isinstance(message, AIMessage) and message.tool_calls:
                for call in message.tool_calls:
                    print(f"  [tool] {call['name']}({call['args']})")
            elif isinstance(message, ToolMessage):
                continue
            elif isinstance(message, AIMessage):
                print(f"\nFolioWise: {message.content}")


def new_messages(messages: list, text: str) -> list:
    """The messages added in this turn: everything after the user's latest message."""
    last_user = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage) and m.content == text)
    return messages[last_user + 1 :]


if __name__ == "__main__":
    main()
