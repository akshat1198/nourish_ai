# NourishAI MCP server (Stage 4.1)

Exposes the same five agent tools (`search_recipes`, `check_allergens`,
`find_substitutions`, `estimate_nutrition`, `build_shopping_list`) to any MCP
client over stdio. It's an **edge adapter** over `app.agent.tools.TOOLS` — the
app's internal callers still use the plain Python functions; nothing is
rerouted through MCP.

Runs on the project's own venv (Python 3.12) — no separate image. `mcp` lives
in the main `requirements.txt` alongside FastAPI (0.139, which accepts the same
`starlette` `mcp` needs).

## Verify

```sh
make up          # DB must be running (the tools query it)
make mcp-verify  # spawns the server over stdio, lists + calls all-5 tools
```

## Use it from Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(the DB must be up — `make up`; the tools query `localhost:5432`):

```json
{
  "mcpServers": {
    "nourishai": {
      "command": "/Applications/NourishAI/nourish_ai/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/Applications/NourishAI/nourish_ai/backend"
    }
  }
}
```

Restart Claude Desktop. The NourishAI tools appear in the tools menu; ask e.g.
*"what can I cook with eggs and rice?"* and it calls `search_recipes`.

## Inspector (optional)

```sh
cd backend
npx @modelcontextprotocol/inspector ../.venv/bin/python -m app.mcp_server
```
