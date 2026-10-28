"""Time-value-of-money maths for FolioWise. Pure functions: no I/O, no LLM."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GoalFunding:
    """How a goal can be funded today.

    At most one of `lumpsum_needed_today` and `surplus_today` is non-zero.
    """

    monthly_sip: float  # start-of-month SIP that closes the gap (0 if none)
    lumpsum_needed_today: float  # extra one-time amount needed today instead of a SIP
    surplus_today: float  # existing money beyond what the goal needs, in today's rupees


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


def sip_needed(
    target_fv: float,
    annual_return: float,
    years: int,
    existing_lumpsum: float = 0,
) -> GoalFunding:
    """Monthly SIP (paid at the start of each month) to reach `target_fv`.

    Any existing lumpsum is grown to the goal date before it is subtracted, so
    money from different dates is never mixed.
    House goal: ₹30,07,261, 10%, 7 yrs, no lumpsum → SIP ~₹25,077.
    """
    monthly_rate = annual_to_monthly_rate(annual_return)
    months = years * 12

    pv_of_goal = lumpsum_needed(target_fv, annual_return, years)
    lumpsum_needed_today = max(0.0, pv_of_goal - existing_lumpsum)
    surplus_today = max(0.0, existing_lumpsum - pv_of_goal)

    gap = target_fv - future_value_lumpsum(existing_lumpsum, annual_return, years)
    if gap <= 0:
        return GoalFunding(
            monthly_sip=0.0,
            lumpsum_needed_today=lumpsum_needed_today,
            surplus_today=surplus_today,
        )

    # FV of ₹1 per month, paid at the start of each month (annuity due).
    annuity_due_factor = ((1 + monthly_rate) ** months - 1) / monthly_rate * (1 + monthly_rate)

    return GoalFunding(
        monthly_sip=gap / annuity_due_factor,
        lumpsum_needed_today=lumpsum_needed_today,
        surplus_today=surplus_today,
    )
