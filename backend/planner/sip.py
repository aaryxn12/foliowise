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


@dataclass(frozen=True)
class Affordability:
    """SIP the goals need compared with what the user can invest each month.

    At most one of `shortfall` and `surplus` is non-zero.
    """

    sip_needed: float
    sip_affordable: float
    shortfall: float  # how much more per month is needed (0 if affordable)
    surplus: float  # spare monthly capacity after the plan (0 if short)
    coverage_pct: float  # share of the needed SIP the user can cover, capped at 100
    is_affordable: bool


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
    annuity_due_factor = (
        ((1 + monthly_rate) ** months - 1) / monthly_rate * (1 + monthly_rate)
    )

    return GoalFunding(
        monthly_sip=gap / annuity_due_factor,
        lumpsum_needed_today=lumpsum_needed_today,
        surplus_today=surplus_today,
    )


def retirement_corpus(
    first_year_expense: float,
    years_in_retirement: int,
    inflation: float,
    post_retirement_return: float,
) -> float:
    """Money needed on retirement day to pay inflation-growing yearly expenses.

    Expenses are paid at the start of each retirement year (annuity due) and grow
    with inflation; the remaining corpus keeps earning `post_retirement_return`.
    Summing year by year handles return == inflation with no special case.
    ₹19,24,281 a year, 35 years, 6% inflation, 8% return → ~₹4.99 Cr.
    """
    if years_in_retirement < 0:
        raise ValueError("years_in_retirement cannot be negative")

    growth_vs_return = (1 + inflation) / (1 + post_retirement_return)
    return sum(
        first_year_expense * growth_vs_return**year
        for year in range(years_in_retirement)
    )


def check_affordability(sip_needed: float, sip_affordable: float) -> Affordability:
    """Compare the SIP the goals need with what the user can invest each month."""
    if sip_needed < 0 or sip_affordable < 0:
        raise ValueError("SIP amounts cannot be negative")

    coverage_pct = (
        100.0 if sip_needed == 0 else min(100.0, sip_affordable / sip_needed * 100)
    )
    return Affordability(
        sip_needed=sip_needed,
        sip_affordable=sip_affordable,
        shortfall=max(0.0, sip_needed - sip_affordable),
        surplus=max(0.0, sip_affordable - sip_needed),
        coverage_pct=coverage_pct,
        is_affordable=sip_affordable >= sip_needed,
    )
