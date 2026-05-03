"""
dividend_calc.py — Buy-deadline math for PSX dividends.

PSX settles T+2. To be on the share register for a dividend, a trade must
execute at least 2 trading days before book closure begins.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

# 2026 PSX trading holidays — verify against the official PSX calendar before relying.
# Edit this list as PSX publishes the annual calendar.
PSX_HOLIDAYS_2026: set[str] = {
    # 'YYYY-MM-DD'
    # '2026-02-05',  # Kashmir Day
    # '2026-03-23',  # Pakistan Day
    # '2026-05-01',  # Labour Day
    # '2026-08-14',  # Independence Day
    # '2026-12-25',  # Quaid Day / Christmas
}


def parse_psx_date(s: str) -> Optional[date]:
    """Be lenient — PSX renders dates in several formats."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%b %d, %Y", "%d-%b-%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:  # Sat/Sun
        return False
    if d.isoformat() in PSX_HOLIDAYS_2026:
        return False
    return True


def subtract_trading_days(d: date, n: int) -> date:
    """Step back n trading days, skipping weekends + holidays."""
    cur = d
    removed = 0
    while removed < n:
        cur = cur - timedelta(days=1)
        if is_trading_day(cur):
            removed += 1
    return cur


def buy_deadline(bc_from: date, settlement_days: int = 2) -> date:
    """
    Last day to BUY to be entitled to the dividend.
    Trade executed on this date settles into the register before book closure.
    """
    return subtract_trading_days(bc_from, settlement_days)


def days_until(target: date) -> int:
    """Calendar days from today (PKT) to target."""
    return (target - date.today()).days


def classify_dividend(bc_from_str: str, settlement_days: int = 2) -> dict:
    """Return a structured status object for an upcoming dividend."""
    bc_from = parse_psx_date(bc_from_str)
    if not bc_from:
        return {"status": "UNKNOWN", "reason": f"Could not parse date: {bc_from_str!r}"}

    deadline = buy_deadline(bc_from, settlement_days)
    days_to_deadline = days_until(deadline)
    days_to_bc = days_until(bc_from)

    if days_to_deadline < 0:
        status = "PASSED"
        message = f"Buy deadline was {abs(days_to_deadline)} day(s) ago. Cannot collect this dividend."
    elif days_to_deadline == 0:
        status = "URGENT_TODAY"
        message = "Buy deadline is TODAY. Trade must execute before market close."
    elif days_to_deadline == 1:
        status = "URGENT_TOMORROW"
        message = "Buy deadline is tomorrow."
    elif days_to_deadline <= 5:
        status = "APPROACHING"
        message = f"Buy deadline in {days_to_deadline} day(s)."
    else:
        status = "UPCOMING"
        message = f"Buy deadline in {days_to_deadline} day(s)."

    return {
        "status": status,
        "message": message,
        "bc_from": bc_from.isoformat(),
        "buy_deadline": deadline.isoformat(),
        "days_to_buy_deadline": days_to_deadline,
        "days_to_bc_from": days_to_bc,
        "settlement_days": settlement_days,
    }
