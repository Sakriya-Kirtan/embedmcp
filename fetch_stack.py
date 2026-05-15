# fetch_stack.py — VERSION 3
# Key fixes vs v2:
#   - errata_console_section naming collision fixed
#   - search_errata called only once (was called twice)
#   - errata relevance filter: only show errata when query is a debugging query,
#     not a datasheet/pinout/configuration lookup
#   - generate_action_summary now calls Groq API for real synthesis
#   - fallback to mechanical summary if API unavailable

import sys
import re
import requests
import json
from config import STACK_SITES, RESULTS_PER_SITE, STACK_API_URL, MIN_SCORE, VENDOR_RESOURCES
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
import html
from github_fetch import search_github_issues
from errata_db import search_errata
from action_summary import generate_action_summary, _is_debug_query
load_dotenv()

STACK_API_KEY = os.getenv("STACK_API_KEY")


# ---------------------------------------------------------------------------
# Query intent classifier
# ---------------------------------------------------------------------------

# These signal a datasheet / pinout / config lookup — NOT a debugging query.
# Errata should NOT be shown for these.
_DATASHEET_SIGNALS = [
    "what are", "which pin", "pinout", "pin map", "pin number",
    "where is", "how to configure", "how do i set", "what is the address",
    "register address", "base address", "memory map", "alternate function",
    "datasheet", "reference manual", "schematic", "footprint",
    "uart pins", "i2c pins", "spi pins", "gpio pin",
]

# These signal a debugging / bug query where errata is useful.
_DEBUG_SIGNALS = [
    "not working", "hang", "hanging", "stuck", "freeze", "crash", "fail",
    "broken", "bug", "issue", "problem", "error", "wrong value", "no data",
    "timeout", "brownout", "reset", "dma", "interrupt", "callback",
    "stall", "hal_busy", "hardfault", "overrun", "noise", "corrupt",
    "hal_error", "hal_timeout", "never fires", "not triggered",
]

# def _is_debug_query(query):
#     """
#     Returns True if the query looks like a debugging problem.
#     Returns False for datasheet/pinout/configuration lookups.
#     Errata should only be shown for debug queries.
#     """
#     q = query.lower()
    
#     # Explicit datasheet signals override everything
#     if any(s in q for s in _DATASHEET_SIGNALS):
#         return False
    
#     # Debug signals confirm it's a bug query
#     if any(s in q for s in _DEBUG_SIGNALS):
#         return True
    
#     # Default: if it contains a chip name but no debug signal,
#     # treat as ambiguous — show errata only if it's a very specific
#     # chip query (user probably wants to debug, not look up pins)
#     # Conservative: default to False for ambiguous queries
#     return False


# ---------------------------------------------------------------------------
# Stack Exchange fetcher
# ---------------------------------------------------------------------------

def fetch_stack_questions(query, site="stackoverflow", tag=None, count=RESULTS_PER_SITE):
    params = {
        "order": "desc",
        "sort": "relevance",
        "q": query,
        "site": site,
        "pagesize": count,
        "filter": "withbody",
        "key": STACK_API_KEY
    }
    if tag:
        params["tagged"] = tag

    try:
        response = requests.get(f"{STACK_API_URL}/search/advanced", params=params)
        response.raise_for_status()
        data = response.json()
        quota = data.get("quota_remaining", "unknown")

        results = []
        for item in data.get("items", []):
            score = item.get("score", 0)
            if score < MIN_SCORE:
                continue
            results.append({
                "title": html.unescape(item.get("title", "")),
                "link": item.get("link"),
                "score": score,
                "answered": item.get("is_answered", False),
                "answer_count": item.get("answer_count", 0),
                "tags": item.get("tags", []),
                "site": site,
                "question_id": item.get("question_id")
            })

        return {"results": results, "quota_remaining": quota, "site": site, "query": query}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching from {site}: {e}")
        return {"results": [], "quota_remaining": 0, "site": site, "query": query}


def search_vendor_kb(product_name, vendor_url):
    try:
        search_url = f"{vendor_url.rstrip('/')}?q={requests.utils.quote(product_name)}"
        return [{
            "title": f"Search '{product_name}' in vendor KB",
            "link": search_url,
            "source": "vendor_kb_search",
            "answered": False,
            "answer_count": 0,
            "score": 0,
            "tags": [],
            "site": "vendor_kb",
            "question_id": None
        }]
    except Exception as e:
        print(f"  Error building vendor KB URL: {e}", file=sys.stderr)
        return []


def fetch_from_so(query):
    return fetch_stack_questions(query, site="stackoverflow")["results"]

def fetch_from_ee(query):
    return fetch_stack_questions(query, site="electronics")["results"]

def fetch_from_github(query, vendor_key=None, max_results=3):
    return search_github_issues(query, vendor_key=vendor_key, max_results=max_results)

def fetch_from_reddit(query, vendor_key=None, max_results=3):
    from reddit_fetch import search_reddit_for_vendor
    return search_reddit_for_vendor(query, vendor_key=vendor_key, max_results=max_results)


def detect_vendor(query):
    query_lower = clean(query)
    for vendor_key, vendor in VENDOR_RESOURCES.items():
        all_keywords = sorted(
            vendor.get("products", []) + vendor.get("aliases", []),
            key=len, reverse=True
        )
        for keyword in all_keywords:
            if clean(keyword) in query_lower:
                return vendor_key, vendor
    return None, None


def build_vendor_fallback(vendor, query):
    return {
        "name": vendor["name"],
        "url": vendor["community_url"],
        "suggested_searches": [
            f"{query} V4L2", f"{query} MIPI CSI",
            f"{query} Linux BSP", f"{query} device tree"
        ]
    }


def fetch_accepted_answer(question_id, site):
    params = {"site": site, "filter": "withbody", "key": STACK_API_KEY}
    try:
        url = f"{STACK_API_URL}/questions/{question_id}/answers"
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        answers = data.get("items", [])
        if not answers:
            return None

        accepted = next((a for a in answers if a.get("is_accepted")), None)
        best = accepted or max(answers, key=lambda a: a.get("score", 0))

        body = best.get("body", "")
        clean_body = re.sub(r'<[^>]+>', '', body)
        clean_body = re.sub(r'&lt;', '<', clean_body)
        clean_body = re.sub(r'&gt;', '>', clean_body)
        clean_body = re.sub(r'&amp;', '&', clean_body)
        clean_body = re.sub(r'&quot;', '"', clean_body)
        clean_body = re.sub(r'\n{3,}', '\n\n', clean_body).strip()

        if len(clean_body) > 1500:
            clean_body = clean_body[:1500] + "... [truncated, see full answer at link]"

        return {
            "score": best.get("score", 0),
            "is_accepted": best.get("is_accepted", False),
            "body": clean_body
        }
    except Exception as e:
        print(f"  Error fetching answer for {question_id}: {e}", file=sys.stderr)
        return None


def clean(text):
    text = text.lower()
    text = re.sub(r'[/_\-]', '', text)
    return text


# ---------------------------------------------------------------------------
# Main search orchestrator
# ---------------------------------------------------------------------------

def search_all_sites(query, debug_list=None):
    original_query = query
    cleaned_query = clean(query)

    vendor_key, vendor = detect_vendor(cleaned_query)

    so_results     = fetch_from_so(original_query)
    ee_results     = fetch_from_ee(original_query)
    github_results = fetch_from_github(original_query, vendor_key=vendor_key, max_results=3)
    reddit_results = fetch_from_reddit(original_query, vendor_key=vendor_key, max_results=3)

    # Errata: only for debug queries, not datasheet/pinout lookups
    errata_results = []
    if _is_debug_query(original_query):
        errata_results = search_errata(original_query, vendor_key=vendor_key)
    else:
        _log(debug_list, "  [Errata] Skipped — query looks like datasheet lookup, not a bug")

    site_counts = {
        "SO":     len(so_results),
        "EE":     len(ee_results),
        "GitHub": len(github_results),
        "Reddit": len(reddit_results),
        "Errata": len(errata_results),
    }

    _log(debug_list, f"  Got {len(so_results)} SO results")
    _log(debug_list, f"  Got {len(ee_results)} EE results")
    _log(debug_list, f"  Got {len(github_results)} GitHub results")
    _log(debug_list, f"  Got {len(reddit_results)} Reddit results")
    _log(debug_list, f"  Got {len(errata_results)} Errata results")

    # Errata always first — highest confidence source
    all_results = errata_results + so_results + ee_results + github_results + reddit_results

    # Sort by score but keep errata pinned at top
    errata_part = [r for r in all_results if r.get("site") == "errata"]
    other_part  = [r for r in all_results if r.get("site") != "errata"]
    other_part.sort(key=lambda x: x.get("score", 0), reverse=True)
    all_results = errata_part + other_part

    # Deduplicate by question_id
    seen_ids = set()
    deduped = []
    for r in all_results:
        qid = r.get("question_id")
        if qid is None or qid not in seen_ids:
            deduped.append(r)
        if qid:
            seen_ids.add(qid)
    all_results = deduped

    # Vendor KB
    vendor_kb_results = []
    if vendor and vendor.get("community_url"):
        matched_keyword = None
        all_keywords_sorted = sorted(
            vendor.get("products", []) + vendor.get("aliases", []),
            key=len, reverse=True
        )
        for keyword in all_keywords_sorted:
            if clean(keyword) in cleaned_query:
                matched_keyword = keyword
                break

        if matched_keyword:
            _log(debug_list, f"  Detected vendor keyword: '{matched_keyword}' → {vendor['name']} KB")
            if vendor_key != "renesas":
                vendor_kb_results.extend(search_vendor_kb(original_query.strip(), vendor["community_url"]))
                vendor_kb_results.extend(search_vendor_kb(matched_keyword, vendor["community_url"]))

        if vendor_kb_results:
            _log(debug_list, f"  Got {len(vendor_kb_results)} vendor KB URLs")
            all_results.extend(vendor_kb_results)
        site_counts["vendor_kb"] = len(vendor_kb_results)

    if vendor_key == "renesas":
        from renesas_kb import get_renesas_resources
        renesas_results = get_renesas_resources(original_query)
        all_results.extend(renesas_results)
        _log(debug_list, f"  [Renesas] Added {len(renesas_results)} results")

    # Fetch accepted answers for top non-errata SE results
    _log(debug_list, "  Fetching answer content for top SE results...")
    se_only = [r for r in all_results if r.get("site") in ("stackoverflow", "electronics")]
    for r in se_only[:3]:
        if r.get("answered") and r.get("question_id"):
            answer = fetch_accepted_answer(r["question_id"], r["site"])
            if answer:
                r["answer_content"] = answer
                _log(debug_list, f"  Got answer for: {r['title'][:50]}...")

    vendor_tip = None
    fallback   = None
    if vendor:
        vendor_tip = {"name": vendor["name"], "url": vendor["community_url"]}
        if len(all_results) == 0:
            fallback = build_vendor_fallback(vendor, query)

    return all_results, (fallback or vendor_tip), site_counts


def _log(debug_list, message):
    if debug_list is not None:
        debug_list.append(message)
    else:
        print(message, file=sys.stderr)


# ---------------------------------------------------------------------------
# Groq synthesis — the real "What to Do" answer
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Console + UI formatters
# ---------------------------------------------------------------------------

def _format_errata_section(results):
    """Renamed from errata_console_section to avoid naming collision."""
    lines = []
    errata_results = [r for r in results if r.get("site") == "errata"]

    if errata_results:
        lines.append(f"  ── Silicon Errata ({len(errata_results)}) ────────────────────────────────────")
        for r in errata_results:
            sev = r.get("severity", "?")
            sev_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪")
            lines.append(f"  {sev_icon} [{r.get('chip_label','?')}] {r['title']}")
            lines.append(f"     📄 {r.get('doc','?')} §{r.get('section','?')} | Affected: {r.get('affected_revisions','?')}")
            if r.get("fixed_in"):
                lines.append(f"     ✅ Fixed in: {r['fixed_in']}")
            else:
                lines.append(f"     ⚠️  Workaround only — no silicon fix")
            lines.append(f"     Fix: {r.get('fix','')[:200]}")
            lines.append(f"     🔗 {r.get('link','')}")
            lines.append("")
    return lines


def format_console_output(query, results, vendor_tip, site_counts):
    lines = []

    so_count = site_counts.get("SO", 0)
    ee_count = site_counts.get("EE", 0)
    kb_count = site_counts.get("vendor_kb", 0)
    gh_count = site_counts.get("GitHub", 0)
    rd_count = site_counts.get("Reddit", 0)
    er_count = site_counts.get("Errata", 0)

    lines.append("\n" + "═" * 65)
    lines.append(f"  QUERY: {query}")
    lines.append("═" * 65)
    lines.append(f"\n  📊 SUMMARY")
    lines.append(f"  SO: {so_count} | EE: {ee_count} | GitHub: {gh_count} | Reddit: {rd_count} | Errata: {er_count} | KB: {kb_count}")

    if vendor_tip:
        lines.append(f"  🏭 Vendor: {vendor_tip['name']} → {vendor_tip['url']}")

    # Errata section — using renamed function, no collision
    errata_lines = _format_errata_section(results)
    if errata_lines:
        lines.extend(errata_lines)

    se_results = [r for r in results if r.get("site") in ("stackoverflow", "electronics")]
    if se_results:
        lines.append(f"\n  ── Stack Overflow + EE Stack Exchange ({len(se_results)}) ──────────────")
        for i, r in enumerate(se_results, 1):
            status     = "✓" if r["answered"] else "✗"
            site_label = "SO" if r["site"] == "stackoverflow" else "EE"
            lines.append(f"  {i}. [{site_label}] {status} (score:{r['score']:>3})  {r['title']}")
            lines.append(f"      🔗 {r['link']}")
            if r.get("answer_content"):
                ans = r["answer_content"]
                label   = "Accepted" if ans["is_accepted"] else "Top ans"
                preview = ans["body"][:200].replace("\n", " ")
                lines.append(f"      ↳ {label} (score:{ans['score']}): {preview}...")
            lines.append("")

    gh_results = [r for r in results if r.get("site") == "github"]
    if gh_results:
        lines.append(f"  ── GitHub Issues ({len(gh_results)}) ────────────────────────────────────")
        for i, r in enumerate(gh_results, 1):
            state = "✓ closed" if r.get("state") == "closed" else "○ open"
            lines.append(f"  {i}. [{r['repo_label']}] {state} 👍{r['reactions']} 💬{r['comments']}")
            lines.append(f"     {r['title']}")
            lines.append(f"     🔗 {r['link']}")
            if r.get("body_preview"):
                lines.append(f"     ↳ {r['body_preview'][:150].replace(chr(10), ' ')}...")
            lines.append("")

    rd_results = [r for r in results if r.get("site") == "reddit"]
    if rd_results:
        lines.append(f"  ── Reddit ({len(rd_results)}) ─────────────────────────────────────────")
        for i, r in enumerate(rd_results, 1):
            has_comments = "✓" if r.get("answer_count", 0) > 0 else "○"
            lines.append(f"  {i}. [r/{r.get('subreddit','embedded')}] {has_comments} ⬆{r.get('upvotes',0)} 💬{r.get('answer_count',0)}")
            lines.append(f"     {r['title']}")
            lines.append(f"     🔗 {r['link']}")
            if r.get("body_preview"):
                lines.append(f"     ↳ {r['body_preview'][:150].replace(chr(10), ' ')}...")
            lines.append("")

    kb_results = [r for r in results if r.get("site") == "vendor_kb"]
    if kb_results:
        lines.append(f"  ── Vendor KB ({len(kb_results)}) ──────────────────────────────────────")
        for r in kb_results:
            lines.append(f"  → {r['title']}")
            lines.append(f"     🔗 {r['link']}")
        lines.append("")

    lines.append(f"  ── 🤖 WHAT TO DO ─────────────────────────────────────────")
    lines.append(generate_action_summary(query, results, vendor_tip))
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import time

    test_queries = [
        # Debug queries — should show errata
        "STM32H743 I2C DMA intermittently stalls clock held low",
        "STM32 HAL I2C HAL_BUSY stuck never recovers",
        "ESP32 brownout detector triggered WiFi init",
        # Datasheet queries — should NOT show errata
        "what are stm32f429zi uart pins",
        "STM32H743 pinout",
        "how to configure SPI on STM32F4",
    ]

    for query in test_queries:
        print("\n" + "═" * 65)
        print(f"  QUERY: {query}")
        print(f"  Debug query: {_is_debug_query(query)}")
        print("═" * 65)

        results, vendor_tip, site_counts = search_all_sites(query)
        print(format_console_output(query, results, vendor_tip, site_counts))
        time.sleep(1)