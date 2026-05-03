# psx-mcp

**Talk to the Pakistan Stock Exchange in plain English.**

`psx-mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server that exposes PSX market data — quotes, dividends, announcements, indices — as tools any MCP-compatible AI client can call. Connect it to Claude Desktop, Cursor, ChatGPT, or your own agent, and ask questions like:

> "What are the upcoming dividends on PSX with payouts above 100%?"
>
> "Should I buy MEBL today to collect the dividend?"
>
> "Pull recent announcements for OGDC and summarize anything material."
>
> "How has FFC's dividend history looked over the past 5 years?"

The LLM picks the right tools automatically and answers in your language.

## Why MCP?

Existing PSX tools are libraries — you import them, write code, get data. MCP servers are tools an LLM calls *for you*. You ask in English, the model invokes `get_quote`, `get_upcoming_dividends`, `get_dividend_history`, and synthesizes an answer. No Python required for the end user.

This is also the first PSX MCP server published. If you're building agents, financial copilots, or AI-augmented research workflows for Pakistani markets, this gives them eyes.

## What's exposed

### Tools (LLM-callable)

| Tool | What it does |
|---|---|
| `get_quote(symbol)` | Current price snapshot for a symbol |
| `get_upcoming_dividends(symbol?)` | Payouts table, optionally filtered, with computed buy deadlines |
| `get_buy_deadline(symbol)` | Last day to buy and still collect the dividend (T+2 settlement) |
| `get_dividend_history(symbol, years)` | Historical payouts |
| `get_announcements(symbol?, limit)` | Recent corporate filings + PDF links |
| `search_symbols(query)` | Fuzzy match company names → tickers |
| `get_indices()` | KSE100, KSE30, KMI30, ALLSHR, PSXDIV20, etc. |
| `get_market_status()` | Is PSX open right now? When does it open next? |
| `screen_dividend_stocks(min_payout_pct)` | Filter upcoming dividends by payout size |

### Resources (read-only context)

- `psx://market-status`
- `psx://indices`
- `psx://upcoming-dividends`

### Prompts (templated workflows)

- `analyze_dividend_play(symbol)` — full dividend-trade analysis
- `portfolio_review(symbols)` — review a holdings list
- `find_dividend_opportunities(min_payout_pct)` — screener + per-name analysis

## Install

Requires Python 3.10+.

```bash
# From PyPI (once published)
pip install psx-mcp

# Or with uv (recommended)
uv tool install psx-mcp

# From source
git clone https://github.com/revolutionarybukhari/psx-mcp
cd psx-mcp
pip install -e .
```

## Connect to Claude Desktop

Edit your Claude Desktop config:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "psx": {
      "command": "uvx",
      "args": ["psx-mcp"]
    }
  }
}
```

Restart Claude Desktop. You should see the PSX tools listed in the connection icon. Try:

> "What dividends are coming up this week on PSX?"

## Connect to Cursor

Settings → MCP → add server:

```json
{
  "mcpServers": {
    "psx": {
      "command": "psx-mcp",
      "args": []
    }
  }
}
```

## Run as remote HTTP server

For shared/team use or hosted agents:

```bash
psx-mcp --transport http --host 0.0.0.0 --port 8000
```

The server is then reachable at `http://localhost:8000/mcp`. Test it with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector
# point it at http://localhost:8000/mcp
```

## Example prompts to try

Once connected:

```
"List all PSX stocks paying more than 50% dividend right now,
sorted by buy deadline."

"For each stock in my portfolio (HBL, OGDC, PSO, ENGRO, MEBL),
tell me if there's an upcoming dividend and what the buy deadline is."

"Find me consistent dividend payers on PSX — companies that have
paid every year for the last 3+ years with payouts above 30%."

"What's happening with FFC today? Pull the quote and the latest
3 announcements."

"Walk me through the dividend trade for MARI step by step."
```

## How it works

```
   ┌──────────────────────┐         ┌─────────────────┐
   │  Claude / Cursor /   │  MCP    │   psx-mcp       │
   │  ChatGPT / Agent     │ ──────► │   server        │
   └──────────────────────┘         └────────┬────────┘
                                             │ httpx + bs4
                                             ▼
                                    ┌─────────────────┐
                                    │ dps.psx.com.pk  │
                                    └─────────────────┘
```

Tools call the public PSX Data Portal, parse HTML with BeautifulSoup, normalize into structured JSON, and return to the LLM. No keys, no auth, no scraping headaches for the consumer.

## Architecture notes

- **Async everywhere.** All scraper functions use `httpx.AsyncClient` so MCP calls don't block.
- **Symbol cache.** The full PSX symbol list is cached for 24h to make `search_symbols` fast.
- **Trading-day math.** Buy-deadline calculation uses `BC_From − 2 trading days`, skipping weekends and configurable holidays in `dividend_calc.PSX_HOLIDAYS_2026`.
- **No persistence.** This server is stateless. State (alerts, watchlists) belongs in your client.

## Pairs well with

This is one server in a wider PSX open-source toolkit:

- [`psx-dividend-alert`](../psx-dividend-alert) — proactive Telegram alerts for upcoming dividends
- `psx-cgt-calculator` — Pakistan capital-gains-tax with FIFO lots
- `psx-zakat-calculator` — zakat on stock holdings (zakatable assets method)
- `psx-broker-statement-parser` — normalize KTrade/AKD/JS Global PDFs
- `psx-announcements-summarizer` — LLM-powered summaries of every PSX filing

The MCP server makes all of these LLM-callable. Pair them and you have a complete conversational PSX research stack.

## Limitations / honest notes

- **PSX data is delayed ~5 minutes.** Same as the public Data Portal.
- **Scraping is fragile.** If PSX changes their HTML, parsers will need updating. PRs welcome.
- **No order placement.** This is read-only. There's no path here that puts trades on the wire — by design.
- **Holiday list is stub.** Edit `PSX_HOLIDAYS_2026` in `dividend_calc.py` once PSX publishes the annual calendar. Without it, the buy-deadline math correctly skips weekends but will be off during Eid/Independence Day weeks.
- **Personal use.** PSX terms restrict commercial redistribution of market data without a license. Email `marketdatarequest@psx.com.pk` if you need one.

## Contributing

- Add a tool: write the function in `scraper.py`, expose it in `server.py` with `@mcp.tool()`, add a docstring (the docstring becomes the LLM's tool description — make it clear).
- Add a test: drop async tests in `tests/`. The MCP SDK supports in-memory testing.
- File issues for HTML parser breakage with the failing URL and a snippet.

## License

MIT. See [LICENSE](LICENSE).
