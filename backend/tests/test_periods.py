from datetime import date

import pytest

from apps.analytics.periods import resolve_period


def test_default_month_uses_prague_today():
    period = resolve_period({}, date(2026, 11, 2))
    assert (period.start, period.end) == (date(2026, 11, 1), date(2026, 11, 30))


@pytest.mark.parametrize(
    "kind,anchor,start,end",
    [
        ("week", date(2026, 1, 1), date(2025, 12, 29), date(2026, 1, 4)),
        ("month", date(2024, 2, 15), date(2024, 2, 1), date(2024, 2, 29)),
        ("year", date(2024, 2, 29), date(2024, 1, 1), date(2024, 12, 31)),
        ("day", date(2026, 3, 29), date(2026, 3, 29), date(2026, 3, 29)),
        ("day", date(2026, 10, 25), date(2026, 10, 25), date(2026, 10, 25)),
    ],
)
def test_calendar_boundaries(kind, anchor, start, end):
    period = resolve_period({"period": kind, "anchor_date": anchor}, anchor)
    assert (period.start, period.end) == (start, end)
