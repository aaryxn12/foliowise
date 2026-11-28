import pytest

from planner.formatting import format_percent, format_rupees


@pytest.mark.parametrize(
    "amount, expected",
    [
        (4_98_93_481.23, "₹4.99 Cr"),
        (1_00_00_000, "₹1.00 Cr"),
        (30_07_260.53, "₹30.07 L"),
        (1_00_000, "₹1.00 L"),
        (99_999, "₹99,999"),
        (17_165.88, "₹17,166"),
        (500, "₹500"),
        (0, "₹0"),
    ],
)
def test_format_rupees_uses_crores_lakhs_and_commas(amount, expected):
    assert format_rupees(amount) == expected


def test_format_percent_keeps_two_decimals():
    assert format_percent(0.1055) == "10.55%"
    assert format_percent(0.0955) == "9.55%"
