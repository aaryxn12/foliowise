# tests/test_sip.py
import pytest

from planner.sip import (
    annual_to_monthly_rate,
    future_cost,
    future_value_lumpsum,
    lumpsum_needed,
)


def test_future_cost_house_goal():
    assert future_cost(20_00_000, 0.06, 7) == pytest.approx(30_07_261, abs=1)


def test_annual_to_monthly_rate():
    assert annual_to_monthly_rate(0.12) == pytest.approx(0.009489, abs=1e-6)


def test_future_value_lumpsum():
    assert future_value_lumpsum(5_00_000, 0.10, 7) == pytest.approx(9_74_359, abs=1)


def test_lumpsum_needed():
    assert lumpsum_needed(30_07_261, 0.10, 7) == pytest.approx(15_43_200, abs=1)
