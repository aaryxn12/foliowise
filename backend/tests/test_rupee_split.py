import pytest

from planner.rupee_split import STEP, round_up_to_step, split_amount

# Priya's retirement goal (moderate, 20 years): 70% equity split 40/30/20/10,
# 25% debt, 5% gold.
PRIYA_SHARES = {
    "large_cap_index": 0.28,
    "flexi_cap": 0.21,
    "mid_cap": 0.14,
    "small_cap": 0.07,
    "debt": 0.25,
    "gold": 0.05,
}


# --- Rounding the total ---------------------------------------------------------


@pytest.mark.parametrize(
    "amount, expected",
    [(24_863, 25_000), (25_000, 25_000), (25_000.01, 25_500), (1, 500)],
)
def test_round_up_to_step(amount, expected):
    assert round_up_to_step(amount) == expected


def test_round_up_returns_a_whole_number_of_rupees():
    assert isinstance(round_up_to_step(24_863.57), int)


# --- Splitting ------------------------------------------------------------------


def test_priya_split_uses_largest_remainders():
    """Rounded down: 24,000. The 2 leftover steps go to the four that lost 250 each,
    larger share first: debt (25%) and flexi (21%)."""
    assert split_amount(25_000, PRIYA_SHARES) == {
        "large_cap_index": 7_000,
        "flexi_cap": 5_500,
        "mid_cap": 3_500,
        "small_cap": 1_500,
        "debt": 6_500,
        "gold": 1_000,
    }


@pytest.mark.parametrize("total", [3_000, 7_777, 12_345, 24_863, 50_000, 1_00_000])
def test_split_adds_up_exactly_in_whole_steps(total):
    amounts = split_amount(total, PRIYA_SHARES)
    assert sum(amounts.values()) == round_up_to_step(total)
    assert all(amount % STEP == 0 and amount >= STEP for amount in amounts.values())


def test_small_sip_drops_tiny_categories():
    """Rs2,000: flexi 420, mid 280, small 140 and gold 100 are under Rs500, so dropped.
    Large (28%) and debt (25%) share it all: 1,056 and 944, rounded to 1,000 each."""
    assert split_amount(2_000, PRIYA_SHARES) == {
        "large_cap_index": 1_000,
        "debt": 1_000,
    }


def test_tiny_sip_goes_entirely_to_the_biggest_share():
    assert split_amount(500, PRIYA_SHARES) == {"large_cap_index": 500}


def test_zero_share_categories_are_left_out():
    shares = {"large_cap_index": 0.6, "small_cap": 0.0, "debt": 0.4}
    assert split_amount(10_000, shares) == {"large_cap_index": 6_000, "debt": 4_000}


def test_shares_must_add_up_to_one():
    with pytest.raises(ValueError):
        split_amount(10_000, {"large_cap_index": 0.6, "debt": 0.3})
