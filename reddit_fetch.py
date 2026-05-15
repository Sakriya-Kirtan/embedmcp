# reddit_fetch.py — v2
# Key fix: added relevance filtering so "STM32H743 uart pins" doesn't return
# results about STM32H750 or STM32L053 — wrong chip, wrong query.

import sys
import re
import time
import requests

HEADERS = {
    "User-Agent": "embedmcp/0.1 embedded-systems-search (educational project)",
    "Accept": "application/json",
}

EMBEDDED_SUBREDDITS = [
    "embedded", "electronics", "stm32", "esp32",
    "raspberry_pi", "FPGA", "arduino", "rfelectronics",
]

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"

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


# ---------------------------------------------------------------------------
# Relevance scoring — same logic as github_fetch.py
# ---------------------------------------------------------------------------

def relevance_score(title, query):
    """
    Word overlap score between query and result title.
    Returns 0.0–1.0. Higher = more relevant.
    
    Threshold: 0.25 — requires at least 1 in 4 query words to match.
    Lower than GitHub (0.2) because Reddit titles are more verbose.
    """
    stop = {
        'the','a','an','is','in','on','at','to','for','of','and','or',
        'with','not','it','this','that','how','what','why','when','where',
        'are','was','were','be','been','have','has','do','does','did',
        'i','my','me','we','our','you','your','can','get','got','use',
        'using','used','need','want','via','from','into','also','just',
        'stm32','esp32','hal','rtos','freertos','arduino','pico','rp2040',
    }

    q_words = set(re.sub(r'[^a-z0-9]', ' ', query.lower()).split()) - stop
    t_words = set(re.sub(r'[^a-z0-9]', ' ', title.lower()).split()) - stop
    if not q_words:
        return 0.0
    overlap = len(q_words & t_words) / len(q_words)
    return overlap


def _filter_by_relevance(results, query, threshold=0.25):
    """
    Removes results whose title doesn't sufficiently overlap with the query.
    This stops "STM32H743 uart pins" from returning STM32H750 or STM32L053 results.
    """
    filtered = []
    for r in results:
        score = relevance_score(r.get("title", ""), query)
        if score >= threshold:
            filtered.append(r)
        else:
            print(
                f"  [Reddit] Filtered out (score={score:.2f}): {r.get('title','')[:60]}",
                file=sys.stderr
            )
    return filtered


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

def search_reddit(query, max_results=5):
    subreddit_filter = " OR ".join([f"subreddit:{s}" for s in EMBEDDED_SUBREDDITS[:4]])
    full_query = f"{query} ({subreddit_filter})"

    params = {
        "q": full_query,
        "sort": "relevance",
        "limit": max_results + 5,   # fetch extra, filter will reduce
        "type": "link",
        "t": "all"
    }

    try:
        response = requests.get(REDDIT_SEARCH_URL, params=params, headers=HEADERS, timeout=8)
        if response.status_code == 429:
            print("  [Reddit] Rate limited", file=sys.stderr)
            return []
        response.raise_for_status()
        data = response.json()
        posts = data.get("data", {}).get("children", [])

        results = []
        for post in posts:
            p = post.get("data", {})
            score = p.get("score", 0)
            num_comments = p.get("num_comments", 0)
            if score < 1 and num_comments < 2:
                continue
            body = p.get("selftext", "") or ""
            if len(body) > 400:
                body = body[:400] + "..."
            subreddit = p.get("subreddit", "")
            results.append({
                "title":        p.get("title", ""),
                "link":         f"https://reddit.com{p.get('permalink', '')}",
                "body_preview": body,
                "score":        score,
                "answered":     num_comments > 0,
                "answer_count": num_comments,
                "tags":         [subreddit],
                "site":         "reddit",
                "question_id":  p.get("id"),
                "subreddit":    subreddit,
                "repo_label":   f"r/{subreddit}",
                "source":       "reddit",
                "upvotes":      score,
                "comments":     num_comments,
            })

        results.sort(key=lambda x: x["score"] + x["answer_count"], reverse=True)
        return results[:max_results]

    except Exception as e:
        print(f"  [Reddit] Error: {e}", file=sys.stderr)
        return []


def search_subreddit(subreddit, query, max_results=3):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "restrict_sr": "true",
        "sort": "relevance",
        "limit": max_results + 3,
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
                "title":        p.get("title", ""),
                "link":         f"https://reddit.com{p.get('permalink', '')}",
                "body_preview": body,
                "score":        p.get("score", 0),
                "answered":     p.get("num_comments", 0) > 0,
                "answer_count": p.get("num_comments", 0),
                "tags":         [subreddit],
                "site":         "reddit",
                "question_id":  p.get("id"),
                "subreddit":    subreddit,
                "repo_label":   f"r/{subreddit}",
                "source":       "reddit",
                "upvotes":      p.get("score", 0),
                "comments":     p.get("num_comments", 0),
            })

        results.sort(key=lambda x: x["score"] + x["answer_count"], reverse=True)
        return results[:max_results]

    except Exception as e:
        print(f"  [Reddit] Subreddit search error: {e}", file=sys.stderr)
        return []

def search_reddit_for_vendor(query, vendor_key=None, max_results=3):
    print(f"  [Reddit] Searching...", file=sys.stderr)

    if vendor_key and vendor_key in VENDOR_SUBREDDITS:
        primary_sub = VENDOR_SUBREDDITS[vendor_key][0]
        print(f"  [Reddit] Targeting r/{primary_sub}", file=sys.stderr)
        results = search_subreddit(primary_sub, query, max_results=max_results + 3)
    else:
        results = search_reddit(query, max_results=max_results + 3)

    results = search_subreddit(primary_sub, query, max_results=max_results + 3)
    results = _filter_by_relevance(results, query, threshold=0.15)

    # Fallback AFTER filtering — if still not enough, try the broader embedded sub

    results = search_subreddit(primary_sub, query, max_results=max_results + 3)
    results = _filter_by_relevance(results, query, threshold=0.15)
    if len(results) < 2 and VENDOR_SUBREDDITS.get(vendor_key, [None])[0] != "embedded":
        time.sleep(0.5)   # add this
        extra = search_subreddit("embedded", query, max_results=max_results + 3)
        extra = _filter_by_relevance(extra, query, threshold=0.15)
        results.extend(extra)

    print(f"  [Reddit] {len(results)} posts after relevance filter", file=sys.stderr)
    return results[:max_results]

def search_reddit(query, max_results=5):
    # Try subreddit:embedded first as the broadest relevant community
    results = search_subreddit("embedded", query, max_results=max_results + 3)
    
    # Also try electronics for hardware-heavy queries
    extra = search_subreddit("electronics", query, max_results=max_results + 3)
    results.extend(extra)
    
    # Deduplicate by question_id
    seen = set()
    deduped = []
    for r in results:
        if r["question_id"] not in seen:
            deduped.append(r)
            seen.add(r["question_id"])
    
    deduped.sort(key=lambda x: x["score"] + x["answer_count"], reverse=True)
    return deduped[:max_results]

if __name__ == "__main__":
    test_cases = [
        # Should return relevant results
        ("STM32H743 uart pins", "st"),
        ("ESP32 WiFi drops connection", "espressif"),
        ("FreeRTOS task priority not working", None),
        # Should return few/no results after filtering
        ("STM32H743 I2C DMA stall", "st"),   # very specific — filter will be strict
    ]

    for query, vendor in test_cases:
        print(f"\n{'═'*65}")
        print(f"  QUERY: {query}  [vendor: {vendor or 'any'}]")
        print(f"{'═'*65}")

        results = search_reddit_for_vendor(query, vendor_key=vendor)

        if results:
            for i, r in enumerate(results, 1):
                score = relevance_score(r["title"], query)
                print(f"  {i}. [r/{r['subreddit']}] ⬆{r['upvotes']} 💬{r['comments']} (relevance={score:.2f})")
                print(f"     {r['title']}")
                print(f"     {r['link']}")
        else:
            print("  No results after filtering")
        time.sleep(1)  # be nice to Reddit's API