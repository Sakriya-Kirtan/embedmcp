# renesas_kb.py
# Smart Renesas resource finder.
# Since Renesas KB is JS-rendered (can't scrape it),
# we use two approaches that actually work:
# 1. Search Stack Overflow with renesas-specific tags
# 2. Provide direct links to relevant KB category pages
# 3. Search GitHub for Renesas BSP/SDK issues

import sys
import requests
import os
from dotenv import load_dotenv

load_dotenv()
STACK_API_KEY = os.getenv("STACK_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Renesas GitHub repos — these ARE scrapeable and have real bug reports
RENESAS_GITHUB_REPOS = [
    {"repo": "renesas-rz/meta-renesas",      "label": "Renesas RZ Yocto BSP"},
    {"repo": "renesas-rz/rzg2_bsp_scripts",  "label": "Renesas RZ/G2 BSP"},
    {"repo": "renesas/fsp",                   "label": "Renesas FSP (RA Family)"},
    {"repo": "renesas-rz/rzg_optee-ta_fwu",  "label": "Renesas RZ/G OP-TEE"},
    {"repo": "renesas-rz/rzg_linux-4.19",    "label": "Renesas RZ/G Linux BSP"},
]

# Curated KB category links — real working URLs the user can click
# These are the actual category pages (not JS-gated article lists)
RENESAS_KB_LINKS = {
    "rzg": [
        {"title": "RZ/G Family Knowledge Base", "url": "https://en-support.renesas.com/knowledgeBase/category/31243/subcategory/31245"},
        {"title": "RZ Family BSP / Linux Support", "url": "https://en-support.renesas.com/knowledgeBase/category/31243"},
    ],
    "ra": [
        {"title": "RA Family Knowledge Base", "url": "https://en-support.renesas.com/knowledgeBase/category/31240"},
        {"title": "RA FSP Knowledge Base", "url": "https://en-support.renesas.com/knowledgeBase/category/31087/subcategory/31090"},
    ],
    "rx": [
        {"title": "RX Family Knowledge Base", "url": "https://en-support.renesas.com/knowledgeBase/category/31241"},
    ],
    "rl78": [
        {"title": "RL78 Family Knowledge Base", "url": "https://en-support.renesas.com/knowledgeBase/category/31242"},
    ],
}


def detect_renesas_family(query):
    """Detect which Renesas family the query is about."""
    q = query.lower()
    if any(k in q for k in ["rzg", "rz/g", "rzg2", "rzg3"]):
        return "rzg"
    elif any(k in q for k in ["rzv", "rz/v"]):
        return "rzg"  # same category
    elif any(k in q for k in ["ra4", "ra6", "ra8", " ra "]):
        return "ra"
    elif "rx" in q:
        return "rx"
    elif "rl78" in q:
        return "rl78"
    return "rzg"  # default for generic Renesas queries


def search_renesas_github(query, max_results=3):
    """Search Renesas GitHub repos for relevant issues."""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    all_issues = []

    for repo_info in RENESAS_GITHUB_REPOS[:3]:
        repo = repo_info["repo"]
        search_q = f"{query} repo:{repo} is:issue"
        try:
            response = requests.get(
                "https://api.github.com/search/issues",
                params={"q": search_q, "sort": "reactions", "per_page": 2},
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                items = response.json().get("items", [])
                for item in items:
                    all_issues.append({
                        "title": item.get("title", ""),
                        "link": item.get("html_url", ""),
                        "body_preview": (item.get("body", "") or "")[:300],
                        "state": item.get("state", "open"),
                        "reactions": item.get("reactions", {}).get("total_count", 0),
                        "comments": item.get("comments", 0),
                        "repo_label": repo_info["label"],
                        "answered": item.get("state") == "closed",
                        "answer_count": item.get("comments", 0),
                        "score": 0,
                        "tags": ["renesas"],
                        "site": "github",
                        "question_id": item.get("number"),
                        "source": "github"
                    })
        except Exception as e:
            print(f"  [Renesas GitHub] Error: {e}", file=sys.stderr)

        import time
        time.sleep(0.3)

    all_issues.sort(key=lambda x: x["reactions"] + x["comments"], reverse=True)
    return all_issues[:max_results]


def get_renesas_resources(query):
    """
    Main function — returns Renesas-specific results:
    1. GitHub issues from Renesas repos
    2. Curated KB category links for the right family
    """
    family = detect_renesas_family(query)
    print(f"  [Renesas] Detected family: {family}", file=sys.stderr)

    # Search Renesas GitHub repos
    github_results = search_renesas_github(query)
    print(f"  [Renesas] Found {len(github_results)} GitHub issues", file=sys.stderr)

    # Get curated KB links for this family
    kb_links = RENESAS_KB_LINKS.get(family, RENESAS_KB_LINKS["rzg"])
    kb_results = [{
        "title": link["title"],
        "link": link["url"],
        "body_preview": f"Official Renesas {family.upper()} knowledge base — search for '{query}' here",
        "source": "renesas_kb",
        "answered": True,
        "answer_count": 0,
        "score": 0,
        "tags": ["renesas"],
        "site": "vendor_kb",
        "question_id": None,
        "repo_label": "Renesas KB"
    } for link in kb_links]

    return github_results + kb_results


if __name__ == "__main__":
    import time
    test_queries = [
        "RZG3E camera interface MIPI CSI",
        "RZG2M secure boot trusted firmware",
        "RA6M5 USB device CDC",
    ]

    for query in test_queries:
        print(f"\n{'═'*65}")
        print(f"  QUERY: {query}")
        print(f"{'═'*65}")
        results = get_renesas_resources(query)
        for i, r in enumerate(results, 1):
            state = "✓" if r.get("answered") else "○"
            print(f"  {i}. {state} [{r.get('repo_label','Renesas')}]")
            print(f"     {r['title']}")
            print(f"     {r['link']}")
            if r.get("body_preview"):
                print(f"     ↳ {r['body_preview'][:150]}")
            print()
        time.sleep(0.5)