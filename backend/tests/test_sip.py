# tests/test_sip.py
import pytest

from planner.sip import annual_to_monthly_rate, future_cost


def test_future_cost_house_goal():
    assert future_cost(20_00_000, 0.06, 7) == pytest.approx(30_07_261, abs=1)


def test_annual_to_monthly_rate():
    assert annual_to_monthly_rate(0.12) == pytest.approx(0.009489, abs=1e-6)
