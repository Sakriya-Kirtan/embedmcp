# github_fetch.py
# Searches GitHub Issues from popular embedded MCU repositories.
#
# WHY GITHUB ISSUES?
# Stack Overflow has questions from developers learning.
# GitHub Issues has bug reports from developers shipping products.
# "STM32 HAL I2C DMA bug" — the fix is in a GitHub issue, not SO.
# This is data your competitors don't have.
#
# WHY FREE?
# GitHub API gives 5000 requests/hour with a free token.
# No credit card. No quota worries at MVP stage.

import sys
import re
import requests
import html
import os
from dotenv import load_dotenv
import time


load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# The repos we search — chosen because they have the most
# real-world embedded bug reports with actual fixes
GITHUB_REPOS = [
    # STM32
    {"repo": "STMicroelectronics/STM32CubeF4",  "vendor": "st",         "label": "STM32 F4 HAL"},
    {"repo": "STMicroelectronics/STM32CubeH7",  "vendor": "st",         "label": "STM32 H7 HAL"},
    # RP2040 / Raspberry Pi
    {"repo": "raspberrypi/pico-sdk",             "vendor": "raspberrypi","label": "RP2040 Pico SDK"},
    {"repo": "raspberrypi/pico-examples",        "vendor": "raspberrypi","label": "RP2040 Examples"},
    # Zephyr RTOS — cross-platform, used with nRF, STM32, ESP32
    {"repo": "zephyrproject-rtos/zephyr",        "vendor": "nordic",     "label": "Zephyr RTOS"},
    # ESP32
    {"repo": "espressif/esp-idf",                "vendor": "espressif",  "label": "ESP-IDF"},
    # Arduino core
    {"repo": "arduino/Arduino",                  "vendor": "arduino",    "label": "Arduino Core"},
    # FreeRTOS
    {"repo": "FreeRTOS/FreeRTOS-Kernel",         "vendor": None,         "label": "FreeRTOS Kernel"},
]

GITHUB_API_URL = "https://api.github.com"


def get_headers():
    """
    Returns auth headers for GitHub API.
    With a token: 5000 req/hour.
    Without: 60 req/hour (fine for testing, terrible for production).
    """
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def search_github_issues(query, vendor_key=None, max_results=5):
    """
    Searches GitHub Issues across embedded repos.
    
    query      : the search term e.g. "I2C DMA timeout"
    vendor_key : if detected, only search repos for that vendor first
    max_results: how many issues to return total
    
    WHY ISSUES NOT CODE?
    We search issues (bug reports + discussions) not source code.
    Issues have the problem description AND the fix in one thread.
    That's exactly what a developer debugging needs.
    """
    
    # If vendor detected, search their repos first
    # then fall back to all repos
    if vendor_key:
        target_repos = [r for r in GITHUB_REPOS if r["vendor"] == vendor_key]
        # Add FreeRTOS always — it's used across all vendors
        fallback = [r for r in GITHUB_REPOS if r["vendor"] is None]
        target_repos = target_repos + fallback
        if not target_repos:
            target_repos = GITHUB_REPOS
    else:
        target_repos = GITHUB_REPOS[:3]  # just the top 3 most popular repos if no vendor detected

    all_issues = []
    
    for repo_info in target_repos:
        repo = repo_info["repo"]
        label = repo_info["label"]
        
        print(f"  [GitHub] Searching {label}...", file=sys.stderr)
        
        # GitHub search API — searches issue title + body
        # "is:issue" means bug reports, not pull requests
        # "is:closed" often means the bug was fixed — most useful!
        # We search both open and closed
        search_query = f"{query} repo:{repo} is:issue"
        
        params = {
            "q": search_query,
            "sort": "reactions",    # most-reacted = most impactful bugs
            "order": "desc",
            "per_page": 3           # 3 per repo, we have many repos
        }
        
        try:
            response = requests.get(
                f"{GITHUB_API_URL}/search/issues",
                params=params,
                headers=get_headers(),
                timeout=5      # give up after 5 seconds — never hang forever
            )
            
            # GitHub returns 403 if rate limited, 422 if query invalid
            if response.status_code == 403:
                print(f"  [GitHub] Rate limited — add GITHUB_TOKEN to .env", file=sys.stderr)
                break
            if response.status_code == 422:
                print(f"  [GitHub] Invalid query for {repo}, skipping", file=sys.stderr)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            issues = data.get("items", [])
            
            for issue in issues:
                # Clean up the body — GitHub uses Markdown
                # We strip it to plain text for Claude
                body = issue.get("body", "") or ""
                body = re.sub(r'```[\s\S]*?```', '[code block]', body)  # replace code blocks
                body = re.sub(r'!\[.*?\]\(.*?\)', '', body)              # remove images
                body = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', body)   # links → text
                body = re.sub(r'#{1,6}\s', '', body)                     # headers
                body = re.sub(r'\n{3,}', '\n\n', body)                  # blank lines
                body = body.strip()
                
                # Truncate body — just enough for Claude to understand the issue
                if len(body) > 500:
                    body = body[:500] + "... [see full issue at link]"
                
                state = issue.get("state", "open")
                reactions = issue.get("reactions", {}).get("total_count", 0)
                comments = issue.get("comments", 0)
                
                all_issues.append({
                    "title": html.unescape(issue.get("title", "")),
                    "link": issue.get("html_url", ""),
                    "body_preview": body,
                    "state": state,                  # open or closed
                    "score": reactions + comments,   # proxy for importance
                    "reactions": reactions,
                    "comments": comments,
                    "repo": repo,
                    "repo_label": label,
                    "answered": state == "closed",   # closed = likely resolved
                    "answer_count": comments,
                    "tags": [],
                    "site": "github",
                    "question_id": issue.get("number"),  # issue number
                    "source": "github"
                })
                
        except requests.exceptions.RequestException as e:
            print(f"  [GitHub] Error searching {repo}: {e}", file=sys.stderr)
            continue
        time.sleep(0.5)    # 500ms between requests — GitHub's secondary rate limit

    
    # Sort by engagement score — most reactions + comments first
    all_issues.sort(key=lambda x: x["score"], reverse=True)
    
    # Deduplicate by issue URL
    seen = set()
    deduped = []
    for issue in all_issues:
        if issue["link"] not in seen:
            deduped.append(issue)
            seen.add(issue["link"])
    
    return deduped[:max_results]


def format_github_results(issues):
    """
    Formats GitHub issues into readable text for Claude.
    Same format as Stack Exchange results so Claude can mix them.
    """
    if not issues:
        return ""
    
    output = f"\nGitHub Issues ({len(issues)} results):\n"
    output += "-" * 40 + "\n"
    
    for i, issue in enumerate(issues, 1):
        state_label = "CLOSED ✓" if issue["state"] == "closed" else "OPEN"
        output += f"{i}. [{issue['repo_label']}] {issue['title']}\n"
        output += f"   State: {state_label} | Reactions: {issue['reactions']} | Comments: {issue['comments']}\n"
        output += f"   URL: {issue['link']}\n"
        if issue.get("body_preview"):
            output += f"   Preview: {issue['body_preview'][:200]}\n"
        output += "\n"
    
    return output


if __name__ == "__main__":
    
    test_queries = [
        ("STM32 I2C DMA timeout", "st"),
        ("ESP32 WiFi drops", "espressif"),
        ("FreeRTOS task stack overflow", None),
        ("RP2040 SPI DMA", "raspberrypi"),
    ]
    
    for query, vendor in test_queries:
        print("\n" + "═" * 65)
        print(f"  QUERY: {query}  [vendor: {vendor or 'any'}]")
        print("═" * 65)
        
        issues = search_github_issues(query, vendor_key=vendor, max_results=5)
        
        if issues:
            for i, issue in enumerate(issues, 1):
                state = "✓" if issue["state"] == "closed" else "○"
                print(f"  {i}. {state} [{issue['repo_label']}] (👍{issue['reactions']} 💬{issue['comments']})")
                print(f"     {issue['title']}")
                print(f"     {issue['link']}")
                print()
        else:
            print("  No results found")