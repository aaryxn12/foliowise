"""Rank funds within each category and pick a shortlist.

Every metric becomes a percentile rank inside its category (1.0 = best), and
the score is a weighted mix of those ranks, from 0 to 100. Raw past return is
deliberately not scored: it depends on start and end dates, and it rewards luck.
"""

import pandas as pd

# How much each metric counts towards the score. Must add up to 1.
WEIGHTS = {
    "consistency": 0.35,
    "expense_ratio": 0.25,
    "sharpe": 0.25,
    "max_drawdown": 0.15,
}

# Shrinkage strength: every fund starts as if it had this many extra windows,
# half won and half lost, so a few lucky windows can't look like a proven record.
PRIOR_WINDOWS = 12

SHORTLIST_SIZE = 3  # top pick + 2 alternatives per category


def shrunk_consistency(consistency: float, windows: int, prior_windows: int = PRIOR_WINDOWS) -> float:
    """Consistency pulled towards 0.5, strongly when based on few windows.

    adjusted = (wins + prior_windows / 2) / (windows + prior_windows),
    where wins = consistency * windows. A fund with no windows gets 0.5.
    """
    if windows == 0:
        return 0.5
    wins = consistency * windows
    return (wins + prior_windows / 2)/(windows + prior_windows)


def score_funds(metrics: pd.DataFrame) -> pd.DataFrame:
    """Add percentile ranks within each category and a 0-100 score.

    Expects the columns written by compute_metrics.py. Adds consistency_adjusted,
    one <metric>_pct column per WEIGHTS key (1.0 = best in category), and score.
    """
    scored = metrics.copy()  # never change the caller's DataFrame
    scored["consistency_adjusted"] = [
        shrunk_consistency(value, windows)
        for value, windows in zip(scored["consistency"], scored["windows_compared"])
    ]

    by_category = scored.groupby("category")
    # ascending=True: a higher value ranks higher (better).
    scored["consistency_pct"] = by_category["consistency_adjusted"].rank(pct=True)
    scored["sharpe_pct"] = by_category["sharpe_5y"].rank(pct=True)
    # Drawdowns are negative: -0.15 beats -0.30, so higher is still better.
    scored["max_drawdown_pct"] = by_category["max_drawdown_5y"].rank(pct=True)
    # A lower fee is better, so rank in reverse.
    scored["expense_ratio_pct"] = by_category["expense_ratio"].rank(pct=True, ascending=False)

    scored["score"] = 100 * sum(
        weight * scored[f"{metric}_pct"] for metric, weight in WEIGHTS.items()
    )
    return scored


def shortlist(scored: pd.DataFrame, size: int = SHORTLIST_SIZE) -> pd.DataFrame:
    """The best `size` funds in each category, with rank 1 = top pick.

    Ties on score go to the cheaper fund.
    """
    ordered = scored.sort_values(
        ["category", "score", "expense_ratio"], ascending=[True, False, True]
    )
    top = ordered.groupby("category").head(size).copy()
    top["rank"] = top.groupby("category").cumcount() + 1
    return top.reset_index(drop=True)
