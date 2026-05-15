# server.py — embedmcp MCP server v0.2.0 (FastMCP / mcp 1.x)

import asyncio
import sys
from mcp.server.fastmcp import FastMCP
from fetch_stack import search_all_sites, format_console_output

mcp = FastMCP("embedmcp")


@mcp.tool()
async def search_embedded_forums(query: str) -> str:
    """
    Search Stack Overflow, EE Stack Exchange, GitHub Issues, and Reddit
    for embedded systems debugging help. Use this when developers ask about:
    - Microcontroller issues (STM32, ESP32, Arduino, RP2040, AVR, PIC)
    - Communication protocols (I2C, SPI, UART, CAN, USB)
    - RTOS topics (FreeRTOS, Zephyr, task scheduling)
    - Hardware design (MOSFETs, gate drivers, PCB layout, power supplies)
    - Electrical engineering concepts (op-amps, filters, ADC, DAC)
    Returns structured debug answer with root cause, confidence, workarounds, and errata.
    """
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


if __name__ == "__main__":
    print("[embedmcp] Server starting...", file=sys.stderr, flush=True)
    mcp.run()