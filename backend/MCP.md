# NourishAI MCP server (Stage 4.1)

Exposes the same five agent tools (`search_recipes`, `check_allergens`,
`find_substitutions`, `estimate_nutrition`, `build_shopping_list`) to any MCP
client over stdio. It's an **edge adapter** over `app.agent.tools.TOOLS` — the
app's internal callers still use the plain Python functions; nothing is
rerouted through MCP.

Built as a **separate image** (`Dockerfile.mcp`) without FastAPI, because the
`mcp` package requires a newer `starlette` than FastAPI allows. Latest `mcp`,
no conflict.

## Build & verify

```sh
make up            # DB must be running (the tools query it)
make mcp-build     # builds the nourish-mcp image (torch + embedding model baked in)
make mcp-verify    # spawns the server over stdio, lists + calls tools
```

## Use it from Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nourishai": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "nourish_ai_default",
        "-e", "DATABASE_URL=postgresql+psycopg2://pantry:pantrypw@db:5432/pantrydb",
        "nourish-mcp"
      ]
    }
  }
}
```

Restart Claude Desktop. The NourishAI tools appear in the tools menu; ask e.g.
*"what can I cook with eggs and rice?"* and it will call `search_recipes`.

**Requirements:** the compose stack must be up (`make up`) so the `db` service is
reachable on `nourish_ai_default`, and the `nourish-mcp` image must be built.

## Inspector (optional)

```sh
npx @modelcontextprotocol/inspector \
  docker run --rm -i --network nourish_ai_default \
  -e DATABASE_URL='postgresql+psycopg2://pantry:pantrypw@db:5432/pantrydb' nourish-mcp
```
