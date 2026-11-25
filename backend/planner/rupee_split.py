"""Turn a monthly SIP (or a lumpsum) into a rounded rupee amount per category.

Rules:
1. The total is rounded up to a multiple of STEP, so the goal stays fully funded.
2. Categories whose share would be less than one STEP are dropped, and their
   share goes to the rest. Small SIPs therefore end up in fewer funds.
3. Amounts are multiples of STEP and add up exactly to the rounded total, using
   the largest remainder method: round every amount down, then give the leftover
   steps to the amounts that lost the most (larger share first on a tie).
"""

import math

STEP = 500  # rupees; also the smallest SIP we suggest in any category


def round_up_to_step(amount: float, step: int = STEP) -> int:
    """`amount` rounded up to the next multiple of `step`, e.g. 24,863 -> 25,000."""
    return math.ceil(amount / step) * step


def split_amount(
    total: float, shares: dict[str, float], step: int = STEP
) -> dict[str, int]:
    """Rupees per category, in multiples of `step`, adding up to the rounded total.

    `shares` maps category -> fraction of the total and must add up to 1.
    Categories that end up with nothing are left out of the result.
    """
    if not math.isclose(sum(shares.values()), 1.0, abs_tol=1e-9):
        raise ValueError(f"Shares must add up to 1, got {sum(shares.values()):.4f}")

    total = round_up_to_step(total, step)
    kept = {
        category: share for category, share in shares.items() if share * total >= step
    }
    if not kept:  # too small to split at all: everything goes to the biggest share
        return {max(shares, key=shares.get): total}

    kept_share = sum(kept.values())  # less than 1 if some categories were dropped
    # Ideal amounts, rounded to paise so float noise can't change who wins a tie.
    ideal = {
        category: round(total * share / kept_share, 2)
        for category, share in kept.items()
    }
    amounts = {category: int(value // step) * step for category, value in ideal.items()}

    leftover_steps = (total - sum(amounts.values())) // step
    biggest_loss_first = sorted(
        kept,
        key=lambda category: (ideal[category] - amounts[category], kept[category]),
        reverse=True,
    )
    for category in biggest_loss_first[:leftover_steps]:
        amounts[category] += step
    return amounts
