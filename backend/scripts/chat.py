"""Chat with FolioWise in the terminal, using Priya's sample form.

Run from the backend folder (needs internet and GROQ_API_KEY in backend/.env):
    python -m scripts.chat
It first asks the form's "anything else?" question, turns your answer into rules,
then starts the chat. Type "quit" to stop. Tool calls are printed.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import build_graph
from agent.rules import apply_rules, extract_rules
from agent.tools import fund_picks
from planner.history import start_history
from tests.sample_forms import priya

THREAD = {"configurable": {"thread_id": "terminal-chat"}}  # one saved conversation


def main() -> None:
    graph = build_graph()
    notes = input("Anything else we should know? (Enter to skip)\nYou: ").strip()
    rules = extract_rules(notes)
    form = apply_rules(priya(notes=notes), rules)
    print(f"  [rules] exclude: {rules.excluded_categories or 'none'}, risk ceiling: {rules.max_risk or 'none'}")
    if rules.not_supported:
        print(f"  [rules] noted but not applied: {rules.not_supported}")
    first_turn = True
    print("FolioWise: Hi! Your plan is ready. Ask me about it, or try a what-if.")
    while (text := input("\nYou: ").strip()).lower() != "quit":
        if not text:
            continue
        update = {"messages": [HumanMessage(text)]}
        if first_turn:  # the plan goes into the saved state once, at the start
            update["history"] = start_history(form, fund_picks())
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
