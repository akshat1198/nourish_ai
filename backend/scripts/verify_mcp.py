"""End-to-end MCP verification: spawn the server over stdio, list + call tools.

Runs inside the MCP image (has mcp + the app + DB access). Proves the server
works without needing the external inspector.

    docker run --rm --network nourish_ai_default \
      -e DATABASE_URL=postgresql+psycopg2://pantry:pantrypw@db:5432/pantrydb \
      nourish-mcp python scripts/verify_mcp.py
"""
import asyncio
import json
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main() -> None:
    # Spawn the SAME interpreter (this venv), and pass our env through — stdio_client
    # otherwise restricts the subprocess env, dropping DATABASE_URL/HOME.
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "app.mcp_server"], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = (await session.list_tools()).tools
            names = [t.name for t in tools]
            print(f"list_tools -> {len(names)} tools: {names}")
            assert len(names) == 5, names

            # A fast, deterministic tool (no embedder).
            r1 = await session.call_tool(
                "find_substitutions", {"ingredient": "chicken breast", "diet": "vegan"}
            )
            subs = json.loads(r1.content[0].text)
            print(f"find_substitutions(chicken breast, vegan) -> {[s['use'] for s in subs['substitutes']]}")
            assert any(s["use"] == "tofu" for s in subs["substitutes"])

            # search_recipes exercises the full hybrid retrieval (loads the model).
            r2 = await session.call_tool(
                "search_recipes", {"pantry": ["pasta", "tomato", "garlic"], "limit": 3}
            )
            res = json.loads(r2.content[0].text)
            titles = [x["title"] for x in res["results"]]
            print(f"search_recipes(pasta,tomato,garlic) -> {titles}")
            assert "Tomato Garlic Pasta" in titles

    print("\nMCP server OK: 5 tools listed, deterministic + hybrid tools executed.")


if __name__ == "__main__":
    asyncio.run(main())
