"""Which LLM the agent talks to, chosen by the FOLIOWISE_LLM setting.

Every LangChain chat model has the same methods (invoke, bind_tools, ...), so
the rest of the agent calls chat_model() and never knows which provider it got.
    FOLIOWISE_LLM=groq       free tier while building (the default)
    FOLIOWISE_LLM=anthropic  Claude Haiku for the live site
API keys come from backend/.env (GROQ_API_KEY, ANTHROPIC_API_KEY), never from code.
"""

import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

load_dotenv()  # read backend/.env into os.environ, if the file exists

MODELS = {
    "groq": "openai/gpt-oss-120b",
    "anthropic": "claude-haiku-5-5",
}
DEFAULT_PROVIDER = "groq"
TEMPERATURE = 0  # the same message should be routed the same way every time
# gpt-oss "thinks" before answering, billed as output tokens. The agent routes and
# explains numbers the planner already computed, so little thinking is needed.
GROQ_REASONING_EFFORT = "low"


def chat_model(provider: str | None = None) -> BaseChatModel:
    """The chat model for `provider`, or for the FOLIOWISE_LLM setting if not given."""
    provider = provider or os.environ.get("FOLIOWISE_LLM", DEFAULT_PROVIDER)
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=MODELS["groq"],
            temperature=TEMPERATURE,
            reasoning_effort=GROQ_REASONING_EFFORT,
        )
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as error:  # only installed for the live site (milestone 9)
            raise ImportError("Run `pip install langchain-anthropic` to use Claude") from error
        return ChatAnthropic(model=MODELS["anthropic"], temperature=TEMPERATURE)
    raise ValueError(f"Unknown FOLIOWISE_LLM {provider!r}; use one of {sorted(MODELS)}")
