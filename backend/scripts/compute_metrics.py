"""Compute fund metrics for every fund in the universe.

Reads data/fund_universe.csv and the NAV files in data/nav/ (both written by
fetch_funds.py) and writes one row of metrics per fund.

Two passes, because consistency needs the whole category:
1. Rolling 5-year returns for every fund, then each category's median per date.
2. Each fund's metrics, including consistency against its category median.

Return, volatility, Sharpe and drawdown use the same trailing 5 years for every
fund, so a fund with 12 years of history is not compared with one that has 6.
Consistency uses every 5-year window each fund has.

Run from the backend folder (as a module, so `planner` can be imported):
    python -m scripts.compute_metrics

Writes:
    data/fund_metrics.csv
"""

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd

from planner.metrics import (
    annualised_volatility,
    cagr,
    category_median,
    consistency,
    max_drawdown,
    month_end_navs,
    nav_series_from_mfapi,
    rolling_returns,
    sharpe_ratio,
    trailing_years,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NAV_DIR = DATA_DIR / "nav"
UNIVERSE_FILE = DATA_DIR / "fund_universe.csv"
METRICS_FILE = DATA_DIR / "fund_metrics.csv"

WINDOW_YEARS = 5  # rolling-return window, and the trailing period for the other metrics


def load_universe() -> list[dict]:
    """The funds chosen by fetch_funds.py, one dict per CSV row."""
    with UNIVERSE_FILE.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_monthly_navs(scheme_code: str) -> pd.Series:
    """Month-end NAVs for one fund, from its saved mfapi file."""
    payload = json.loads((NAV_DIR / f"{scheme_code}.json").read_text(encoding="utf-8"))
    return month_end_navs(nav_series_from_mfapi(payload))


def fund_metrics(navs: pd.Series, median_rolling: pd.Series) -> dict:
    """Every metric for one fund, rounded for the CSV."""
    recent = trailing_years(navs, WINDOW_YEARS)
    annual_return = cagr(recent)
    volatility = annualised_volatility(recent)
    fund_rolling = rolling_returns(navs, WINDOW_YEARS)
    shared_windows = fund_rolling.index.intersection(median_rolling.index)
    return {
        "cagr_5y": round(annual_return, 4),
        "volatility_5y": round(volatility, 4),
        "sharpe_5y": round(sharpe_ratio(annual_return, volatility), 3),
        "max_drawdown_5y": round(max_drawdown(recent), 4),
        "consistency": round(consistency(fund_rolling, median_rolling), 3),
        "windows_compared": len(shared_windows),
    }


def main() -> None:
    funds = load_universe()
    navs_by_code = {fund["scheme_code"]: load_monthly_navs(fund["scheme_code"]) for fund in funds}

    # Pass 1: each category's median rolling return, per window end date.
    medians = {}
    for category in sorted({fund["category"] for fund in funds}):
        rolling_by_fund = {
            fund["scheme_code"]: rolling_returns(navs_by_code[fund["scheme_code"]], WINDOW_YEARS)
            for fund in funds
            if fund["category"] == category
        }
        medians[category] = category_median(rolling_by_fund)

    # Pass 2: every fund's metrics.
    today = date.today().isoformat()
    rows = []
    for fund in funds:
        navs = navs_by_code[fund["scheme_code"]]
        rows.append(
            {
                "scheme_code": fund["scheme_code"],
                "scheme_name": fund["scheme_name"],
                "category": fund["category"],
                **fund_metrics(navs, medians[fund["category"]]),
                "nav_as_of": fund["latest_nav_date"],
                "computed_on": today,
            }
        )

    with METRICS_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} funds to {METRICS_FILE.relative_to(DATA_DIR.parent)}")
    for category, median in medians.items():
        if median.empty:
            print(f"  {category}: no category median (too few funds with 5-year windows)")
        else:
            print(
                f"  {category}: median from {median.index[0]:%b %Y} to "
                f"{median.index[-1]:%b %Y} ({len(median)} windows)"
            )


if __name__ == "__main__":
    main()
