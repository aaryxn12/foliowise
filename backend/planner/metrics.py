"""Fund metrics from NAV history: drawdown, returns, volatility, Sharpe, consistency."""

import math

import pandas as pd

# Return on a safe investment (roughly government bonds); an assumption.
RISK_FREE_RATE = 0.065

# A category median for a date needs at least this many funds, or one or two
# funds would decide what "typical" means.
MIN_FUNDS_FOR_MEDIAN = 5

MONTHS_PER_YEAR = 12


def nav_series_from_mfapi(payload: dict) -> pd.Series:
    """NAVs from an mfapi response, as floats indexed by date, oldest first."""
    rows = payload["data"]  # each row looks like {"date": "21-11-2026", "nav": "89.36"}
    navs = [float(row["nav"]) for row in rows]
    dates = pd.to_datetime([row["date"] for row in rows], format="%d-%m-%Y")
    return pd.Series(navs, index=dates).sort_index()  # mfapi lists newest first


def month_end_navs(daily: pd.Series) -> pd.Series:
    """The last NAV of each month."""
    return daily.resample("ME").last().dropna()


def max_drawdown(navs: pd.Series) -> float:
    """Worst fall from a previous peak, e.g. -0.50 for a 50% fall."""
    return float((navs / navs.cummax() - 1).min())


def cagr(navs: pd.Series) -> float:
    """Compound annual growth rate between the first and last NAV."""
    years = (navs.index[-1] - navs.index[0]).days / 365.25
    growth = navs.iloc[-1] / navs.iloc[0]
    return float(growth ** (1 / years) - 1)


def annualised_volatility(navs: pd.Series) -> float:
    """Standard deviation of monthly returns, scaled to a year."""
    monthly_returns = navs.pct_change().dropna()  # first month has no previous NAV
    return float(monthly_returns.std() * math.sqrt(MONTHS_PER_YEAR))


def sharpe_ratio(
    annual_return: float, volatility: float, risk_free: float = RISK_FREE_RATE
) -> float:
    """Return above the risk-free rate per unit of volatility."""
    if volatility == 0:
        return math.nan
    return (annual_return - risk_free) / volatility


def rolling_returns(navs: pd.Series, years: int = 5) -> pd.Series:
    """CAGR of every `years`-long window, indexed by each window's end date.

    Expects month-end NAVs (see month_end_navs), so `years` years = `years * 12` rows.
    """
    window = years * MONTHS_PER_YEAR
    growth = navs / navs.shift(
        window
    )  # each NAV divided by the NAV `window` months earlier
    return (
        growth ** (1 / years) - 1
    ).dropna()  # the first `window` rows have no start NAV


def consistency(fund_rolling: pd.Series, median_rolling: pd.Series) -> float:
    """Share of windows in which the fund beat its category median.

    Only dates present in both series are compared; a tie does not count as a win.
    """
    fund, median = fund_rolling.align(median_rolling, join="inner")
    if fund.empty:
        return math.nan  # no overlapping windows, so nothing to compare
    return float((fund > median).mean())


def trailing_years(navs: pd.Series, years: int) -> pd.Series:
    """The last `years` years of NAVs, counted back from the latest date."""
    start = navs.index[-1] - pd.DateOffset(years=years)
    return navs[navs.index >= start]


def category_median(
    rolling_by_fund: dict[int, pd.Series], min_funds: int = MIN_FUNDS_FOR_MEDIAN
) -> pd.Series:
    """Median rolling return across a category's funds, for each window end date.

    Dates where fewer than `min_funds` funds have a window are dropped.
    """
    frame = pd.DataFrame(rolling_by_fund)  # one column per fund, one row per date
    medians = frame.median(axis=1)  # typical fund in each row; NaN cells are skipped
    enough_funds = frame.count(axis=1) >= min_funds  # True/False per row
    return medians[enough_funds]
