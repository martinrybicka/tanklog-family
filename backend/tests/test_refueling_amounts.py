from decimal import Decimal

import pytest

from apps.refuelings.amounts import resolve_amount


def test_half_up_and_source():
    assert resolve_amount({"liters": Decimal("1.005"), "unit_price_entered": Decimal("1")}) == (
        Decimal("1.01"),
        "CALCULATED",
    )


def test_entered_receipt_discount_wins():
    assert resolve_amount(
        {
            "liters": Decimal("42.350"),
            "unit_price_entered": Decimal("38.9"),
            "total_amount": Decimal("1600.00"),
        }
    ) == (Decimal("1600.00"), "ENTERED")


def test_only_total_and_explicit_zero():
    assert resolve_amount({"liters": Decimal("10"), "total_amount": Decimal("0")}) == (
        Decimal("0"),
        "ENTERED",
    )


def test_no_silent_zero_from_unit_price():
    with pytest.raises(Exception, match="nul"):
        resolve_amount({"liters": Decimal("10"), "unit_price_entered": Decimal("0")})


def test_patch_preserves_entered_total_but_recalculates_calculated():
    old = {"total_amount": Decimal("99.00"), "amount_source": "ENTERED"}
    assert resolve_amount({"liters": Decimal("4"), "unit_price_entered": Decimal("30")}, old) == (
        Decimal("99.00"),
        "ENTERED",
    )
    old["amount_source"] = "CALCULATED"
    assert resolve_amount({"liters": Decimal("4"), "unit_price_entered": Decimal("30")}, old) == (
        Decimal("120.00"),
        "CALCULATED",
    )
