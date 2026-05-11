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


from flask import Flask, request, jsonify, render_template_string  # type: ignore[import]
from flask_cors import CORS  # type: ignore[import]

from fetch_stack import search_all_sites
from github_fetch import search_github_issues
import os
app = Flask(__name__)
CORS(app)

# ── HTML template — inline so you only need one file ──────────
# We're keeping this simple on purpose. Clean, fast, mobile-friendly.
# No React, no Tailwind, no build step. Just works.

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>embedmcp — embedded systems search</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #e0e0e0; min-height: 100vh; }
  
  .header { padding: 48px 24px 32px; text-align: center; border-bottom: 1px solid #222; }
  .logo { font-size: 28px; font-weight: 600; color: #fff; letter-spacing: -0.5px; }
  .logo span { color: #4f8ef7; }
  .tagline { font-size: 14px; color: #888; margin-top: 8px; }
  .sources { display: flex; gap: 8px; justify-content: center; margin-top: 16px; flex-wrap: wrap; }
  .source-badge { font-size: 11px; padding: 3px 10px; border-radius: 20px; border: 1px solid #333; color: #999; }
  
  .search-box { max-width: 680px; margin: 40px auto; padding: 0 24px; }
  .search-row { display: flex; gap: 10px; }
  .search-input { flex: 1; padding: 12px 16px; font-size: 15px; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; color: #e0e0e0; outline: none; transition: border-color 0.15s; }
  .search-input:focus { border-color: #4f8ef7; }
  .search-input::placeholder { color: #555; }
  .search-btn { padding: 12px 24px; background: #4f8ef7; color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: background 0.15s; }
  .search-btn:hover { background: #3a7de8; }
  .search-btn:disabled { background: #333; color: #666; cursor: not-allowed; }
  
  .examples { max-width: 680px; margin: 0 auto 40px; padding: 0 24px; }
  .examples-label { font-size: 12px; color: #666; margin-bottom: 10px; }
  .example-chips { display: flex; gap: 8px; flex-wrap: wrap; }
  .chip { font-size: 12px; padding: 5px 12px; background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 20px; color: #aaa; cursor: pointer; transition: all 0.15s; }
  .chip:hover { border-color: #4f8ef7; color: #4f8ef7; }
  
  .results { max-width: 680px; margin: 0 auto; padding: 0 24px 60px; }
  .results-header { font-size: 13px; color: #666; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #1a1a1a; }
  .results-header strong { color: #aaa; }
  
  .vendor-tip { background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px; }
  .vendor-tip-icon { font-size: 18px; }
  .vendor-tip-text { font-size: 13px; color: #aaa; }
  .vendor-tip-link { color: #4f8ef7; text-decoration: none; }
  .vendor-tip-link:hover { text-decoration: underline; }

  .section-title { font-size: 11px; font-weight: 600; color: #555; letter-spacing: 0.08em; text-transform: uppercase; margin: 24px 0 12px; }

  .result-card { background: #1a1a1a; border: 1px solid #252525; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; transition: border-color 0.15s; }
  .result-card:hover { border-color: #333; }
  .result-card a { color: #e0e0e0; text-decoration: none; font-size: 14px; font-weight: 500; line-height: 1.4; display: block; margin-bottom: 6px; }
  .result-card a:hover { color: #4f8ef7; }
  .result-meta { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
  .badge-so { background: #1e2a1e; color: #5a9e5a; }
  .badge-ee { background: #1e1e2e; color: #5a7aae; }
  .badge-gh { background: #2a1e2a; color: #9e7aae; }
  .badge-kb { background: #2a2a1e; color: #ae9e5a; }
  .badge-answered { background: #1e2a1e; color: #5a9e5a; }
  .badge-open { background: #2a1e1e; color: #ae5a5a; }
  .score { font-size: 11px; color: #666; }
  .answer-preview { font-size: 12px; color: #777; margin-top: 8px; line-height: 1.5; border-left: 2px solid #2a2a2a; padding-left: 10px; }
  
  .kb-card { background: #1a1a14; border: 1px solid #2a2a1e; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; }
  .kb-card a { color: #ae9e5a; text-decoration: none; font-size: 13px; }
  .kb-card a:hover { text-decoration: underline; }

  .loading { text-align: center; padding: 40px; color: #555; font-size: 14px; }
  .loading-dots::after { content: ''; animation: dots 1.5s infinite; }
  @keyframes dots { 0%,20%{content:'.'} 40%{content:'..'} 60%,100%{content:'...'} }
  
  .error { background: #2a1a1a; border: 1px solid #4a2a2a; border-radius: 8px; padding: 16px; color: #ae5a5a; font-size: 14px; }
  .empty { text-align: center; padding: 40px; color: #555; font-size: 14px; }
</style>
</head>
<body>

<div class="header">
  <div class="logo">embed<span>mcp</span></div>
  <div class="tagline">AI-powered search for embedded systems developers</div>
  <div class="sources">
    <span class="source-badge">Stack Overflow</span>
    <span class="source-badge">EE Stack Exchange</span>
    <span class="source-badge">GitHub Issues</span>
    <span class="source-badge">Vendor Forums</span>
  </div>
</div>

<div class="search-box">
  <div class="search-row">
    <input class="search-input" id="q" type="text" placeholder="e.g. STM32 I2C bus hanging, ESP32 WiFi drops..." autocomplete="off" />
    <button class="search-btn" id="btn" onclick="doSearch()">Search</button>
  </div>
</div>

<div class="examples">
  <div class="examples-label">Try these</div>
  <div class="example-chips">
    <span class="chip" onclick="setQuery('STM32 I2C bus hanging')">STM32 I2C bus hanging</span>
    <span class="chip" onclick="setQuery('ESP32 WiFi drops connection')">ESP32 WiFi drops</span>
    <span class="chip" onclick="setQuery('FreeRTOS task priority not working')">FreeRTOS priority</span>
    <span class="chip" onclick="setQuery('MOSFET gate driver high side')">MOSFET gate driver</span>
    <span class="chip" onclick="setQuery('RP2040 SPI DMA transfer')">RP2040 SPI DMA</span>
    <span class="chip" onclick="setQuery('nRF52 BLE connection drops')">nRF52 BLE drops</span>
  </div>
</div>

<div class="results" id="results"></div>

<script>
const input = document.getElementById('q');
input.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

function setQuery(q) {
  input.value = q;
  doSearch();
}

async function doSearch() {
  const q = input.value.trim();
  if (!q) return;
  
  const btn = document.getElementById('btn');
  const results = document.getElementById('results');
  btn.disabled = true;
  btn.textContent = 'Searching...';
  results.innerHTML = '<div class="loading">Searching Stack Overflow, EE Stack Exchange, GitHub<span class="loading-dots"></span></div>';
  
  try {
    const res = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q })
    });
    const data = await res.json();
    renderResults(data, q);
  } catch(e) {
    results.innerHTML = '<div class="error">Search failed — make sure the server is running.</div>';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Search';
  }
}

function renderResults(data, query) {
  const results = document.getElementById('results');
  
  if (data.error) {
    results.innerHTML = `<div class="error">${data.error}</div>`;
    return;
  }
  
  const { stack_results, github_results, vendor_tip, counts } = data;
  const total = (stack_results?.length || 0) + (github_results?.length || 0);
  
  if (total === 0 && !vendor_tip) {
    results.innerHTML = '<div class="empty">No results found — try different keywords.</div>';
    return;
  }
  
  let html = '';
  
  // Summary
  html += `<div class="results-header">
    <strong>${total} results</strong> for "${query}" — 
    SO: ${counts?.stackoverflow || 0} · EE: ${counts?.electronics || 0} · GitHub: ${counts?.github || 0}
  </div>`;
  
  // Vendor tip
  if (vendor_tip) {
    html += `<div class="vendor-tip">
      <span class="vendor-tip-icon">🏭</span>
      <span class="vendor-tip-text">
        Official community: <strong>${vendor_tip.name}</strong> — 
        <a class="vendor-tip-link" href="${vendor_tip.url}" target="_blank">${vendor_tip.url}</a>
      </span>
    </div>`;
  }
  
  // Stack Exchange results
  if (stack_results?.length) {
    html += '<div class="section-title">Stack Overflow + EE Stack Exchange</div>';
    for (const r of stack_results) {
      const siteClass = r.site === 'stackoverflow' ? 'badge-so' : 'badge-ee';
      const siteLabel = r.site === 'stackoverflow' ? 'Stack Overflow' : 'EE Stack Exchange';
      const statusClass = r.answered ? 'badge-answered' : 'badge-open';
      const statusLabel = r.answered ? '✓ answered' : '○ open';
      
      html += `<div class="result-card">
        <a href="${r.link}" target="_blank">${r.title}</a>
        <div class="result-meta">
          <span class="badge ${siteClass}">${siteLabel}</span>
          <span class="badge ${statusClass}">${statusLabel}</span>
          <span class="score">score: ${r.score}</span>
          ${r.tags?.length ? `<span class="score">${r.tags.slice(0,3).join(', ')}</span>` : ''}
        </div>
        ${r.answer_content ? `<div class="answer-preview">${r.answer_content.body.substring(0, 300).replace(/</g,'&lt;').replace(/>/g,'&gt;')}...</div>` : ''}
      </div>`;
    }
  }
  
  // GitHub results
  if (github_results?.length) {
    html += '<div class="section-title">GitHub Issues</div>';
    for (const r of github_results) {
      const statusClass = r.state === 'closed' ? 'badge-answered' : 'badge-open';
      const statusLabel = r.state === 'closed' ? '✓ closed' : '○ open';
      html += `<div class="result-card">
        <a href="${r.link}" target="_blank">${r.title}</a>
        <div class="result-meta">
          <span class="badge badge-gh">${r.repo_label}</span>
          <span class="badge ${statusClass}">${statusLabel}</span>
          <span class="score">👍 ${r.reactions} · 💬 ${r.comments}</span>
        </div>
        ${r.body_preview ? `<div class="answer-preview">${r.body_preview.substring(0,300).replace(/</g,'&lt;').replace(/>/g,'&gt;')}...</div>` : ''}
      </div>`;
    }
  }
  
  // Vendor KB links
  const kb_results = (stack_results || []).filter(r => r.site === 'vendor_kb');
  if (kb_results.length) {
    html += '<div class="section-title">Vendor Knowledge Base</div>';
    for (const r of kb_results) {
      html += `<div class="kb-card"><a href="${r.link}" target="_blank">🔗 ${r.title}</a></div>`;
    }
  }
  
  results.innerHTML = html;
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

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
        
        # Split results by type for the frontend
        se_results  = [r for r in results if r.get("site") in ("stackoverflow", "electronics")]
        gh_results  = [r for r in results if r.get("site") == "github"]
        kb_results  = [r for r in results if r.get("site") == "vendor_kb"]
        
        return jsonify({
            "stack_results": se_results,
            "github_results": gh_results,
            "kb_results": kb_results,
            "vendor_tip": vendor_tip,
            "counts": site_counts
        })
        
    except Exception as e:
        print(f"Search error: {e}", file=__import__('sys').stderr)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"embedmcp web demo running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)