# server.py - clean final version

import asyncio
import sys
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types
from fetch_stack import search_all_sites

app = Server("embedmcp")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_embedded_forums",
            description="""Search Stack Overflow and Electrical Engineering Stack Exchange 
            for embedded systems and electronics questions. Use this when developers ask about:
            - Microcontroller issues (STM32, ESP32, Arduino, RP2040, AVR, PIC)
            - Communication protocols (I2C, SPI, UART, CAN, USB)
            - RTOS topics (FreeRTOS, Zephyr, task scheduling)
            - Hardware design (MOSFETs, gate drivers, PCB layout, power supplies)
            - Electrical engineering concepts (op-amps, filters, ADC, DAC)
            Returns real questions and answers sorted by community score.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The technical question or topic to search for"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    
    if name != "search_embedded_forums":
        raise ValueError(f"Unknown tool: {name}")
    
    if not isinstance(arguments, dict):
        return [types.TextContent(type="text", text="Error: Invalid arguments format")]

    query = arguments.get("query", "")
    if not query:
        return [types.TextContent(type="text", text="Error: No query provided")]
    
    print(f"[embedmcp] Searching for: '{query}'", file=sys.stderr, flush=True)
    
    # search_all_sites returns 3 values — results, vendor_tip, site_counts
    results, vendor_tip, site_counts = search_all_sites(query)
    
    # Separate result types
    se_results  = [r for r in results if r.get("site") in ("stackoverflow", "electronics")]
    gh_results  = [r for r in results if r.get("site") == "github"]
    kb_results  = [r for r in results if r.get("site") == "vendor_kb"]
    
    if not se_results and not gh_results and not kb_results:
        return [types.TextContent(
            type="text",
            text=f"No results found for '{query}'. Try different keywords."
        )]
    
    # Build output for Claude
    output = f"Search results for: '{query}'\n"
    output += f"Sources: SO={site_counts.get('stackoverflow',0)} | EE={site_counts.get('electronics',0)} | GitHub={site_counts.get('github',0)}\n"
    
    if vendor_tip:
        output += f"Official community: {vendor_tip['name']} → {vendor_tip['url']}\n"
    
    output += "=" * 60 + "\n\n"
    
    # Stack Exchange results
    if se_results:
        output += "── STACK OVERFLOW + EE STACK EXCHANGE ──\n\n"
        for i, r in enumerate(se_results, 1):
            status    = "ANSWERED" if r.get("answered") else "OPEN"
            site_label = "Stack Overflow" if r["site"] == "stackoverflow" else "EE Stack Exchange"
            output += f"{i}. [{site_label}] {r['title']}\n"
            output += f"   Status: {status} | Score: {r.get('score',0)} | Answers: {r.get('answer_count',0)}\n"
            output += f"   Tags: {', '.join(r.get('tags',[])[:4])}\n"
            output += f"   URL: {r['link']}\n"
            if r.get("answer_content"):
                ans = r["answer_content"]
                label = "✓ Accepted answer" if ans["is_accepted"] else "Top answer"
                output += f"   {label} (score:{ans['score']}):\n"
                output += f"   {ans['body']}\n"
            output += "\n"
    
    # GitHub Issues
    if gh_results:
        output += "── GITHUB ISSUES ──\n\n"
        for i, r in enumerate(gh_results, 1):
            state_label = "CLOSED ✓" if r.get("state") == "closed" else "OPEN"
            output += f"{i}. [{r.get('repo_label','GitHub')}] {r['title']}\n"
            output += f"   State: {state_label} | 👍 {r.get('reactions',0)} | 💬 {r.get('comments',0)}\n"
            output += f"   URL: {r['link']}\n"
            if r.get("body_preview"):
                output += f"   Preview: {r['body_preview'][:300]}\n"
            output += "\n"
    
    # Vendor KB links
    if kb_results:
        output += "── VENDOR KNOWLEDGE BASE ──\n\n"
        for r in kb_results:
            output += f"→ {r['title']}\n"
            output += f"  {r['link']}\n\n"
    
    return [types.TextContent(type="text", text=output)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        print("[embedmcp] Server starting...", file=sys.stderr, flush=True)
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="embedmcp",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())