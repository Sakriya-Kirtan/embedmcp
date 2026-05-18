# Replacement for generate_action_summary() and _is_debug_query() in fetch_stack.py
#
# Key changes:
#   - Datasheet/pin queries now get a direct Groq answer from training knowledge
#     instead of a useless "no results found" message
#   - Debug queries with no community results also get a Groq answer
#   - Groq is only called when it adds value — not as a fallback to nothing
#   - Added GROQ_API_KEY check with clear error message


import os
import requests as _requests


# ---------------------------------------------------------------------------
# Query intent — more granular than before
# ---------------------------------------------------------------------------

_DATASHEET_SIGNALS = [
    "what are", "which pin", "pinout", "pin map", "pin number",
    "where is pin", "how to configure", "what is the address",
    "register address", "base address", "memory map", "alternate function",
    "datasheet", "reference manual", "schematic", "footprint",
    "uart pins", "i2c pins", "spi pins", "can pins", "gpio pin",
    "alternate function", "af mapping", "port mapping",
]

_DEBUG_SIGNALS = [
    "not working", "hang", "hanging", "stuck", "freeze", "crash", "fail",
    "broken", "bug", "issue", "problem", "error", "wrong value", "no data",
    "timeout", "brownout", "reset", "dma", "interrupt", "callback",
    "stall", "hal_busy", "hardfault", "overrun", "noise", "corrupt",
    "hal_error", "hal_timeout", "never fires", "not triggered", "stops after",
    "blocked", "latch", "endless", "no callback", "silent failure",
    "never recovers", "not triggered", "busy", "hal busy", "never called",
    "wrong order", "abort", "intermittent", "random", "second start",
]


def _query_intent(query):
    """
    Returns:
        'datasheet'  — pin lookup, configuration, memory map query
        'debug'      — bug, hang, wrong value, crash query  
        'general'    — ambiguous, treat as general search
    """
    q = query.lower()
    if any(s in q for s in _DATASHEET_SIGNALS):
        return 'datasheet'
    if any(s in q for s in _DEBUG_SIGNALS):
        return 'debug'
    return 'general'


def _is_debug_query(query):
    """Kept for backward compatibility with search_all_sites()."""
    return _query_intent(query) == 'debug'


# ---------------------------------------------------------------------------
# groq API call
# ---------------------------------------------------------------------------

def _call_groq(system_prompt, user_prompt, max_tokens=600):
    api_key = os.getenv("GROQ_API_KEY", os.getenv("GROG_API_KEY", ""))
    if not api_key:
        print("  [Groq] GROQ_API_KEY not set in .env — skipping synthesis",
              file=__import__('sys').stderr)
        return None

    groq_url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")

    # Prefer an OpenAI-compatible provider/model by default that your key can access.
    model_name = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    deprecated_models = {"llama3-70b-8192", "llama3-70b"}
    if model_name in deprecated_models:
        fallback_model = os.getenv("GROQ_MODEL_FALLBACK", "meta-llama/llama-4-scout-17b-16e-instruct")
        print(
            f"  [Groq] configured model {model_name} is deprecated; using fallback {fallback_model}",
            file=__import__('sys').stderr
        )
        model_name = fallback_model

    # If using Groq's native API (non-openai path) it expects bare model names.
    # When calling the OpenAI-compatible endpoint keep the provider/model form.
    if "/openai/" not in groq_url and "/" in model_name:
        model_name = model_name.split("/", 1)[1]
    print(f"  [Groq] using endpoint {groq_url} model={model_name}",
          file=__import__('sys').stderr)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model_name,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }

    # Debug: print truncated payload for troubleshooting (redact long user content)
    try:
        import json as _json
        payload_preview = _json.dumps(payload)[:1000]
    except Exception:
        payload_preview = str(payload)[:1000]
    print(f"  [Groq] request payload (truncated): {payload_preview}",
          file=__import__('sys').stderr)

    try:
        response = _requests.post(groq_url, headers=headers, json=payload, timeout=15)
    except Exception as e:
        print(f"  [Groq] HTTP request failed ({groq_url}): {e}", file=__import__('sys').stderr)
        return None

    # If non-2xx, show status and response body to help debug 4xx/5xx errors
    if not response.ok:
        try:
            body = response.text
            body_json = response.json()
        except Exception:
            body = response.text if response is not None else '<unreadable response body>'
            body_json = None
        print(f"  [Groq] API call failed ({groq_url}): {response.status_code} {response.reason}",
              file=__import__('sys').stderr)
        print(f"  [Groq] response body: {body}", file=__import__('sys').stderr)

        # If model was decommissioned or not found, try a fallback model once
        error_code = None
        if isinstance(body_json, dict):
            error_code = body_json.get('error', {}).get('code')

        if error_code in ('model_decommissioned', 'model_not_found'):
            fallback = os.getenv('GROQ_MODEL_FALLBACK', 'meta-llama/llama-4-scout-17b-16e-instruct')
            print(f"  [Groq] detected model issue ({error_code}), retrying with fallback model {fallback}",
                  file=__import__('sys').stderr)
            # Prepare fallback payload respecting native vs openai endpoint form
            send_model = fallback
            if "/openai/" not in groq_url and "/" in send_model:
                send_model = send_model.split("/", 1)[1]
            payload['model'] = send_model
            try:
                retry_resp = _requests.post(groq_url, headers=headers, json=payload, timeout=15)
            except Exception as e:
                print(f"  [Groq] retry HTTP request failed: {e}", file=__import__('sys').stderr)
                return None

            if not retry_resp.ok:
                try:
                    rr_body = retry_resp.text
                except Exception:
                    rr_body = '<unreadable response body>'
                print(f"  [Groq] retry failed: {retry_resp.status_code} {retry_resp.reason}",
                      file=__import__('sys').stderr)
                print(f"  [Groq] retry response body: {rr_body}", file=__import__('sys').stderr)
                return None

            # Replace response with successful retry for downstream parsing
            response = retry_resp
        else:
            return None

    try:
        data = response.json()
    except Exception as e:
        print(f"  [Groq] failed parsing JSON response: {e}", file=__import__('sys').stderr)
        print(f"  [Groq] raw response: {response.text}", file=__import__('sys').stderr)
        return None

    # Support common chat completion response shapes.
    if isinstance(data, dict):
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if isinstance(choice.get("message"), dict):
                return choice["message"].get("content")
            return choice.get("text")
        if "completion" in data:
            return data["completion"]
        if "output" in data:
            output = data["output"]
            if isinstance(output, list) and output:
                first = output[0]
                if isinstance(first, dict):
                    return first.get("content") or first.get("text")
                return first
            return output
    return None


# ---------------------------------------------------------------------------
# Main action summary
# ---------------------------------------------------------------------------

def generate_action_summary(query, results, vendor_tip):
    """
    Three paths:
    
    1. DATASHEET QUERY (pin lookup, configuration)
       → Groq answers directly from its knowledge — it knows STM32 datasheets well.
       → Community sources won't have this; don't pretend they will.
    
    2. DEBUG QUERY with community results
       → Groq synthesizes errata + SO answer + GitHub fix into numbered steps.
    
    3. DEBUG QUERY with no community results  
       → Groq answers from training knowledge + flags it may be outdated.
    """
    intent = _query_intent(query)

    errata_hits = [r for r in results if r.get("site") == "errata"]
    se_hits     = [r for r in results if r.get("answer_content")]
    gh_hits     = [r for r in results if r.get("site") == "github" and r.get("state") == "closed"]

    has_community_results = bool(errata_hits or se_hits or gh_hits)

    # ── PATH 1: Datasheet/pin query ────────────────────────────────────────
    if intent == 'datasheet':
        system = (
            "You are an embedded systems engineer with expert knowledge of STM32 datasheets. "
            "When asked for UART/USART pin mappings for a specific STM32 part (for example, STM32H743), "
            "provide a complete, authoritative bullet list of all UART/USART instances and every valid "
            "pin pair option for TX/RX with their Alternate Function numbers (AFx). "
            "Format exactly as: '- <UART/USART>: <TX_pin>/<RX_pin> (AFx), [additional pin pairs if any]'. "
            "If pin availability depends on package or variant, state 'depends on package/variant' for that entry. "
            "Do NOT hallucinate: if you cannot be certain about a specific pin or AF, write 'unknown' for that entry. "
            "Prefer vendor KB or the official reference manual as the source and mention when the answer is taken from vendor KB. "
            "Be concise; no preamble or extra commentary."
        )
        
        user_prompt = query

        answer = _call_groq(system, user_prompt, max_tokens=1200)

        if answer:
            note = (
                "\n\n---\n"
                "_Note: This answer is from Groq's training knowledge of the datasheet. "
                "Always verify pin assignments in ST CubeMX or the official reference manual "
                "for your exact chip variant and package._"
            )
            return answer + note

        # Fallback if Groq unavailable
        return (
            f"  This looks like a datasheet/configuration question.\n"
            f"  embedmcp searches community forums for debugging problems — "
            f"pin assignments live in the datasheet.\n\n"
            f"  For STM32: open STM32CubeMX, select your chip, and check the pinout view.\n"
            f"  Reference manual: st.com → search '{query}' in documentation.\n"
            + (f"  Official forum: {vendor_tip['url']}" if vendor_tip else "")
        )

    # ── PATH 2: Debug query WITH community results ─────────────────────────
    if intent == 'debug' and has_community_results:
        context_parts = []

        for r in errata_hits[:2]:
            context_parts.append(
                f"SILICON ERRATA [{r.get('doc','?')} §{r.get('section','?')}] "
                f"Chip: {r.get('chip_label','?')}\n"
                f"Issue: {r.get('description','')}\n"
                f"Fix: {r.get('fix','')}\n"
                f"Affected: {r.get('affected_revisions','unknown')}"
            )

        for r in se_hits[:1]:
            ans = r["answer_content"]
            context_parts.append(
                f"COMMUNITY ANSWER (score {ans['score']}, "
                f"{'accepted' if ans['is_accepted'] else 'top'}):\n"
                f"{ans['body'][:800]}"
            )

        for r in gh_hits[:1]:
            preview = r.get("body_preview", "")[:400]
            context_parts.append(
                f"CONFIRMED GITHUB FIX ({r.get('repo_label','?')}, closed):\n"
                f"Title: {r['title']}\n{preview}"
            )

        context = "\n\n---\n\n".join(context_parts)

        system = (
            "Senior embedded engineer. Given errata/community sources, "
            "output numbered fix steps only, most likely first. "
            "Be specific: function names, register names, version numbers. "
            "Max 8 steps. No preamble."
        )

        user_prompt = (
            f"Problem: {query}\n\n"
            f"Sources:\n{context}\n\n"
            "What should the developer do? Numbered steps, most likely fix first."
        )

        answer = _call_groq(system, user_prompt, max_tokens=1200)
        if answer:
            return answer
    # ── PATH 3: Debug query OR general query with NO community results ─────
    if not has_community_results:
        system = (
            "You are a senior embedded Linux engineer specializing in Renesas RZ-family BSPs. "
            "Give a specific, actionable answer. No marketing language. No generic overviews. "
            "Include: exact kernel config options, device tree node examples, driver names, "
            "known gotchas, and which BSP version introduced the feature if relevant. "
            "Start with '⚠️ No live community results — answering from training knowledge.' "
            "Use numbered steps. Be terse and technical."
        )

        answer = _call_groq(system, query, max_tokens=1200)
        if answer:
            return answer

    # ── PATH 4: Debug query WITH community results but Groq unavailable ────
    if intent == 'debug' and has_community_results:
        pass  # falls through to mechanical summary below

    # ── Final fallback — Groq unavailable, nothing useful to show ────────
    SECTION_SEP = "\n── \n"
    lines = []

    if errata_hits:
        best = errata_hits[0]
        lines.append(f"  ⚡ Errata match [{best.get('doc','?')} §{best.get('section','?')}]:")
        lines.append(f"     {best.get('fix','')[:300]}")
        lines.append(f"     → {best.get('link','')}")

    if se_hits:
        best = se_hits[0]
        ans = best["answer_content"]
        lines.append(f"{SECTION_SEP}  ✅ Best answer (score {ans['score']}):")
        lines.append(f"     {ans['body'][:300].replace(chr(10), ' ')}...")
        lines.append(f"     → {best['link']}")

    if gh_hits:
        best = gh_hits[0]
        lines.append(f"{SECTION_SEP}  🐛 Confirmed fix ({best.get('repo_label','?')}, closed):")
        lines.append(f"     {best['title']} → {best['link']}")

    if not lines:
        if vendor_tip:
            lines.append(
                f"  No results found. Set GROQ_API_KEY in .env for AI-powered answers.\n"
                f"  Official forum: {vendor_tip['url']}"
            )
        
        else:
            lines.append(
                "  No community results found for this query.\n"
                "  Try rephrasing with specific chip names or symptoms (e.g. 'hang', 'not working')."
            )
    return "\n".join(lines)