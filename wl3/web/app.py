
"""
Flask front end (presentation only).

Extracts the query and an anonymous session id from the HTTP request, calls
QueryEngine.search and returns JSON / HTML. No ranking, cache, Rocchio or
MMR logic lives here.

Endpoints
    GET  /                 search page
    GET  /api/search       ?q=...&mode=bm25&k=10&mmr=0|1
    POST /api/feedback     {"doc_id": 12}   mark a result relevant
    POST /api/reset        clear this browser session's feedback
    GET  /api/stats        cache / index statistics
"""

from __future__ import annotations

import html
import os
import uuid

from flask import Flask, jsonify, make_response, render_template_string, request

from wl3.engine.factory import build_engine
from wl3.engine.query_engine import QueryEngine, parse_ranking_mode
from wl3.engine.text import highlight, tokenize_query
from wl3.integration.worklet2_adapter import Worklet2Error

SESSION_COOKIE = "wl3_session"

_PAGE = """<!doctype html>
<html lang="en">
<head>
 <meta charset="utf-8">
 <meta name="viewport" content="width=device-width, initial-scale=1">
 <meta name="theme-color" content="#172b4d">
 <title>Mini Search Engine | COEP Technological University</title>
 <style>
  :root{color-scheme:light;--ink:#172033;--muted:#657188;--line:#e1e6ef;--surface:#fff;--page:#f4f6f9;--navy:#172b4d;--blue:#315fe8;--blue-soft:#edf2ff;--green:#187b59;--green-soft:#e8f7ef;--gold:#eab85b}
  *{box-sizing:border-box}
  body{margin:0;background:#f4f6f9;color:#202b3c;font-family:"Times New Roman",Times,serif;font-size:17px;line-height:1.6}
  .topbar{background:#fff;color:#172b4d;border-bottom:3px solid #172b4d;position:relative;overflow:hidden}
  .topbar:after{display:none}
  .topbar-inner{max-width:1180px;margin:auto;padding:1.1rem 2rem;display:flex;align-items:center;justify-content:space-between;gap:1.5rem;position:relative}
  .brand{display:flex;align-items:center;gap:1rem}
  .brand-mark{width:48px;height:48px;display:grid;place-items:center;background:#172b4d;color:#fff;border-radius:4px;font-weight:bold;font-size:20px;box-shadow:none}
  .brand-name{font-family:"Times New Roman",Times,serif;font-size:1.35rem;font-weight:bold;letter-spacing:.04em;color:#172b4d}
  .brand-caption{color:#596579;font-size:.95rem}
  .institution{display:flex;align-items:center;gap:1rem;text-align:right;position:relative}
  .institution-name{font-size:1.1rem;font-weight:bold;color:#172b4d;letter-spacing:0}
  .institution-caption{font-size:.9rem;color:#596579;letter-spacing:0}
  .coep-logo{width:76px;height:76px;object-fit:contain}
  main{max-width:1120px;margin:0 auto;padding:3rem 2rem 2.5rem}
  .intro{margin-bottom:1.7rem}
  .eyebrow{font-size:.9rem;font-weight:bold;letter-spacing:.08em;text-transform:uppercase;color:#52627a;margin-bottom:.4rem}
  h1{margin:0;color:#172b4d;font-family:"Times New Roman",Times,serif;font-size:2.8rem;line-height:1.2;font-weight:bold;letter-spacing:0}
  .intro p{margin:.7rem 0 0;color:#596579;font-size:1.1rem;max-width:750px}

  .search-panel{background:#fff;border:1px solid #e1e6ef;border-radius:12px;padding:1.2rem;box-shadow:0 8px 28px #172b4d0a}
  .search-form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.85rem}
  .query-wrap{display:flex;min-width:0;position:relative}
  .query-input{width:100%;min-width:0;padding:1rem 1.15rem;border:1px solid #dce3ef;border-radius:8px;color:var(--ink);font:inherit;background:#fff;transition:border .2s,box-shadow .2s}
  .query-input:focus,select:focus,input[type=number]:focus,button:focus-visible,a:focus-visible{outline:3px solid #315fe82b;outline-offset:2px;border-color:#8aa4ff}
  .search-button,.feedback-button,.reset-button{font:inherit;cursor:pointer;transition:transform .15s,background .15s,border-color .15s}
  .search-button{padding:.85rem 1.65rem;background:#172b4d;color:#fff;border:1px solid #172b4d;border-radius:8px;font-weight:bold;box-shadow:none}
  .search-button:hover{background:#243e66;transform:translateY(-1px)}
  .search-options{grid-column:1/-1;display:flex;align-items:end;gap:1.2rem;flex-wrap:wrap;padding:.35rem .15rem .1rem}
  .field{display:grid;gap:.4rem;color:var(--muted);font-size:.9rem;font-weight:bold}
  .field select,.field input[type=number]{min-height:2.7rem;padding:.55rem .75rem;border:1px solid #d5dce7;border-radius:7px;background:#fff;color:var(--ink);font:inherit}
  .field select{min-width:9rem}
  .field input[type=number]{width:6rem}
  .check-field{display:flex;align-items:center;gap:.55rem;min-height:2.7rem;color:#34415a;font-size:.95rem}
  .check-field input{width:1.05rem;height:1.05rem;accent-color:#172b4d}

  .notice,.error,.empty-state{padding:.9rem 1rem;border-radius:8px;margin:1rem 0}
  .notice{border:1px solid #f1d58d;background:#fff8e8;color:#765510}
  .error{border:1px solid #f0c2c2;background:#fff2f2;color:#8a2525}
  .empty-state{border:1px solid var(--line);background:#fff;color:var(--muted)}

  .section-heading{display:flex;justify-content:space-between;align-items:center;gap:1rem;margin:2.5rem 0 1rem}
  .section-heading h2{margin:0;color:var(--ink);font-size:1.5rem;font-weight:bold;letter-spacing:0}
  .result-count{color:var(--muted);font-size:.9rem;font-weight:bold;background:#e9edf5;border-radius:5px;padding:.3rem .65rem}
  .result-list{display:grid;gap:1rem}
  .result-card{background:#fff;border:1px solid #e1e6ef;border-radius:10px;padding:1.35rem 1.5rem;box-shadow:0 5px 18px #172b4d08;transition:box-shadow .18s,border-color .18s}
  .result-card:hover{box-shadow:0 9px 24px #172b4d10;border-color:#cbd5e5}
  .result-title{font-family:"Times New Roman",Times,serif;font-size:1.2rem;font-weight:bold;color:#1c4e80;text-decoration:none}
  .result-title:hover{text-decoration:underline}
  .result-url{overflow-wrap:anywhere;margin:.35rem 0 .75rem;color:var(--green);font-size:.95rem;font-weight:600}
  .snippet{margin:0;color:#3b465a;font-size:1.05rem;line-height:1.7}
  .snippet mark{background:#fff0bd;color:#4c3a0c;padding:.08em .2em;border-radius:3px}
  .result-meta{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;margin-top:1rem;padding-top:.85rem;border-top:1px solid #eef1f6;color:var(--muted);font-size:.9rem}
  .feedback-button,.reset-button{padding:.5rem .85rem;background:#fff;color:#30415f;border:1px solid #cbd5e5;border-radius:7px;font-size:.9rem;font-weight:bold}
  .feedback-button:hover,.reset-button:hover{background:var(--blue-soft);border-color:#c6d3ff}
  .feedback-button.marked{background:var(--green-soft);border-color:#bde7ce;color:var(--green);cursor:default}
  .feedback-status{font-size:.9rem;font-weight:bold;color:var(--green)}
  .reset-button{margin-top:1.2rem}
  .status{min-height:0;margin:.5rem 0 0;padding:0;color:var(--muted);font-size:.9rem}
  .status:empty{display:none}
  footer{max-width:1120px;margin:1.5rem auto 0;padding:1.2rem 2rem 2rem;border-top:1px solid #e2e7f0;color:#778197;font-size:.9rem}

  input,select,button,textarea{font-family:"Times New Roman",Times,serif}

  @media(max-width:650px){
   .topbar-inner{padding:1rem}
   .institution-name{font-size:.85rem}
   .institution-caption{font-size:.75rem}
   .coep-logo{width:54px;height:54px}
   main{padding:2rem 1rem}
   .search-form{grid-template-columns:1fr}
   .query-wrap{display:grid;grid-template-columns:minmax(0,1fr) auto}
   .search-button{padding:.75rem 1rem}
   .search-options{gap:.75rem}
   .section-heading{align-items:center}
   .result-card{padding:1rem}
   .result-meta{gap:.6rem}
   h1{font-size:2.2rem}
   footer{padding:1rem}
  }
 </style>
</head>
<body>
 <header class="topbar">
  <div class="topbar-inner">
   <div class="brand">
    

   <div class="institution" aria-label="COEP Technological University">
    <div class="institution-text">
     <div class="institution-name">COEP Technological University</div>
    </div>
    <img src="{{ url_for('static', filename='coep-logo.png') }}"
         class="coep-logo"
         alt="COEP Technological University Logo">
   </div>
  </div>
 </header>

 <main>
  <section class="intro" aria-labelledby="page-title">
   <div class="eyebrow">Information Retrieval</div>
   <h1 id="page-title">Mini Search Engine</h1>
   <p>An academic search portal for retrieving relevant information from an indexed document collection using different ranking techniques.</p>
  </section>

  <section class="search-panel" aria-label="Search options">
   <form class="search-form" method="get" action="/">
    <div class="query-wrap">
     <input class="query-input" type="text" name="q" value="{{ q }}"
      placeholder="Enter your search terms" aria-label="Search terms" autofocus>
     <button class="search-button" type="submit">Search</button>
    </div>
    <div class="search-options">
     <label class="field">Ranking method
      <select name="mode">{% for m in ('tfidf','bm25','vector') %}
       <option value="{{ m }}" {{ 'selected' if m == mode }}>{{ m|upper }}</option>{% endfor %}</select>
     </label>
     <label class="field">Results per page
      <input type="number" name="k" value="{{ k }}" min="1" max="50">
     </label>
     <label class="check-field">
      <input type="checkbox" name="mmr" value="1" {{ 'checked' if mmr }}>
      Diversify results
     </label>
    </div>
   </form>
  </section>

  {% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}
  {% if notice %}<p class="notice" id="notice" role="status">{{ notice }}</p>{% endif %}

  {% if searched %}
   <section aria-labelledby="results-heading">
    <div class="section-heading">
     <h2 id="results-heading">Search Results</h2>
     <span class="result-count">{{ results|length }} result{% if results|length != 1 %}s{% endif %}</span>
    </div>

    {% if not results and not error and not notice %}
     <p class="empty-state">No results found. Try different search terms.</p>
    {% endif %}

    <div class="result-list">
     {% for r in results %}
      <article class="result-card">
       <a class="result-title" href="{{ r.url }}">{{ r.rank }}. {{ r.title }}</a>
       <div class="result-url">{{ r.url }}</div>
       <p class="snippet">{{ r.snippet_html|safe }}</p>
       <div class="result-meta">
        <span>Relevance score <strong>{{ '%.4f'|format(r.score) }}</strong></span>
        <button class="feedback-button" type="button" onclick="fb({{ r.doc_id }}, this)">Mark relevant</button>
        <span class="feedback-status" id="feedback-{{ r.doc_id }}" role="status" aria-live="polite"></span>
       </div>
      </article>
     {% endfor %}
    </div>

    {% if results %}<button class="reset-button" type="button" onclick="rs()">Reset feedback</button>{% endif %}
   </section>
  {% endif %}

  <p class="status" id="msg" role="status" aria-live="polite"></p>
 </main>

 <footer>Mini Search Engine · Information Retrieval Project · COEP Technological University</footer>

 <script>
 function fb(id, button){
  if(button.dataset.marked === 'true') return;
  button.disabled = true;

  fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({doc_id:id})})
   .then(r=>r.json()).then(d=>{
    if(d.ok){
     button.textContent='Relevance marked ✓';
     button.classList.add('marked');
     button.dataset.marked='true';
     document.getElementById('feedback-'+id).textContent='Relevance marked successfully.';
    } else {
     button.disabled=false;
     document.getElementById('feedback-'+id).textContent='Could not mark this result.';
    }
   }).catch(()=>{
    button.disabled=false;
    document.getElementById('feedback-'+id).textContent='Could not mark this result. Try again.';
   });
 }

 function rs(){
  fetch('/api/reset',{method:'POST'}).then(()=>{
   document.querySelectorAll('.feedback-button').forEach(button=>{
    button.disabled=false;
    button.dataset.marked='false';
    button.classList.remove('marked');
    button.textContent='Mark relevant';
   });
   document.querySelectorAll('.feedback-status').forEach(status=>status.textContent='');
   document.getElementById('msg').textContent='Feedback cleared.';
  });
 }
 </script>
</body>
</html>"""


def create_app(engine: QueryEngine | None = None, **engine_kwargs) -> Flask:
    """Application factory. Pass a ready engine (tests) or let it be built."""
    app = Flask(__name__)
    app.config["ENGINE"] = engine or build_engine(**engine_kwargs)

    def get_engine() -> QueryEngine:
        return app.config["ENGINE"]

    def session_id() -> tuple[str, bool]:
        sid = request.cookies.get(SESSION_COOKIE)
        return (sid, False) if sid else (str(uuid.uuid4()), True)

    def finish(response, sid: str, is_new: bool):
        resp = make_response(response)
        if is_new:
            resp.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="Lax")
        return resp

    def parse_params():
        q = request.args.get("q", "").strip()
        mode = parse_ranking_mode(request.args.get("mode", "bm25")).value
        try:
            k = max(1, min(int(request.args.get("k", 10)), 50))
        except ValueError:
            k = 10
        use_mmr = request.args.get("mmr", "0").lower() in ("1", "true", "on", "yes")
        return q, mode, k, use_mmr

    @app.get("/api/search")
    def api_search():
        sid, is_new = session_id()
        try:
            q, mode, k, use_mmr = parse_params()
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        try:
            results = get_engine().search(q, sid, mode, k, use_mmr)
        except Worklet2Error as exc:
            return jsonify(error=str(exc)), 502
        body = jsonify(query=q, mode=mode, k=k, mmr=use_mmr,
                       notice=getattr(results, "notice", ""),
                       results=[r.to_dict() for r in results])
        return finish(body, sid, is_new)

    @app.post("/api/feedback")
    def api_feedback():
        sid, is_new = session_id()
        payload = request.get_json(silent=True) or {}
        doc_id = payload.get("doc_id")
        if not isinstance(doc_id, int):
            return jsonify(error="doc_id (integer) is required"), 400
        try:
            ok = get_engine().mark_relevant(sid, doc_id)
        except Worklet2Error as exc:
            return jsonify(error=str(exc)), 502
        return finish(jsonify(ok=ok), sid, is_new)

    @app.post("/api/reset")
    def api_reset():
        sid, is_new = session_id()
        get_engine().reset_feedback(sid)
        return finish(jsonify(ok=True), sid, is_new)

    @app.get("/api/stats")
    def api_stats():
        return jsonify(get_engine().stats())

    @app.get("/")
    def index():
        sid, is_new = session_id()
        ctx = {"q": "", "mode": "bm25", "k": 10, "mmr": False,
               "results": [], "searched": False, "error": None, "notice": ""}
        if request.args.get("q", "").strip():
            try:
                q, mode, k, use_mmr = parse_params()
                ctx.update(q=q, mode=mode, k=k, mmr=use_mmr, searched=True)
                terms = tokenize_query(q)
                rows = []
                found = get_engine().search(q, sid, mode, k, use_mmr)
                ctx["notice"] = getattr(found, "notice", "")
                for r in found:
                    row = r.to_dict()
                    row["snippet_html"] = highlight(
                        html.escape(r.snippet), terms, "<mark>", "</mark>"
                    )
                    row["title"] = r.title
                    rows.append(row)
                ctx["results"] = rows
            except (ValueError, Worklet2Error) as exc:
                ctx["error"] = str(exc)
        return finish(render_template_string(_PAGE, **ctx), sid, is_new)

    return app


if __name__ == "__main__":
    create_app().run(port=int(os.environ.get("PORT", "5000")), debug=False)
