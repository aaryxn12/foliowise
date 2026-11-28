"""Turn the form's free-text box into rules the planner can apply.

The LLM only fills in ExtractedRules (a strict schema); the planner applies them.
Anything the user asked for that isn't one of these rules goes in not_supported,
so the user is told it was noted but not applied, never silently dropped.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agent.llm import chat_model
from planner.inputs import ExcludableCategory, PlanInput, RiskCap, with_changes

EXTRACTION_PROMPT = """You read what an Indian investor wrote in the "anything else?" box \
of a mutual fund planning form, and turn it into rules for the planner.

Only two kinds of rule exist:
- excluded_categories: fund categories they do not want. Use only flexi_cap, mid_cap, \
small_cap and gold. "No gold" -> gold. "Nervous about small companies" -> small_cap. \
"Only index funds" -> flexi_cap, mid_cap and small_cap.
- max_risk: "conservative" or "moderate" if they say they want less risk than usual \
("play it safe", "I can't stomach big falls"). Leave it empty otherwise.

Put every other wish in not_supported, as a short phrase in plain words (for example \
"avoid tobacco companies", "also saving for a car"). Never guess a rule the user did not \
ask for. If the text asks for nothing, return empty rules."""


class ExtractedRules(BaseModel):
    """Rules read from the user's free text."""

    excluded_categories: list[ExcludableCategory] = Field(
        default_factory=list, description="Fund categories the user does not want"
    )
    max_risk: RiskCap | None = Field(
        None, description="A risk ceiling, only if the user asked for less risk"
    )
    not_supported: list[str] = Field(
        default_factory=list, description="Wishes that are not one of the rules above"
    )


def extract_rules(notes: str) -> ExtractedRules:
    """Ask the LLM to turn free text into ExtractedRules (no call for empty notes)."""
    if not notes.strip():
        return ExtractedRules()
    model = chat_model().with_structured_output(ExtractedRules)
    return model.invoke([SystemMessage(EXTRACTION_PROMPT), HumanMessage(notes)])


def apply_rules(plan_input: PlanInput, rules: ExtractedRules) -> PlanInput:
    """The form with the extracted rules filled in, validated again."""
    return with_changes(plan_input, excluded_categories=rules.excluded_categories, max_risk=rules.max_risk)
