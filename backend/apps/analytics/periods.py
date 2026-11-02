from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Period:
    kind: str
    anchor: date | None
    start: date
    end: date
    group_by: str


def resolve_period(params, today):
    kind = params.get("period", "month")
    anchor = params.get("anchor_date", today)
    if kind == "custom":
        start, end = params["date_from"], params["date_to"]
        anchor = None
    elif kind == "day":
        start = end = anchor
    elif kind == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
    elif kind == "month":
        start, end = anchor.replace(day=1), anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
    else:
        start, end = date(anchor.year, 1, 1), date(anchor.year, 12, 31)
    days = (end - start).days + 1
    group = params.get("group_by", "day" if days <= 60 else "week" if days <= 366 else "month")
    return Period(kind, anchor, start, end, group)


def bucket(day, group):
    if group == "week":
        return day - timedelta(days=day.weekday())
    if group == "month":
        return day.replace(day=1)
    return day


def buckets(period):
    current = bucket(period.start, period.group_by)
    output = []
    while current <= period.end:
        output.append(current)
        if len(output) > 5000:
            raise ValueError("Graf má více než 5 000 skupin. Zvolte hrubší seskupení nebo kratší období.")
        if current == date(9999, 12, 31):
            break
        if period.group_by == "month":
            if current.year == 9999 and current.month == 12:
                break
            current = date(current.year + current.month // 12, current.month % 12 + 1, 1)
        else:
            step = 7 if period.group_by == "week" else 1
            if (date.max - current).days < step:
                break
            current += timedelta(days=step)
    return tuple(output)
