# Clark MCP integration docs

Integrate Clark into your LLM client for crypto and stock screening, economic data, tax and regulation info, backtesting, technical analysis, and Krypton Pay (balances, swaps, transfers).

> This page is the “getting started” reference for connecting to the Clark HTTP MCP server from tools like Cursor or any MCP-compatible client.

## Quickstart

- Add the Clark MCP server to your MCP configuration
- Pass user identity via headers (recommended)
- Call `krypton_query` with natural-language instructions
- If you receive a human-in-the-loop interrupt, resolve it with `krypton_approve_interrupt`

## Connect from your LLM client

In your MCP config (for example `mcp.json` or Cursor MCP settings), add the Clark MCP server URL.

If you can, pass identity via headers so you don’t have to include `user_id` / `username` on every tool call.

```json
{
  "mcpServers": {
    "krypton-strands": {
      "url": "https://clark.kryptonfund.com/mcp",
      "headers": {
        "x-user-id": "your-user-id",
        "x-username": "your-username"
      }
    }
  }
}
```

## MCP tools

### `krypton_query`

Routes a natural-language request through the Krypton/Strands multi-agent orchestrator and returns a structured result (message, data, agent_flow, costs, etc.).

If the response includes `stop_reason: "interrupt"` and an `interrupts` array, you must call `krypton_approve_interrupt` to approve or reject the operation.

- Parameters (common): `query`, `user_id`, `username`, `session_id`, `top_n`, `include_search`, `interrupt_content`

### `krypton_approve_interrupt`

Approves or rejects an interrupt (for example Krypton Pay transfers).

- Parameters: `interrupt_id`, `query`, `approve` (default true), `user_id`, `username`, `session_id`

## What the orchestrator can do

You send a single natural-language query; the orchestrator decides which internal tools to call.

- **screener**: Crypto screening (price, market cap, technical indicators)
- **economic**: Stocks, crypto, forex, commodities, indicators, rates, calendar data
- **regulations**: Tax and regulation information
- **backtest**: Strategy backtesting (historical simulations, Sharpe ratio, max drawdown)
- **technical**: Technical analysis and charting (RSI, MAs, Bollinger Bands, ADX, SuperTrend)
- **search**: General web search (news, facts, definitions)
- **data_fetcher**: Historical OHLCV data
- **krypton_pay**: Balances, swaps, transfers (may require approval interrupts)

## Human-in-the-loop (interrupts)

For operations that require user approval (e.g. payments), the orchestrator can return `stop_reason: "interrupt"` with an `interrupts` array.

Your client should display the interrupt details (amount, recipient, operation), then call `krypton_approve_interrupt` with the interrupt id and `approve: true` or `false`. Use the same `query` and session identifiers so the flow can continue.

```json
{
  "stop_reason": "interrupt",
  "interrupts": [
    {
      "id": "<interrupt-id>",
      "name": "krypton-pay-approval",
      "reason": {
        "receiver_username": "alice",
        "to_token": "USD",
        "received_amount": 10,
        "operation": "direct_transfer"
      }
    }
  ]
}
```

## Example query payload

What gets sent to the Strands API (via `krypton_query`) for a normal query:

```json
{
  "query": "Find top 5 cryptos with price above $5",
  "user_id": "user123",
  "username": "alice",
  "session_id": "session456",
  "top_n": 5,
  "include_search": true
}
```

