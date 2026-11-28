"""Money and percentages formatted for people (and for the LLM to copy as-is)."""

LAKH = 1_00_000
CRORE = 1_00_00_000


def format_rupees(amount: float) -> str:
    """Rupees the way Indians read them: ₹4.99 Cr, ₹30.07 L, ₹17,166."""
    if amount >= CRORE:
        return f"₹{amount / CRORE:.2f} Cr"
    if amount >= LAKH:
        return f"₹{amount / LAKH:.2f} L"
    return f"₹{amount:,.0f}"


def format_percent(share: float) -> str:
    """A share as a percentage with 2 decimals, e.g. 0.1055 -> "10.55%"."""
    return f"{share * 100:.2f}%"
