"""Time-value-of-money maths for FolioWise. Pure functions: no I/O, no LLM."""


def annual_to_monthly_rate(annual_rate: float) -> float:
    """Effective monthly rate for an effective annual rate. 0.12 → ~0.009489."""
    return (1 + annual_rate) ** (1 / 12) - 1


def future_cost(amount_today: float, inflation: float, years: int) -> float:
    """Cost after `years` of inflation. ₹20L, 6%, 7 yrs → ~₹30,07,261."""
    return amount_today * (1 + inflation) ** years