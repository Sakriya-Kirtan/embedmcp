# app.py
# Simple web demo for embedmcp.
#
# WHY FLASK?
# You already know Python. Flask is the simplest way to put
# a web interface on top of your existing fetch functions.
# No JavaScript framework, no build step, just Python + HTML.
#
# HOW IT WORKS:
# Browser → POST /search with query
# Flask calls search_all_sites() + search_github_issues()
# Returns JSON → browser displays results
#
# This is your DEMO page — the link you'll post on Reddit.


from flask import Flask, request, jsonify, render_template  # type: ignore[import]
from dotenv import load_dotenv
import os
import sys

load_dotenv(override=True)
from fetch_stack import search_all_sites, generate_action_summary
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    try:
        data = request.get_json()
        query = data.get("query", "").strip()
        
        if not query:
            return jsonify({"error": "No query provided"}), 400
        
        # search_all_sites already includes GitHub internally
        # DO NOT call search_github_issues separately — that was causing double search
        results, vendor_tip, site_counts = search_all_sites(query)
        action_summary = generate_action_summary(query, results, vendor_tip)
        se_results  = [r for r in results if r.get("site") in ("stackoverflow", "electronics")]
        gh_results  = [r for r in results if r.get("site") == "github"]
        kb_results  = [r for r in results if r.get("site") == "vendor_kb"]
        rr_results  = [r for r in results if r.get("site") == "reddit"]
        er_results  = [r for r in results if r.get("site") == "errata"]

        return jsonify({
          "stack_results": se_results,
          "github_results": gh_results,
          "kb_results": kb_results,
          "reddit_results": rr_results,
          "errata_results": er_results,
          "vendor_tip": vendor_tip,
          "counts": {
            "stackoverflow": site_counts.get("SO", 0),
            "electronics":   site_counts.get("EE", 0),
            "github":        site_counts.get("GitHub", 0),
            "reddit":        site_counts.get("Reddit", 0),
            "errata":        site_counts.get("Errata", 0),
            "vendor_kb":     site_counts.get("vendor_kb", 0),
          },
          "action_summary": action_summary
        })
    except Exception as e:
        print(f"Search error: {e}", file=__import__('sys').stderr)
        return jsonify({"error": str(e)}), 500



DEPRECATED_GROQ_MODELS = {"llama3-70b-8192", "llama3-70b"}
DEFAULT_GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def resolve_groq_model():
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    if model in DEPRECATED_GROQ_MODELS:
        fallback = os.getenv("GROQ_MODEL_FALLBACK", DEFAULT_GROQ_MODEL)
        if fallback != model:
            print(
                f"[Groq] WARNING: configured GROQ_MODEL {model} is deprecated and will be replaced by {fallback}",
                file=sys.stderr,
            )
            model = fallback
    return model


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    groq_url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
    groq_model = resolve_groq_model()
    groq_key = bool(os.getenv("GROQ_API_KEY") or os.getenv("GROG_API_KEY"))
    print(f"embedmcp web demo running at http://localhost:{port}")
    print(f"Using Groq endpoint: {groq_url} model: {groq_model} key set: {groq_key}")
    app.run(host="0.0.0.0", port=port, debug=False)
