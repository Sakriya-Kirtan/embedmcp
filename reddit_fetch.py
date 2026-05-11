# reddit_fetch.py
# Searches Reddit WITHOUT the official API.
# Uses Reddit's own search endpoint which is publicly accessible.
# This is the same approach used by hundreds of open source tools.
# Free, no API key, no approval needed.
# Rate limit: be polite, 1 request per second max.

import sys
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "embedmcp/0.1 embedded-systems-search (educational project)",
    "Accept": "application/json",
}

# Subreddits most relevant to embedded systems
EMBEDDED_SUBREDDITS = [
    "embedded",
    "electronics", 
    "stm32",
    "esp32",
    "raspberry_pi",
    "FPGA",
    "arduino",
    "rfelectronics",
]

# Reddit's JSON API — works without auth for read-only public data
# Adding .json to any Reddit URL returns JSON
REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"


def search_reddit(query, max_results=5):
    """
    Searches Reddit public posts using Reddit's .json endpoint.
    No API key needed — this is public data.
    
    WHY THIS WORKS:
    Reddit's website uses the same JSON API internally.
    Appending .json to search URLs returns structured data.
    This is read-only public data — no auth needed for public posts.
    """
    
    # Search across relevant subreddits
    subreddit_filter = " OR ".join([f"subreddit:{s}" for s in EMBEDDED_SUBREDDITS[:4]])
    full_query = f"{query} ({subreddit_filter})"
    
    params = {
        "q": full_query,
        "sort": "relevance",
        "limit": max_results + 3,  # fetch extra, filter low quality
        "type": "link",             # posts only, not comments
        "t": "all"                  # all time
    }
    
    try:
        response = requests.get(
            REDDIT_SEARCH_URL,
            params=params,
            headers=HEADERS,
            timeout=8
        )
        
        if response.status_code == 429:
            print(f"  [Reddit] Rate limited — skipping", file=sys.stderr)
            return []
            
        response.raise_for_status()
        data = response.json()
        
        posts = data.get("data", {}).get("children", [])
        results = []
        
        for post in posts:
            p = post.get("data", {})
            
            score = p.get("score", 0)
            num_comments = p.get("num_comments", 0)
            
            # Skip very low quality posts
            if score < 1 and num_comments < 2:
                continue
            
            # Get post text — selftext for text posts, title for links
            body = p.get("selftext", "") or ""
            if len(body) > 400:
                body = body[:400] + "..."
            
            subreddit = p.get("subreddit", "")
            
            results.append({
                "title": p.get("title", ""),
                "link": f"https://reddit.com{p.get('permalink', '')}",
                "body_preview": body,
                "score": score,
                "answered": num_comments > 0,
                "answer_count": num_comments,
                "tags": [subreddit],
                "site": "reddit",
                "question_id": p.get("id"),
                "subreddit": subreddit,
                "repo_label": f"r/{subreddit}",
                "source": "reddit",
                "upvotes": score,
                "comments": num_comments
            })
        
        # Sort by engagement
        results.sort(key=lambda x: x["score"] + x["answer_count"], reverse=True)
        return results[:max_results]
        
    except Exception as e:
        print(f"  [Reddit] Error: {e}", file=sys.stderr)
        return []


def search_subreddit(subreddit, query, max_results=3):
    """
    Searches a specific subreddit — more targeted than global search.
    Used when vendor is detected e.g. ESP32 → search r/esp32 directly.
    """
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "restrict_sr": "true",   # only this subreddit
        "sort": "relevance",
        "limit": max_results + 2,
        "t": "all"
    }
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=8)
        if response.status_code == 429:
            return []
        response.raise_for_status()
        data = response.json()
        posts = data.get("data", {}).get("children", [])
        
        results = []
        for post in posts:
            p = post.get("data", {})
            body = p.get("selftext", "") or ""
            if len(body) > 400:
                body = body[:400] + "..."
            results.append({
                "title": p.get("title", ""),
                "link": f"https://reddit.com{p.get('permalink', '')}",
                "body_preview": body,
                "score": p.get("score", 0),
                "answered": p.get("num_comments", 0) > 0,
                "answer_count": p.get("num_comments", 0),
                "tags": [subreddit],
                "site": "reddit",
                "question_id": p.get("id"),
                "subreddit": subreddit,
                "repo_label": f"r/{subreddit}",
                "source": "reddit",
                "upvotes": p.get("score", 0),
                "comments": p.get("num_comments", 0)
            })
        
        results.sort(key=lambda x: x["score"] + x["answer_count"], reverse=True)
        return results[:max_results]
        
    except Exception as e:
        print(f"  [Reddit] Subreddit search error: {e}", file=sys.stderr)
        return []


# Map vendor keys to their most relevant subreddits
VENDOR_SUBREDDITS = {
    "st":          ["stm32", "embedded"],
    "espressif":   ["esp32", "embedded"],
    "arduino":     ["arduino", "embedded"],
    "raspberrypi": ["raspberry_pi", "embedded"],
    "nordic":      ["embedded", "rfelectronics"],
    "nxp":         ["embedded"],
    "ti":          ["embedded", "electronics"],
    "renesas":     ["embedded"],
}


def search_reddit_for_vendor(query, vendor_key=None, max_results=3):
    """
    Smart Reddit search — uses vendor-specific subreddits when detected,
    falls back to broad embedded search otherwise.
    """
    print(f"  [Reddit] Searching...", file=sys.stderr)
    
    if vendor_key and vendor_key in VENDOR_SUBREDDITS:
        # Search the most relevant subreddit for this vendor
        primary_sub = VENDOR_SUBREDDITS[vendor_key][0]
        print(f"  [Reddit] Targeting r/{primary_sub}", file=sys.stderr)
        results = search_subreddit(primary_sub, query, max_results=max_results)
        
        # If not enough results, broaden to r/embedded
        if len(results) < 2:
            extra = search_subreddit("embedded", query, max_results=2)
            results.extend(extra)
    else:
        # No vendor — search across all embedded subreddits
        results = search_reddit(query, max_results=max_results)
    
    print(f"  [Reddit] Got {len(results)} posts", file=sys.stderr)
    return results[:max_results]


if __name__ == "__main__":
    test_queries = [
        ("STM32 I2C bus hanging", "st"),
        ("ESP32 WiFi drops connection", "espressif"),
        ("FreeRTOS task priority not working", None),
        ("MOSFET gate driver bootstrap", None),
    ]
    
    for query, vendor in test_queries:
        print(f"\n{'═'*65}")
        print(f"  QUERY: {query}  [vendor: {vendor or 'any'}]")
        print(f"{'═'*65}")
        
        results = search_reddit_for_vendor(query, vendor_key=vendor)
        
        if results:
            for i, r in enumerate(results, 1):
                print(f"  {i}. [r/{r['subreddit']}] ⬆{r['upvotes']} 💬{r['comments']}")
                print(f"     {r['title']}")
                print(f"     {r['link']}")
                if r.get("body_preview"):
                    preview = r["body_preview"][:120].replace("\n", " ")
                    print(f"     ↳ {preview}")
                print()
        else:
            print("  No results found")
        
        time.sleep(1)  # be polite — 1 second between queries