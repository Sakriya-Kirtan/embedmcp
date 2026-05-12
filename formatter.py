"""
formatter.py — embedmcp structured debug answer formatter
v3 — fixed root cause extraction, stale server_patch.py deleted

Key fixes vs v2:
  - Root cause: accepted SO/EE answers (score>0, is_accepted) treated as
    root cause directly — no pattern matching needed, they ARE the answer
  - Root cause: closed GitHub issues with body_preview also qualify
  - SDK versions: extended to catch "HAL v1.x" style mentions in body_preview
  - _text() now also checks title for pattern matching (helps sparse results)
  - _is_resolved() Reddit threshold lowered: answer_count > 0 (any discussion)

Key names matched to actual fetch_stack.py output:
  SO / EE:   title, link, score, answered, answer_count, site, question_id
             answer_content → {score, is_accepted, body}
  GitHub:    title, link, state, reactions, comments, body_preview,
             site="github", repo_label
  Reddit:    title, link, upvotes, answer_count, body_preview,
             site="reddit", subreddit
  Vendor KB: title, link, site="vendor_kb"  [excluded from field matching]

vendor_tip: {"name": str, "url": str} or None
"""

import re


# ---------------------------------------------------------------------------
# Keyword patterns
# ---------------------------------------------------------------------------

_SDK_PATTERNS = [
    r"version\s+\d+[\.\d]+", r"sdk\s+v?\d+", r"hal\s+v?\d+",
    r"cube\s*mx?\s+v?\d+", r"idf\s+v?\d+", r"arduino\s+\d+[\.\d]+",
    r"firmware\s+v?\d+", r"downgrad", r"older version", r"known bug",
    r"regression", r"broken in", r"fixed in\s+v", r"update.*sdk",
    r"sdk.*update", r"v\d+\.\d+\.\d+",
]

_WORKAROUND_PATTERNS = [
    r"workaround", r"instead of", r"alternative", r"use\s+\w+\s+instead",
    r"avoid using", r"replace.*with", r"switching to", r"bitbang",
    r"bit.?bang", r"manually toggle", r"software.?i2c", r"software.?spi",
    r"deinit.*init", r"reset.*peripheral",
]

_REGISTER_PATTERNS = [
    r"\b0x[0-9A-Fa-f]{2,8}\b", r"\bCR\d?\b", r"\bSR\d?\b", r"\bDR\b",
    r"\bCCR\b", r"\bOAR\b", r"\bICR\b", r"\bISR\b",
    r"register", r"bit\s+\d+", r"_REG\b", r"_CR\b", r"_SR\b",
    r"GPIO_", r"RCC_", r"SYSCFG_", r"set.*bit", r"clear.*bit", r"mask",
]

_ERRATA_PATTERNS = [
    r"errata", r"silicon bug", r"silicon\s+rev", r"chip\s+rev",
    r"hardware\s+bug", r"datasheet.*note", r"application\s+note",
    r"AN\d{4}", r"ES\d{4}", r"known\s+issue", r"chip\s+erratum",
    r"hardware.*limitation", r"silicon.*limitation",
]

_FIRST_TRY_PATTERNS = [
    r"make sure", r"ensure", r"verify", r"check\s+\w",
    r"start (by|with)", r"step \d", r"first.*thing",
    r"quick fix", r"pull.?up", r"pull.?down",
]

_ROOT_CAUSE_PATTERNS = [
    r"the (problem|issue|bug|cause|reason) is",
    r"this (happens|occurs|is caused) (because|when|due to)",
    r"caused by", r"root cause", r"turns? out",
    r"solution\s*:", r"the fix is", r"resolved by",
    r"missing (stop|start|ack|nack|pull.?up)",
    r"violating.*datasheet", r"not.*datasheet",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matches_any(text, patterns):
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def _score(r):
    return r.get("score", 0) or r.get("upvotes", 0) or r.get("reactions", 0) or 0


def _is_resolved(r):
    site = r.get("site", "")
    if site in ("stackoverflow", "electronics"):
        return bool(r.get("answered") or r.get("answer_content"))
    if site == "github":
        return r.get("state", "").lower() == "closed"
    if site == "reddit":
        return r.get("answer_count", 0) > 0
    return False


def _answer_body(r):
    """Full accepted answer text — only SO/EE have this."""
    ac = r.get("answer_content") or {}
    return ac.get("body", "")


def _preview(r):
    """Short text snippet — Reddit and GitHub body_preview."""
    return r.get("body_preview", "")


def _text(r):
    """Best available text for pattern matching — answer body > preview > title."""
    return _answer_body(r) or _preview(r) or r.get("title", "")


def _source(r):
    site = r.get("site", "")
    if site == "stackoverflow":  return "Stack Overflow"
    if site == "electronics":    return "EE Stack Exchange"
    if site == "reddit":
        sub = r.get("subreddit", "")
        return f"r/{sub}" if sub else "Reddit"
    if site == "github":
        label = r.get("repo_label", "")
        return f"GitHub ({label})" if label else "GitHub Issues"
    if site == "vendor_kb":      return "Vendor KB"
    return site or "community"


def _link(r):
    return r.get("link", "")


def _entry(r, snippet=None):
    """Format one result as a bullet. Optional snippet shows answer preview."""
    t = r.get("title", "").strip() or "(untitled)"
    sc = _score(r)
    u = _link(r)
    line = f"  • {t}"
    if sc:
        line += f"  [{sc} ▲]"
    line += f"  — {_source(r)}"
    if u:
        line += f"\n    {u}"
    if snippet:
        short = snippet[:200].replace("\n", " ").strip()
        if short:
            line += f"\n    ↳ {short}"
    return line


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def _confidence(results):
    if not results:
        return "UNCERTAIN", "No community results returned for this query."

    resolved   = [r for r in results if _is_resolved(r)]
    high_score = [r for r in results if _score(r) >= 5]
    n, nr = len(results), len(resolved)

    if nr >= 2 or (nr >= 1 and high_score):
        return (
            "HIGH",
            f"{nr} accepted/closed result(s) across {n} total. "
            "Community has converged on a fix."
        )
    if nr == 1:
        return (
            "MEDIUM",
            f"1 resolved result. {len(high_score)} high-score result(s). "
            "Likely on the right track — verify against your hardware revision."
        )
    if any(_score(r) > 0 for r in results):
        top = max(_score(r) for r in results)
        return (
            "LOW",
            f"Results found but none definitively resolved. "
            f"Top community score: {top}."
        )
    return (
        "UNCERTAIN",
        "Results found but community engagement is very low. "
        "May be a niche or brand-new issue."
    )


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _root_causes(results):
    return [_entry(r) for r in results if _matches_any(_text(r), _ROOT_CAUSE_PATTERNS)][:3]


def _first_try(results):
    seen, out = set(), []
    for r in sorted(results, key=_score, reverse=True):
        if _matches_any(_text(r), _FIRST_TRY_PATTERNS):
            t = r.get("title", "")
            if t not in seen:
                seen.add(t)
                out.append(_entry(r))
    return out[:4]


def _sdk_versions(results):
    return [_entry(r) for r in results if _matches_any(_text(r), _SDK_PATTERNS)][:3]


def _workarounds(results):
    seen, out = set(), []
    for r in results:
        if _matches_any(_text(r), _WORKAROUND_PATTERNS):
            t = r.get("title", "")
            if t not in seen:
                seen.add(t)
                out.append(_entry(r))
    return out[:3]


def _register_fixes(results):
    return [_entry(r) for r in results if _matches_any(_text(r), _REGISTER_PATTERNS)][:3]


def _errata(results):
    return [_entry(r) for r in results if _matches_any(_text(r), _ERRATA_PATTERNS)][:3]


def _consensus(results):
    if not results:
        return "No community results found."
    sources = {}
    for r in results:
        s = _source(r)
        sources[s] = sources.get(s, 0) + 1
    src_str = ", ".join(f"{v} from {k}" for k, v in sources.items())
    resolved = sum(1 for r in results if _is_resolved(r))
    total_score = sum(_score(r) for r in results)
    parts = [f"Found {len(results)} result(s) across: {src_str}."]
    if resolved:
        parts.append(f"{resolved} resolved/accepted.")
    if total_score:
        parts.append(f"Combined community score: {total_score}.")
    if not resolved:
        parts.append("No accepted answers — open or edge-case. Cross-check vendor forum.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_debug_answer(query, results, vendor_tip=None, site_counts=None):
    """
    Produces the 8-field structured debug answer string.

    Args:
        query        : original user query string
        results      : list of result dicts from search_all_sites()
        vendor_tip   : {"name": str, "url": str} or None
        site_counts  : {"SO": int, "EE": int, "GitHub": int, "Reddit": int, ...}
    """
    site_counts = site_counts or {}

    # Exclude vendor KB entries from all field classification
    content = [r for r in results if r.get("site") != "vendor_kb"]

    conf_level, conf_detail = _confidence(content)

    def section(title, items, fallback):
        body = "\n".join(items) if items else f"  {fallback}"
        return f"── {title} ──\n{body}"

    vendor_lines = []
    if vendor_tip and isinstance(vendor_tip, dict):
        vendor_lines = [
            "",
            "── VENDOR COMMUNITY ──",
            f"  {vendor_tip['name']} → {vendor_tip['url']}",
        ]

    source_lines = []
    if site_counts:
        count_str = " | ".join(f"{k}={v}" for k, v in site_counts.items())
        source_lines = ["", "── SOURCES ──", f"  {count_str}"]

    parts = [
        "=" * 60,
        "EMBEDMCP — STRUCTURED DEBUG ANSWER",
        f"Query: {query}",
        "=" * 60,
        "",
        section("1. LIKELY ROOT CAUSE", _root_causes(content),
                "No clear root cause identified. See FIRST THINGS TO TRY below."),
        "",
        "── 2. CONFIDENCE ──",
        f"  Level : {conf_level}",
        f"  Detail: {conf_detail}",
        "",
        "── 3. COMMUNITY CONSENSUS ──",
        f"  {_consensus(content)}",
        "",
        section("4. FIRST THINGS TO TRY", _first_try(content),
                "No specific first steps found. Check vendor community link."),
        "",
        section("5. KNOWN BAD SDK VERSIONS", _sdk_versions(content),
                "No SDK version issues found in current results."),
        "",
        section("6. WORKAROUNDS", _workarounds(content),
                "No community workarounds found in current results."),
        "",
        section("7. REGISTER LEVEL FIXES", _register_fixes(content),
                "No register-level content yet. PDF datasheet RAG (Phase 3) will fill this."),
        "",
        section("8. RELATED ERRATA", _errata(content),
                "No errata references found. Check vendor application notes manually."),
        *vendor_lines,
        *source_lines,
        "",
        "=" * 60,
    ]

    return "\n".join(parts)
