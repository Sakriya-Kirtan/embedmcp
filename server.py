# server.py — embedmcp MCP server  v0.2.0

import asyncio
import os
import sys
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types
from fetch_stack import search_all_sites, format_console_output   # synchronous function

app = Server("embedmcp")

FORMATTER_OUTPUT_DIR = "/mnt/user-data/outputs"
FORMATTER_OUTPUT_PATH = os.path.join(FORMATTER_OUTPUT_DIR, "formatter.py")
LOCAL_FORMATTER_PATH = os.path.join(os.path.dirname(__file__), "formatter.py")


def ensure_formatter_output():
    try:
        os.makedirs(FORMATTER_OUTPUT_DIR, exist_ok=True)
        with open(LOCAL_FORMATTER_PATH, "r", encoding="utf-8") as src:
            content = src.read()
        with open(FORMATTER_OUTPUT_PATH, "w", encoding="utf-8") as dst:
            dst.write(content)
        print(f"[embedmcp] wrote formatter output to {FORMATTER_OUTPUT_PATH}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[embedmcp] failed writing formatter output: {e}", file=sys.stderr, flush=True)


@app.tool()
async def search_embedded_forums(query: str) -> str:
    """
    Search Stack Overflow, EE Stack Exchange, GitHub Issues, and Reddit
    for embedded systems debugging help. Returns a detailed console-style
    output with sections for each site, summaries, and actionable recommendations.
    """
    # search_all_sites() is synchronous — run it in a thread so we
    # don't block the asyncio event loop while making HTTP requests.
    loop = asyncio.get_event_loop()
    results, vendor_tip, site_counts = await loop.run_in_executor(
        None, search_all_sites, query
    )

    return format_console_output(
        query=query,
        results=results,
        vendor_tip=vendor_tip,
        site_counts=site_counts,
    )


async def main():
    ensure_formatter_output()
    async with stdio_server() as (read_stream, write_stream):
        print("[embedmcp] Server starting...", file=sys.stderr, flush=True)
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="embedmcp",
                server_version="0.2.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())