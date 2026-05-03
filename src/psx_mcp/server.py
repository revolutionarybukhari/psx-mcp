"""
psx_mcp.server — Model Context Protocol server for Pakistan Stock Exchange.

Exposes PSX market data as MCP tools, resources, and prompts so any
MCP-compatible client (Claude Desktop, Cursor, ChatGPT, custom agents)
can query PSX in natural language.

Run:
    psx-mcp                         # stdio (Claude Desktop default)
    psx-mcp --transport http        # streamable HTTP on :8000

DATA NOTICE: PSX market data is licensed for personal/non-commercial use.
This server scrapes the public PSX Data Portal (dps.psx.com.pk). Do not
redistribute or resell the data. Contact marketdatarequest@psx.com.pk
for commercial licensing.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import scraper
from . import dividend_calc

mcp = FastMCP("psx-mcp")


# ──────────────────────────── tools ────────────────────────────

@mcp.tool()
async def get_quote(symbol: str) -> dict:
    """
    Get the current price quote for a PSX-listed symbol.

    Args:
        symbol: PSX ticker, e.g. "MEBL", "OGDC", "FFC", "ENGRO".

    Returns last price, change, change %, volume, day high/low, open, prev close.
    Data is delayed by 5 minutes per PSX Data Portal.
    """
    q = await scraper.fetch_quote(symbol)
    if not q:
        return {"error": f"Symbol {symbol!r} not found on PSX."}
    return {
        "symbol": q.symbol,
        "name": q.name,
        "last": q.last,
        "change": q.change,
        "change_pct": q.change_pct,
        "volume": q.volume,
        "high": q.high,
        "low": q.low,
        "open": q.open,
        "prev_close": q.prev_close,
        "timestamp_utc": q.timestamp,
        "note": "Data delayed ~5 min per PSX Data Portal.",
    }


@mcp.tool()
async def get_upcoming_dividends(symbol: Optional[str] = None) -> list[dict]:
    """
    List upcoming dividend payouts on PSX.

    Args:
        symbol: Optional PSX ticker to filter. If omitted, returns all upcoming
                payouts in the table.

    Each result includes book closure dates, AGM date, payout amount/type, and
    the computed buy deadline (T+2 settlement) — the last day you can buy and
    still be entitled to the dividend.
    """
    payouts = await scraper.fetch_payouts()
    if symbol:
        sym = symbol.upper()
        payouts = [p for p in payouts if p.symbol.upper() == sym]

    out = []
    for p in payouts:
        status = dividend_calc.classify_dividend(p.bc_from)
        out.append({
            "symbol": p.symbol,
            "company": p.company,
            "type": p.type,
            "payout": p.payout,
            "book_closure_from": p.bc_from,
            "book_closure_to": p.bc_to,
            "agm_date": p.agm_date,
            "agm_time": p.agm_time,
            "buy_deadline": status.get("buy_deadline"),
            "days_to_buy_deadline": status.get("days_to_buy_deadline"),
            "status": status.get("status"),
            "guidance": status.get("message"),
        })
    return out


@mcp.tool()
async def get_buy_deadline(symbol: str) -> dict:
    """
    For a symbol with an upcoming dividend, return the last day you can buy
    and still be entitled to the dividend (T+2 settlement applied).

    Returns 'no upcoming dividend' if the symbol isn't currently in the
    PSX payouts table.
    """
    sym = symbol.upper()
    payouts = await scraper.fetch_payouts()
    matches = [p for p in payouts if p.symbol.upper() == sym]
    if not matches:
        return {
            "symbol": sym,
            "status": "NO_UPCOMING_DIVIDEND",
            "message": f"{sym} has no upcoming dividend in the PSX payouts table.",
        }
    p = matches[0]
    status = dividend_calc.classify_dividend(p.bc_from)
    return {
        "symbol": p.symbol,
        "company": p.company,
        "payout": p.payout,
        "type": p.type,
        "book_closure_from": p.bc_from,
        **status,
    }


@mcp.tool()
async def get_dividend_history(symbol: str, years: int = 5) -> list[dict]:
    """
    Get historical dividend payouts for a symbol.

    Args:
        symbol: PSX ticker.
        years: How many years of history to return (default 5).
    """
    history = await scraper.fetch_dividend_history(symbol, years=years)
    return [
        {
            "symbol": d.symbol,
            "type": d.type,
            "payout": d.payout,
            "book_closure_from": d.bc_from,
            "book_closure_to": d.bc_to,
        }
        for d in history
    ]


@mcp.tool()
async def get_announcements(symbol: Optional[str] = None, limit: int = 20) -> list[dict]:
    """
    Get recent corporate announcements from PSX.

    Args:
        symbol: Optional ticker filter (e.g. only OGDC announcements).
        limit:  Max rows to return (default 20, cap 100).

    Each item includes date, symbol, title, and a PDF link to the original notice.
    """
    limit = max(1, min(int(limit), 100))
    items = await scraper.fetch_announcements(symbol=symbol, limit=limit)
    return [
        {
            "date": a.date,
            "symbol": a.symbol,
            "title": a.title,
            "pdf_url": a.pdf_url,
        }
        for a in items
    ]


@mcp.tool()
async def search_symbols(query: str, limit: int = 10) -> list[dict]:
    """
    Fuzzy search PSX symbols and company names.

    Useful when the user names a company casually
    ("habib bank" -> "HBL", "fauji fertilizer" -> "FFC").
    """
    matches = await scraper.search_symbols(query, limit=limit)
    return [{"symbol": s, "name": n} for s, n in matches]


@mcp.tool()
async def get_indices() -> list[dict]:
    """
    Get current values for major PSX indices: KSE100, KSE30, ALLSHR, KMI30,
    KMIALLSHR, PSXDIV20, BKTI, OGTI, MII30.
    """
    idx = await scraper.fetch_indices()
    return [
        {
            "name": i.name,
            "value": i.value,
            "change": i.change,
            "change_pct": i.change_pct,
        }
        for i in idx
    ]


@mcp.tool()
def get_market_status() -> dict:
    """
    Is PSX open right now? Returns OPEN / PRE_OPEN / CLOSED_TODAY / WEEKEND
    plus the next market open in PKT.
    """
    return scraper.market_status()


@mcp.tool()
async def screen_dividend_stocks(min_payout_pct: float = 0.0, limit: int = 25) -> list[dict]:
    """
    Screen the upcoming-payouts table by payout size.

    Args:
        min_payout_pct: Minimum payout % to include (e.g. 50 = 50% of par).
                        PSX payouts are quoted as % of face value (typically Rs 10).
        limit: Max results.

    NOTE: This is a payout-size filter, not a true dividend-yield screen
    (yield = dividend / current price). For real yield you'd cross-reference
    each symbol's current price — call get_quote() per symbol if needed.
    """
    payouts = await scraper.fetch_payouts()
    filtered = []
    for p in payouts:
        # Try to extract a numeric % from the payout string
        import re
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", p.payout)
        if not m:
            continue
        pct = float(m.group(1))
        if pct < min_payout_pct:
            continue
        status = dividend_calc.classify_dividend(p.bc_from)
        filtered.append({
            "symbol": p.symbol,
            "company": p.company,
            "payout": p.payout,
            "payout_pct": pct,
            "type": p.type,
            "book_closure_from": p.bc_from,
            "buy_deadline": status.get("buy_deadline"),
            "status": status.get("status"),
        })

    filtered.sort(key=lambda x: -x["payout_pct"])
    return filtered[:limit]


# ──────────────────────────── resources ────────────────────────────

@mcp.resource("psx://market-status")
def resource_market_status() -> str:
    """Current PSX trading status as JSON."""
    return json.dumps(scraper.market_status(), indent=2)


@mcp.resource("psx://indices")
async def resource_indices() -> str:
    """Snapshot of all major PSX indices as JSON."""
    idx = await scraper.fetch_indices()
    payload = [
        {"name": i.name, "value": i.value, "change": i.change, "change_pct": i.change_pct}
        for i in idx
    ]
    return json.dumps(payload, indent=2)


@mcp.resource("psx://upcoming-dividends")
async def resource_upcoming_dividends() -> str:
    """All upcoming dividends with computed buy deadlines, as JSON."""
    payouts = await scraper.fetch_payouts()
    out = []
    for p in payouts:
        status = dividend_calc.classify_dividend(p.bc_from)
        out.append({
            "symbol": p.symbol,
            "company": p.company,
            "payout": p.payout,
            "type": p.type,
            "bc_from": p.bc_from,
            "buy_deadline": status.get("buy_deadline"),
            "status": status.get("status"),
        })
    return json.dumps(out, indent=2)


# ──────────────────────────── prompts ────────────────────────────

@mcp.prompt()
def analyze_dividend_play(symbol: str) -> str:
    """
    Generate a thorough analysis prompt for a potential dividend-capture trade
    on the given PSX symbol. The LLM will call get_quote, get_upcoming_dividends,
    get_dividend_history, and get_announcements to gather data.
    """
    sym = symbol.upper()
    return (
        f"I'm considering a dividend trade on {sym} on the Pakistan Stock Exchange. "
        f"Use the available PSX tools to:\n"
        f"1. Pull {sym}'s current quote (get_quote).\n"
        f"2. Pull {sym}'s upcoming dividend and buy deadline (get_buy_deadline).\n"
        f"3. Pull {sym}'s dividend history for the last 3 years (get_dividend_history).\n"
        f"4. Pull recent announcements for {sym} (get_announcements).\n\n"
        f"Then give me an honest assessment that covers:\n"
        f"- Whether the buy deadline is still reachable\n"
        f"- The dividend yield at the current price (dividend / price)\n"
        f"- Whether the company has a consistent payout history\n"
        f"- Any recent announcements that could affect price around ex-date\n"
        f"- The expected ex-dividend price drop (typically ≈ dividend amount)\n"
        f"- Tax friction: 15% WHT for filers, 30% for non-filers\n"
        f"- Whether the trade has a positive expected value vs friction, "
        f"or whether I should only take it if I want to hold {sym} anyway\n\n"
        f"Be direct. If the math doesn't work, say so."
    )


@mcp.prompt()
def portfolio_review(symbols: str) -> str:
    """
    Review a comma-separated list of PSX holdings. The LLM will pull current
    prices, upcoming dividends, and recent news for each.
    """
    return (
        f"Review my PSX portfolio: {symbols}.\n\n"
        f"For each symbol use the PSX tools to fetch:\n"
        f"- Current price and day change (get_quote)\n"
        f"- Any upcoming dividend / buy deadline (get_buy_deadline)\n"
        f"- 3 most recent corporate announcements (get_announcements)\n\n"
        f"Then summarise:\n"
        f"- Names with imminent buy deadlines I should act on\n"
        f"- Names with material announcements worth reading\n"
        f"- Concentration risks (sectors, single names)\n"
        f"- Anything I should investigate further before today's close\n\n"
        f"Also pull the major indices (get_indices) so I have market context."
    )


@mcp.prompt()
def find_dividend_opportunities(min_payout_pct: float = 50.0) -> str:
    """Find dividend trades worth investigating right now."""
    return (
        f"Use screen_dividend_stocks(min_payout_pct={min_payout_pct}) to find PSX "
        f"stocks with sizable upcoming dividends. Then for the top 5, pull "
        f"get_quote and get_dividend_history to compute realistic yield and "
        f"check payout consistency.\n\n"
        f"Rank the opportunities by:\n"
        f"1. Whether the buy deadline is still actionable\n"
        f"2. Yield at current price (after estimated 15% WHT)\n"
        f"3. 3-year payout consistency\n\n"
        f"Be skeptical — flag any stocks where the high payout looks like a "
        f"one-off or a return-of-capital situation rather than sustainable income."
    )


# ──────────────────────────── entrypoint ────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PSX MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="MCP transport. stdio for Claude Desktop (default); "
             "http for streamable HTTP; sse for legacy SSE.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host (http/sse only)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (http/sse only)")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:  # sse
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
