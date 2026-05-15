"""
server.py — PATCH for 8-field structured output
================================================
This shows only the parts of server.py that need to change.
Your existing imports, app setup, and vendor logic stay the same.

STEP 1: add this import at the top of server.py
"""

from formatter import format_debug_answer


"""
STEP 2: replace your existing search_embedded_forums tool handler
with this version. The key changes are:

  - Unpack 3 values from search_all_sites()  (fixes the crash bug too)
  - Pass results + vendor_tip + site_counts into format_debug_answer()
  - Return the structured 8-field string instead of raw results

If your search_all_sites() currently returns 2 values, update it to
return (results, vendor_tip, site_counts) — see fetch_stack.py note below.
"""

# ── EXAMPLE HANDLER (replace your existing one) ──────────────────────────────

# @server.tool()
# async def search_embedded_forums(query: str) -> str:
#     """
#     Search Stack Overflow, EE Stack Exchange, GitHub Issues, and Reddit
#     for embedded systems debugging help. Returns a structured 8-field
#     debug answer: root cause, confidence, consensus, first steps,
#     bad SDK versions, workarounds, register fixes, and errata.
#     """
#     # Unpack all 3 return values (fixes the crash on vendor queries)
#     results, vendor_tip, site_counts = await search_all_sites(query)
#
#     # Build and return the structured answer
#     return format_debug_answer(
#         query=query,
#         results=results,
#         vendor_tip=vendor_tip,
#         site_counts=site_counts,
#     )


"""
STEP 3: fetch_stack.py — make sure search_all_sites() returns 3 values.

Your current search_all_sites() likely returns (results, vendor_tip).
Update the return statement to also include site_counts:

    so_results = fetch_from_so(query)
    ee_results = fetch_from_ee(query)
    github_results = fetch_from_github(query)   # when ready
    reddit_results = fetch_from_reddit(query)   # when ready

    all_results = so_results + ee_results + github_results + reddit_results

    site_counts = {
        "SO": len(so_results),
        "EE": len(ee_results),
        "GitHub": len(github_results),
        "Reddit": len(reddit_results),
    }

    vendor_tip = detect_vendor(query)   # your existing function

    return all_results, vendor_tip, site_counts


Each result dict should have as many of these keys as available
(formatter.py will use whichever are present, skip missing ones):

    {
        "title":             str,   # question/issue title
        "url":               str,   # link to original
        "source":            str,   # "stackoverflow", "reddit", "github", etc.
        "score":             int,   # SO/EE vote count
        "upvotes":           int,   # Reddit upvotes
        "is_answered":       bool,  # SO accepted answer flag
        "accepted_answer_id":int,   # SO accepted answer id
        "state":             str,   # GitHub issue state: "OPEN" or "CLOSED"
        "body":              str,   # answer body text (SO/EE)
        "preview":           str,   # short text preview (Reddit/GitHub)
        "answer_body":       str,   # full accepted answer text if fetched
        "site":              str,   # "stackoverflow" or "electronics"
        "subreddit":         str,   # e.g. "stm32"
        "repo":              str,   # e.g. "STMicroelectronics/STM32CubeF4"
    }

Keys you don't have yet just get ignored — the formatter degrades gracefully.
"""


"""
QUICK TEST — run this directly to verify formatter output without
needing the full MCP server running:

    python server_patch.py

It uses a realistic mock result set matching what your live tool returns.
"""

if __name__ == "__main__":
    from formatter import format_debug_answer

    mock_results = [
        {
            "title": "[STM32 F4 HAL] HAL_I2C_Mem_Read_IT routine causing interrupts to hang processor",
            "url": "https://github.com/STMicroelectronics/STM32CubeF4/issues/63",
            "source": "github",
            "repo": "STMicroelectronics/STM32CubeF4",
            "state": "CLOSED",
            "upvotes": 0,
            "score": 0,
            "preview": (
                "Custom board with STM32F417, external 8MHz crystal, system clock at 168MHz. "
                "I2C bus running at 100KHz. HAL_I2C_Mem_Read_IT causes interrupt to hang. "
                "Workaround: use blocking HAL_I2C_Mem_Read instead. Fixed in HAL v1.7.3."
            ),
        },
        {
            "title": "I2C eeprom w/ L0 and F7 hanging at HAL_I2C_IsDeviceReady()",
            "url": "https://reddit.com/r/stm32/comments/rgknun/i2c_eeprom_w_l0_and_f7_hanging_at_hal_i2c/",
            "source": "reddit",
            "subreddit": "stm32",
            "upvotes": 2,
            "score": 0,
            "preview": (
                "Make sure you reset the I2C peripheral after a bus error. "
                "Check SR1 register for BERR or ARLO flags. "
                "The root cause is usually missing STOP condition. "
                "Try calling HAL_I2C_DeInit() then HAL_I2C_Init() to recover."
            ),
        },
        {
            "title": "STM32 I2C bus stuck — two weeks debugging a BME688",
            "url": "https://reddit.com/r/stm32/comments/1oo8wjh/",
            "source": "reddit",
            "subreddit": "stm32",
            "upvotes": 5,
            "score": 0,
            "preview": (
                "Solution was adding 4.7k pull-up resistors to SDA and SCL. "
                "Also had to configure GPIO as open-drain. "
                "Verified with logic analyser — clock stretching errata on STM32WL "
                "documented in ES0506 errata sheet."
            ),
        },
    ]

    mock_vendor_tip = "Official STMicroelectronics community → https://community.st.com"
    mock_site_counts = {"SO": 0, "EE": 0, "GitHub": 1, "Reddit": 3}

    output = format_debug_answer(
        query="STM32 I2C bus hanging HAL timeout",
        results=mock_results,
        vendor_tip=mock_vendor_tip,
        site_counts=mock_site_counts,
    )

    print(output)
