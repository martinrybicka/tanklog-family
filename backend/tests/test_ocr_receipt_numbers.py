import pytest

from apps.extensions.ocr import parse_tsv


def tsv(*lines):
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tconf\ttext\n"
    return header + "".join(f"5\t1\t1\t1\t{i}\t92\t{line}\n" for i, line in enumerate(lines, 1))


def test_fuel_grade_unit_misread_and_grouped_payment_total():
    _, result = parse_tsv(
        tsv(
            "Položka Množství Cena za l Celkem",
            "Benzín NATURAL 95 42,371. 36,90 Kč 1563,45Kč",
            "Celkem k úhradě: 1 563,45 Kč",
            "Sazba DPH Základ daně DPH Celkem",
            "21 % 1 292,11 Kč 271,34 Kč 1 563,45 Kč",
        )
    )
    assert result["liters"]["value"] == "42.37"
    assert float(result["liters"]["confidence"]) <= 50
    assert result["total_amount"]["value"] == "1563.45"
    assert result["unit_price_entered"]["value"] == "36.90"


@pytest.mark.parametrize("space", [" ", "\u00a0", "\u202f"])
def test_payment_total_with_thousands_grouping(space):
    _, result = parse_tsv(tsv(f"Celkem k úhradě: 1{space}563,45 Kč"))
    assert result["total_amount"]["value"] == "1563.45"


@pytest.mark.parametrize(
    "line",
    [
        "Benzín NATURAL 95 42,37 l 36,90 Kč 1 563,45 Kč",
        "Nafta Diesel 42,37 L 36,90 Kč 1563,45 Kč",
        "Nafta 42,37 litru 36,90 Kč 1563,45 Kč",
    ],
)
def test_fuel_row_quantity_is_not_grade_or_price(line):
    _, result = parse_tsv(tsv(line, "CELKEM 1563,45 Kč"))
    assert result["liters"]["value"] == "42.37"
    assert result["unit_price_entered"]["value"] == "36.90"


def test_ambiguous_digit_as_unit_requires_consistent_row_arithmetic():
    _, result = parse_tsv(tsv("Benzín NATURAL 95 42,371. 36,90 Kč 999,00 Kč"))
    assert "liters" not in result
    assert "unit_price_entered" not in result


def test_multiple_fuels_and_conflicting_totals_are_not_guessed():
    _, result = parse_tsv(
        tsv(
            "Natural 95 10,00 l 36,90 Kč 369,00 Kč",
            "Diesel 20,00 l 36,90 Kč 738,00 Kč",
            "CELKEM 369,00 Kč",
            "CELKEM 738,00 Kč",
        )
    )
    assert "liters" not in result
    assert "total_amount" not in result


def test_malformed_grouping_and_tax_values_do_not_become_total():
    _, result = parse_tsv(tsv("Celkem 12 34,56 Kč", "DPH 271,34 Kč", "Základ daně 1292,11 Kč"))
    assert "total_amount" not in result


@pytest.mark.parametrize("quantity", ["-10,00", "+10,00", "0,00"])
def test_invalid_or_signed_quantities_are_not_positive_suggestions(quantity):
    _, result = parse_tsv(tsv(f"Natural 95 {quantity} l 36,90 Kč 369,00 Kč"))
    assert "liters" not in result


@pytest.mark.parametrize(
    "line,expected",
    [
        ("Benzín NATURAL 95 42,37 l 36,90 Kč 1563,45 Kč", "PETROL"),
        ("Nafta Diesel 42,37 l 36,90 Kč 1563,45 Kč", "DIESEL"),
        ("LPG 42,37 l 36,90 Kč 1563,45 Kč", "LPG"),
        ("Palivo: Ethanol E85", "ETHANOL"),
    ],
)
def test_fuel_type_from_purchase_or_explicit_label(line, expected):
    _, fields = parse_tsv(tsv(line))
    assert fields["fuel_type"]["value"] == expected


def test_unknown_station_merchant_name_and_other_code():
    _, fields = parse_tsv(
        tsv(
            "3 | PetrolFlex s.r.o. =",
            "Čerpací stanice: Praha 5 - Jinonice",
            "Benzín NATURAL 95 42,37 l 36,90 Kč 1563,45 Kč",
        )
    )
    assert fields["station_custom_name"]["value"] == "PetrolFlex"
    assert fields["station_code"]["value"] == "OTHER"


def test_known_station_does_not_get_incompatible_custom_name():
    _, fields = parse_tsv(tsv("SHELL", "Provozovatel: Ukázková firma s.r.o.", "Nafta Diesel 10,00 l"))
    assert fields["station_code"]["value"] == "SHELL"
    assert "station_custom_name" not in fields


def test_promotional_fuels_and_conflicting_station_names_are_not_guessed():
    _, fields = parse_tsv(tsv("Nabízíme benzín, diesel a LPG", "První firma s.r.o.", "Druhá firma a.s."))
    assert "fuel_type" not in fields
    assert "station_code" not in fields
    assert "station_custom_name" not in fields


def test_linux_font_vertical_bar_is_liter_unit_not_missing_quantity():
    _, result = parse_tsv(tsv("MNOŽSTVÍ 10,500 |", "CENA/L 40,0000", "CELKEM 420,00"))
    assert result["liters"]["value"] == "10.500"
    assert float(result["liters"]["confidence"]) <= 50
    assert result["total_amount"]["value"] == "420.00"


def test_vertical_bar_unit_in_fuel_row_has_reduced_confidence():
    _, result = parse_tsv(tsv("Natural 95 10,500 | 40,00 Kč 420,00 Kč"))
    assert result["liters"]["value"] == "10.500"
    assert float(result["liters"]["confidence"]) <= 50
