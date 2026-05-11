# fetch_stack.py
# VERSION 2 — smarter, cleaner, ready to plug into MCP server

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

load_dotenv()

STACK_API_KEY = os.getenv("STACK_API_KEY")
# --- WHY ARE WE IMPORTING FROM config.py? ---
# Because when we build the MCP server next, it will ALSO import from config.py
# Both files share the same settings — change once, updates everywhere.

def fetch_stack_questions(query, site="stackoverflow", tag=None, count=RESULTS_PER_SITE):
    """
    Fetches questions from Stack Exchange sites.
    
    query  : what to search for e.g. "I2C not working STM32"
    site   : "stackoverflow" or "electronics"  
    tag    : filter by tag e.g. "embedded", "i2c"
    count  : how many results to return
    """
    
    params = {
        "order": "desc",
        "sort": "relevance",
        "q": query,
        "site": site,
        "pagesize": count,
        "filter": "withbody",
        "key": STACK_API_KEY
    }
    
    # Only add tag filter if a tag was provided
    if tag:
        params["tagged"] = tag
    
    try:
        response = requests.get(f"{STACK_API_URL}/search/advanced", params=params)
        
        # --- WHAT IS STATUS CODE? ---
        # Every API response comes with a number.
        # 200 = success, 400 = bad request, 429 = too many requests (rate limited)
        # We check this so our program doesn't crash silently
        response.raise_for_status()
        
        data = response.json()
        
        # Stack Exchange tells us if we're being rate limited
        # quota_remaining tells how many API calls we have left today (free = 300/day)
        quota = data.get("quota_remaining", "unknown")
        
        results = []
        for item in data.get("items", []):
            score = item.get("score", 0)
            
            # Skip low quality results
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
        
        return {
            "results": results,
            "quota_remaining": quota,
            "site": site,
            "query": query
        }
        
    except requests.exceptions.RequestException as e:
        # --- WHY HANDLE ERRORS? ---
        # Networks fail. APIs go down. Rate limits hit.
        # Instead of crashing, we return an empty result with the error message.
        # Your MCP server will thank you for this later.
        print(f"Error fetching from {site}: {e}")
        return {"results": [], "quota_remaining": 0, "site": site, "query": query}



def search_vendor_kb(product_name, vendor_url):
    """
    Builds a direct search URL for a specific product in the vendor KB.
    Only called for the exact product/alias detected in the query.
    """
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
    
def normalize_query(query):
    query = query.lower()

    replacements = {
        "rz/g": "rzg",
        "rz-g": "rzg",
        "rz/v": "rzv",
        "rz-v": "rzv",
        "stm32h7": "stm32h7",
        "stm32f4": "stm32f4"
    }

    for old, new in replacements.items():
        query = query.replace(old, new)

    # remove weird separators
    query = re.sub(r'[/_-]', '', query)
    return query    
def detect_vendor(query):
    query_lower = clean(query)

    for vendor_key, vendor in VENDOR_RESOURCES.items():
        # Sort longest first — "rzg3e" matches before "rzg"
        all_keywords = sorted(
            vendor.get("products", []) + vendor.get("aliases", []),
            key=len, reverse=True
        )
        for keyword in all_keywords:
            if clean(keyword) in query_lower:
                return vendor_key, vendor

    return None, None

def build_vendor_fallback(vendor, query):
    query = query.strip()
    return {
        "name": vendor["name"],
        "url": vendor["community_url"],
        "suggested_searches": [
            f"{query} V4L2",
            f"{query} MIPI CSI",
            f"{query} Linux BSP",
            f"{query} device tree"
        ]
    }


def fetch_accepted_answer(question_id, site):
    """
    Given a question ID, fetches the actual text of the accepted answer.
    
    WHY IS THIS IMPORTANT?
    Right now we only send Claude the question title and link.
    Claude then answers from its own training data — which might be outdated.
    
    With this function, we fetch the REAL accepted answer from Stack Exchange
    — the one the community voted as best. Claude then quotes actual expert
    answers instead of guessing. Much more accurate for embedded questions
    where details like register names and timing values really matter.
    
    question_id : the number at the end of a Stack Exchange URL
    site        : "stackoverflow" or "electronics"
    """
    
    params = {
        "site": site,
        "filter": "withbody",  # include full answer HTML/markdown body
        "key": STACK_API_KEY
    }
    
    try:
        url = f"{STACK_API_URL}/questions/{question_id}/answers"
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        answers = data.get("items", [])
        
        if not answers:
            return None
        
        # Find the accepted answer first
        # If no accepted answer, take the highest scored one
        # --- WHY? ---
        # Not every question has an accepted answer (OP never clicked the checkmark)
        # but the highest scored answer is usually still the best one
        accepted = next((a for a in answers if a.get("is_accepted")), None)
        best = accepted or max(answers, key=lambda a: a.get("score", 0))
        
        # Clean up the HTML body — Stack Exchange returns HTML tags
        # We strip them to get plain readable text for Claude
        body = best.get("body", "")
        
        # Simple HTML tag removal — good enough for our use case
        clean_body = re.sub(r'<[^>]+>', '', body)        # remove HTML tags
        clean_body = re.sub(r'&lt;', '<', clean_body)    # fix escaped chars
        clean_body = re.sub(r'&gt;', '>', clean_body)
        clean_body = re.sub(r'&amp;', '&', clean_body)
        clean_body = re.sub(r'&quot;', '"', clean_body)
        clean_body = re.sub(r'\n{3,}', '\n\n', clean_body)  # collapse blank lines
        clean_body = clean_body.strip()
        
        # Limit to 1000 chars — we don't want to flood Claude's context
        # with one giant answer. 1000 chars captures the key fix/explanation.
        if len(clean_body) > 1000:
            clean_body = clean_body[:1000] + "... [truncated, see full answer at link]"
        
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


def search_all_sites(query):
    """
    Searches both sites and fetches accepted answers for top results.
    """
    original_query = query          # keep original for Stack Exchange search
    cleaned_query = clean(query)  # normalized query for vendor detection
    all_results = []
    site_counts = {}

    # Detect vendor first
    vendor_key, vendor = detect_vendor(cleaned_query)
    
    tag = None  # Don't use tag to avoid filtering too much

    for site_key, site_info in STACK_SITES.items():
        site = site_info["site"]

        data = fetch_stack_questions(original_query, site=site, tag=tag)
        all_results.extend(data["results"])   # 🔥 THIS WAS MISSING
        site_counts[site] = len(data["results"])

        print(f"  Got {len(data['results'])} results | quota left: {data['quota_remaining']}",file=sys.stderr)
    all_results.sort(key=lambda x: x["score"], reverse=True)

    # Remove duplicate questions — same question_id means same question
    # appearing on both SO and EE Stack Exchange
    seen_ids = set()
    deduped = []
    for r in all_results:
        qid = r.get("question_id")
        if qid is None or qid not in seen_ids:
            deduped.append(r)
        if qid:
            seen_ids.add(qid)
    all_results = deduped

    # Search vendor KB if vendor is detected

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
            print(f"  Detected vendor keyword: '{matched_keyword}' → searching {vendor['name']} KB", file=sys.stderr)
            
            # Skip generic ?q= search for Renesas — their site is JS-rendered
            # and those URLs don't actually work. renesas_kb.py handles Renesas.
            if vendor_key != "renesas":
                kb_results = search_vendor_kb(original_query.strip(), vendor["community_url"])
                vendor_kb_results.extend(kb_results)
                kb_results = search_vendor_kb(matched_keyword, vendor["community_url"])
                vendor_kb_results.extend(kb_results)
    
        if vendor_kb_results:
            print(f"  Got {len(vendor_kb_results)} vendor KB URLs", file=sys.stderr)
            all_results.extend(vendor_kb_results)
    
        site_counts["vendor_kb"] = len(vendor_kb_results)
    # Fetch actual answer content for top 3 results only
    # WHY ONLY 3?
    # Each answer fetch = 1 API call. 10 results × every query = quota burns fast.
    # Top 3 by score are almost always the most useful anyway.
    # Search GitHub Issues for the same query
    # WHY HERE? After Stack Exchange so we have vendor_key already detected
    print(f"  [GitHub] Searching issues...", file=sys.stderr)
    github_results = search_github_issues(original_query, vendor_key=vendor_key, max_results=3)
    all_results.extend(github_results)
    site_counts["github"] = len(github_results)
    print(f"  [GitHub] Got {len(github_results)} issues", file=sys.stderr)

    print(f"  Fetching answer content for top 3 results...", file=sys.stderr)

# For Renesas queries, also search Renesas GitHub repos
    if vendor_key == "renesas":
        from renesas_kb import get_renesas_resources
        renesas_results = get_renesas_resources(original_query)
        all_results.extend(renesas_results)
        print(f"  [Renesas] Added {len(renesas_results)} Renesas-specific results", file=sys.stderr)
    
    # Reddit search
    from reddit_fetch import search_reddit_for_vendor
    print(f"  [Reddit] Searching...", file=sys.stderr)
    reddit_results = search_reddit_for_vendor(original_query, vendor_key=vendor_key, max_results=3)
    all_results.extend(reddit_results)
    site_counts["reddit"] = len(reddit_results)
    for r in all_results[:3]:


        # Only fetch answers for Stack Exchange results — NOT GitHub issues
        if r.get("site") in ("stackoverflow", "electronics") and r.get("answered") and r.get("question_id"):
            answer = fetch_accepted_answer(r["question_id"], r["site"])
            if answer:
                r["answer_content"] = answer
                print(f"  Got answer for: {r['title'][:50]}...", file=sys.stderr)

    
    # Vendor tip already detected above
    vendor_tip = None
    fallback = None

    if vendor:
        vendor_tip = {
            "name": vendor["name"],
            "url": vendor["community_url"]
        }

        if len(all_results) == 0:
            fallback = build_vendor_fallback(vendor, query)

    
    return all_results, (fallback or vendor_tip), site_counts


def search_all_vendor_families(vendor_key):
    """
    Search all product families of a specific vendor in their KB.
    Useful for getting an overview of all MPU families.
    
    vendor_key : key from VENDOR_RESOURCES (e.g., "renesas", "st", "espressif")
    """
    
    if vendor_key not in VENDOR_RESOURCES:
        print(f"Vendor '{vendor_key}' not found")
        return []
    
    vendor = VENDOR_RESOURCES[vendor_key]
    all_results = []
    
    print(f"\n Searching all {vendor['name']} product families...")
    print(f"   Knowledge Base: {vendor['community_url']}")
    print(f"   Products: {', '.join(vendor.get('products', []))}")
    print(f"   Aliases: {', '.join(vendor.get('aliases', []))}\n")
    
    # Search for each product family
    for product in vendor.get("products", []):
        results = search_vendor_kb(product, vendor["community_url"])
        all_results.extend(results)
    
    # Search for each alias
    for alias in vendor.get("aliases", []):
        results = search_vendor_kb(alias, vendor["community_url"])
        all_results.extend(results)
    
    return all_results



def generate_action_summary(query, results, vendor_tip):
    """
    Reads all results and generates a simple action plan.
    This replaces opening 15 browser tabs — gives you ONE clear answer.
    
    WHY THIS MATTERS FOR YOUR PRODUCT:
    Developers don't want 15 links. They want to know what to do FIRST.
    This is your product's killer feature — not just search, but synthesis.
    """
    se_results  = [r for r in results if r.get("site") in ("stackoverflow", "electronics") and r.get("answer_content")]
    gh_results  = [r for r in results if r.get("site") == "github" and r.get("state") == "closed"]
    rd_results  = [r for r in results if r.get("site") == "reddit" and r.get("answer_count", 0) > 3]

    lines = []

    # Best Stack Exchange answer
    if se_results:
        best = se_results[0]
        ans = best["answer_content"]
        label = "accepted" if ans["is_accepted"] else "top"
        lines.append(f"  ✅ Best answer ({label}, score {ans['score']}) from {best['site']}:")
        lines.append(f"     {ans['body'][:300].replace(chr(10), ' ')}...")
        lines.append(f"     → {best['link']}")

    # Closed GitHub issue = confirmed fix
    if gh_results:
        best_gh = gh_results[0]
        lines.append(f"\n  🐛 Confirmed fix on GitHub ({best_gh['repo_label']}, now closed):")
        lines.append(f"     {best_gh['title']}")
        lines.append(f"     → {best_gh['link']}")

    # Active Reddit discussion
    if rd_results:
        best_rd = rd_results[0]
        lines.append(f"\n  💬 Active community discussion on r/{best_rd.get('subreddit','embedded')}:")
        lines.append(f"     {best_rd['title']} (⬆{best_rd.get('upvotes',0)} upvotes, {best_rd.get('answer_count',0)} comments)")
        lines.append(f"     → {best_rd['link']}")

    # Vendor forum
    if vendor_tip:
        lines.append(f"\n  🏭 Also check official {vendor_tip['name']} forum:")
        lines.append(f"     → {vendor_tip['url']}")

    if not lines:
        lines.append("  No strong matches found — try rephrasing or check vendor forum directly.")

    lines.append(f"\n  📌 Start with the Stack Exchange answer, then check the GitHub issue if it persists.")

    return "\n".join(lines)


if __name__ == "__main__":
    import time

    test_queries = [
        "Renesas RZG3/E camera interface",
        "STM32 I2C bus hanging",
        "ESP32 WiFi drops connection",
        "MOSFET gate driver high side",
        "FreeRTOS task priority not working",
    ]

    for query in test_queries:
        print("\n" + "═" * 65)
        print(f"  QUERY: {query}")
        print("═" * 65)

        results, vendor_tip, site_counts = search_all_sites(query)

        so_count  = site_counts.get("stackoverflow", 0)
        ee_count  = site_counts.get("electronics", 0)
        kb_count  = site_counts.get("vendor_kb", 0)
        gh_count  = site_counts.get("github", 0)
        rd_count  = site_counts.get("reddit", 0)

        print(f"\n  📊 SUMMARY")
        print(f"  SO: {so_count} | EE: {ee_count} | GitHub: {gh_count} | Reddit: {rd_count} | KB: {kb_count}")
        if vendor_tip:
            print(f"  🏭 Vendor: {vendor_tip['name']} → {vendor_tip['url']}")

        # ── Stack Exchange ────────────────────────────────────────
        se_results = [r for r in results if r.get("site") in ("stackoverflow", "electronics")]
        if se_results:
            print(f"\n  ── Stack Overflow + EE Stack Exchange ({len(se_results)}) ──────────────")
            for i, r in enumerate(se_results, 1):
                status = "✓" if r["answered"] else "✗"
                site_label = "SO" if r["site"] == "stackoverflow" else "EE"
                print(f"  {i}. [{site_label}] {status} (score:{r['score']:>3})  {r['title']}")
                print(f"      🔗 {r['link']}")
                if r.get("answer_content"):
                    ans = r["answer_content"]
                    label = "Accepted" if ans["is_accepted"] else "Top ans"
                    preview = ans["body"][:200].replace("\n", " ")
                    print(f"      ↳ {label} (score:{ans['score']}): {preview}...")
                print()

        # ── GitHub ────────────────────────────────────────────────
        gh_results = [r for r in results if r.get("site") == "github"]
        if gh_results:
            print(f"  ── GitHub Issues ({len(gh_results)}) ────────────────────────────────────")
            for i, r in enumerate(gh_results, 1):
                state = "✓ closed" if r.get("state") == "closed" else "○ open"
                print(f"  {i}. [{r['repo_label']}] {state} 👍{r['reactions']} 💬{r['comments']}")
                print(f"     {r['title']}")
                print(f"     🔗 {r['link']}")
                if r.get("body_preview"):
                    preview = r["body_preview"][:150].replace("\n", " ")
                    print(f"     ↳ {preview}...")
                print()

        # ── Reddit ────────────────────────────────────────────────
        rd_results = [r for r in results if r.get("site") == "reddit"]
        if rd_results:
            print(f"  ── Reddit ({len(rd_results)}) ─────────────────────────────────────────")
            for i, r in enumerate(rd_results, 1):
                has_comments = "✓" if r.get("answer_count", 0) > 0 else "○"
                print(f"  {i}. [r/{r.get('subreddit','embedded')}] {has_comments} ⬆{r.get('upvotes',0)} 💬{r.get('answer_count',0)}")
                print(f"     {r['title']}")
                print(f"     🔗 {r['link']}")
                if r.get("body_preview"):
                    preview = r["body_preview"][:150].replace("\n", " ")
                    print(f"     ↳ {preview}...")
                print()

        # ── Vendor KB ─────────────────────────────────────────────
        kb_results = [r for r in results if r.get("site") == "vendor_kb"]
        if kb_results:
            print(f"  ── Vendor KB ({len(kb_results)}) ──────────────────────────────────────")
            for r in kb_results:
                print(f"  → {r['title']}")
                print(f"     🔗 {r['link']}")
            print()

        # ── AI SUMMARY ────────────────────────────────────────────
        # This is the "one tab" feature — instead of opening 15 browser tabs,
        # we synthesize all results into a single actionable recommendation
        print(f"  ── 🤖 WHAT TO DO ─────────────────────────────────────────")
        print(generate_action_summary(query, results, vendor_tip))
        print()
        time.sleep(1)
