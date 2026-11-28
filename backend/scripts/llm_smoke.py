"""Check that the configured LLM answers. Needs internet and an API key in backend/.env.

Run from the backend folder:
    python -m scripts.llm_smoke
"""

from agent.llm import chat_model


def main() -> None:
    model = chat_model()
    reply = model.invoke("Reply with exactly these words: FolioWise is connected")
    print(f"Model: {type(model).__name__}")
    print(f"Reply: {reply.content}")
    print(f"Tokens: {reply.usage_metadata}")


if __name__ == "__main__":
    main()
