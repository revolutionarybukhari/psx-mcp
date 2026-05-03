"""Smoke tests — exercise the parts that don't need network."""
from __future__ import annotations

from psx_mcp import dividend_calc, scraper
from psx_mcp.server import mcp


async def test_tools_registered():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "get_quote",
        "get_upcoming_dividends",
        "get_buy_deadline",
        "get_dividend_history",
        "get_announcements",
        "search_symbols",
        "get_indices",
        "get_market_status",
        "screen_dividend_stocks",
    }
    assert expected <= names, f"missing: {expected - names}"


async def test_resources_registered():
    resources = await mcp.list_resources()
    uris = {str(r.uri) for r in resources}
    assert {
        "psx://market-status",
        "psx://indices",
        "psx://upcoming-dividends",
    } <= uris


async def test_prompts_registered():
    prompts = await mcp.list_prompts()
    names = {p.name for p in prompts}
    assert {
        "analyze_dividend_play",
        "portfolio_review",
        "find_dividend_opportunities",
    } <= names


def test_market_status_shape():
    s = scraper.market_status()
    assert s["status"] in {"OPEN", "PRE_OPEN", "CLOSED_TODAY", "WEEKEND"}
    assert "now_pkt" in s
    assert "next_open" in s


def test_buy_deadline_skips_weekend():
    # BC From = Monday → buy deadline must be the previous Thursday (skip Sat/Sun)
    from datetime import date

    # 2026-06-08 is a Monday
    bc_from = date(2026, 6, 8)
    deadline = dividend_calc.buy_deadline(bc_from, settlement_days=2)
    assert deadline == date(2026, 6, 4)  # Thursday — skipped Sat 6th, Sun 7th, T-2 from Mon 8th


def test_classify_dividend_unknown_date():
    out = dividend_calc.classify_dividend("not-a-date")
    assert out["status"] == "UNKNOWN"


def test_classify_dividend_passed():
    # A clearly past date
    out = dividend_calc.classify_dividend("2020-01-15")
    assert out["status"] == "PASSED"
