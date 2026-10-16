"""Read-side logic shared by the API and the dashboard."""

from datetime import date, datetime, timedelta

from .models import DailyVerse, Program, SpecialVerse, day_of_year

MINUTES_PER_WEEK = 7 * 24 * 60


def verses_for(start: date, days: int):
    """`days` consecutive verses from `start`, matching the app's local fallback.

    A SpecialVerse for a date wins. Otherwise the rotation is picked by day of
    year, wrapping round if fewer than 366 verses exist.
    """
    end = start + timedelta(days=days - 1)
    specials = {s.date: s for s in SpecialVerse.objects.filter(date__range=(start, end))}
    by_day = {v.day: v for v in DailyVerse.objects.all()}
    ordered = sorted(by_day)

    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        if d in specials:
            v, special = specials[d], True
        elif by_day:
            doy = day_of_year(d)
            v = by_day.get(doy) or by_day[ordered[(doy - 1) % len(ordered)]]
            special = False
        else:
            continue
        out.append({"date": d, "reference": v.reference, "text": v.text, "special": special, "source": v})
    return out


def minute_of_week(t: datetime) -> int:
    return t.weekday() * 24 * 60 + t.hour * 60 + t.minute


def is_on_air(p: Program, t: datetime) -> bool:
    return (minute_of_week(t) - p.start_minute_of_week) % MINUTES_PER_WEEK < p.duration_minutes


def minutes_until_start(p: Program, t: datetime) -> int:
    m = (p.start_minute_of_week - minute_of_week(t)) % MINUTES_PER_WEEK
    return m or MINUTES_PER_WEEK


def now_and_next(t: datetime, programs=None):
    """(program on air at t or None, next program to start or None)."""
    programs = list(programs if programs is not None else Program.objects.filter(is_active=True))
    if not programs:
        return None, None
    on_air = next((p for p in programs if is_on_air(p, t)), None)
    upcoming = min((p for p in programs if p is not on_air), key=lambda p: minutes_until_start(p, t), default=None)
    return on_air, upcoming
