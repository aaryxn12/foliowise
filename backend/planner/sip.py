"""Time-value-of-money maths for FolioWise. Pure functions: no I/O, no LLM."""


def annual_to_monthly_rate(annual_rate: float) -> float:
    """Effective monthly rate for an effective annual rate. 0.12 → ~0.009489."""
    return (1 + annual_rate) ** (1 / 12) - 1


def future_cost(amount_today: float, inflation: float, years: int) -> float:
    """Cost after `years` of inflation. ₹20L, 6%, 7 yrs → ~₹30,07,261."""
    return future_value_lumpsum(amount_today, inflation, years)


def future_value_lumpsum(amount: float, annual_return: float, years: int) -> float:
    """What `amount` invested today grows to. ₹5L, 10%, 7 yrs → ~₹9,74,359."""
    return amount * (1 + annual_return) ** years


def lumpsum_needed(target_fv: float, annual_return: float, years: int) -> float:
    """Amount to invest today to reach `target_fv`. ₹30.07L, 10%, 7 yrs → ~₹15,43,200."""
    return target_fv / (1 + annual_return) ** years
