import math

import pandas as pd
import pytest

from planner.scoring import (
    PRIOR_WINDOWS,
    WEIGHTS,
    score_funds,
    shortlist,
    shrunk_consistency,
)


def fund(code, category, *, consistency=0.5, windows=100, sharpe=0.5, drawdown=-0.2, fee=1.0):
    """One row of fund_metrics.csv, with average values unless told otherwise."""
    return {
        "scheme_code": code,
        "category": category,
        "consistency": consistency,
        "windows_compared": windows,
        "sharpe_5y": sharpe,
        "max_drawdown_5y": drawdown,
        "expense_ratio": fee,
    }


# --- Shrinking consistency towards 50% ------------------------------------------


def test_weights_add_up_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_few_windows_are_pulled_strongly_towards_half():
    """5 wins out of 5: (5 + 6) / (5 + 12) = 11/17, about 0.65."""
    assert shrunk_consistency(1.0, 5) == pytest.approx(11 / 17)


def test_many_windows_barely_move():
    """107 wins out of 107: (107 + 6) / (107 + 12), about 0.95."""
    assert shrunk_consistency(1.0, 107) == pytest.approx(113 / 119)


def test_bad_luck_is_pulled_up_too():
    """0 wins out of 2: (0 + 6) / (2 + 12), about 0.43, not a damning 0."""
    assert shrunk_consistency(0.0, 2) == pytest.approx(6 / 14)


def test_no_windows_means_a_coin_flip():
    """consistency() returns NaN when there is nothing to compare."""
    assert shrunk_consistency(math.nan, 0) == pytest.approx(0.5)


def test_prior_strength_can_be_changed():
    assert shrunk_consistency(1.0, 10, prior_windows=0) == pytest.approx(1.0)
    assert PRIOR_WINDOWS == 12


# --- Percentile ranks and the score ---------------------------------------------


def test_the_best_fund_on_every_metric_scores_100():
    metrics = pd.DataFrame(
        [
            fund(1, "mid_cap", consistency=0.9, sharpe=0.8, drawdown=-0.10, fee=0.5),
            fund(2, "mid_cap", consistency=0.5, sharpe=0.5, drawdown=-0.20, fee=1.0),
            fund(3, "mid_cap", consistency=0.1, sharpe=0.2, drawdown=-0.30, fee=1.5),
        ]
    )
    scored = score_funds(metrics).set_index("scheme_code")
    assert scored.loc[1, "score"] == pytest.approx(100)
    assert scored.loc[1, "score"] > scored.loc[2, "score"] > scored.loc[3, "score"]


def test_lower_fee_and_smaller_drawdown_rank_higher():
    metrics = pd.DataFrame(
        [
            fund(1, "debt", fee=0.3, drawdown=-0.01),
            fund(2, "debt", fee=0.9, drawdown=-0.05),
        ]
    )
    scored = score_funds(metrics).set_index("scheme_code")
    assert scored.loc[1, "expense_ratio_pct"] == pytest.approx(1.0)
    assert scored.loc[2, "expense_ratio_pct"] == pytest.approx(0.5)
    assert scored.loc[1, "max_drawdown_pct"] == pytest.approx(1.0)


def test_funds_are_ranked_only_against_their_own_category():
    """A debt fund's tiny fee must not make every equity fund look expensive."""
    metrics = pd.DataFrame(
        [
            fund(1, "debt", fee=0.3),
            fund(2, "small_cap", fee=0.8),
            fund(3, "small_cap", fee=1.2),
        ]
    )
    scored = score_funds(metrics).set_index("scheme_code")
    assert scored.loc[1, "expense_ratio_pct"] == pytest.approx(1.0)  # alone in debt
    assert scored.loc[2, "expense_ratio_pct"] == pytest.approx(1.0)  # cheapest small cap


def test_score_funds_does_not_change_its_input():
    metrics = pd.DataFrame([fund(1, "gold"), fund(2, "gold")])
    columns_before = list(metrics.columns)
    score_funds(metrics)
    assert list(metrics.columns) == columns_before


# --- Shortlist --------------------------------------------------------------------


def test_shortlist_keeps_the_top_three_per_category_in_order():
    metrics = pd.DataFrame(
        [fund(code, "flexi_cap", sharpe=code / 10) for code in range(1, 6)]
        + [fund(9, "gold")]
    )
    top = shortlist(score_funds(metrics))
    flexi = top[top["category"] == "flexi_cap"]
    assert list(flexi["scheme_code"]) == [5, 4, 3]  # highest Sharpe first
    assert list(flexi["rank"]) == [1, 2, 3]
    assert list(top[top["category"] == "gold"]["scheme_code"]) == [9]  # only one gold fund


def test_shortlist_breaks_ties_with_the_lower_fee():
    """Same score, different fees can't happen with fee in the score, so force a tie."""
    scored = pd.DataFrame(
        [
            {"scheme_code": 1, "category": "gold", "score": 70.0, "expense_ratio": 0.5},
            {"scheme_code": 2, "category": "gold", "score": 70.0, "expense_ratio": 0.2},
        ]
    )
    assert list(shortlist(scored)["scheme_code"]) == [2, 1]
