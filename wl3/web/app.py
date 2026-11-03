"""
Flask front end (presentation only).

Extracts the query and an anonymous session id from the HTTP request, calls
``QueryEngine.search`` and returns JSON / HTML.  No ranking, cache, Rocchio or
MMR logic lives here.

    python3 -m wl3.web.app                  # http://127.0.0.1:5000
    flask --app wl3.web.app:create_app run

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
 <meta name="theme-color" content="#17365b">
 <title>Mini Search | Search portal</title>
 <style>
  :root{color-scheme:light;--navy:#17365b;--navy-dark:#102844;--ink:#1f2937;
   --muted:#5b6777;--line:#d8dee8;--surface:#fff;--background:#f3f5f8;
   --link:#174f8a;--focus:#2b6cb0}
  *{box-sizing:border-box}
  body{margin:0;background:var(--background);color:var(--ink);
   font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
  .topbar{background:var(--navy);color:#fff;border-bottom:4px solid #d5aa4a}
  .topbar-inner{max-width:1040px;margin:auto;padding:1rem 1.5rem;
   display:flex;align-items:center;gap:.85rem}
  .brand-mark{width:2.5rem;height:2.5rem;display:grid;place-items:center;
   border:1px solid #aebed0;border-radius:4px;font-weight:700;letter-spacing:.04em}
  .brand-name{font-size:1.05rem;font-weight:650;letter-spacing:.04em}
  .brand-caption{color:#d5dfeb;font-size:.82rem}
  main{max-width:900px;margin:2.5rem auto;padding:0 1.5rem}
  .intro{margin-bottom:1.5rem}
  h1{margin:0;color:var(--navy-dark);font-size:1.8rem;line-height:1.25}
  .intro p{margin:.45rem 0 0;color:var(--muted)}
  .search-panel,.result-card{background:var(--surface);border:1px solid var(--line);
   border-radius:6px;box-shadow:0 2px 6px rgba(16,40,68,.04)}
  .search-panel{padding:1.25rem}
  .search-form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.65rem}
  .query-wrap{display:flex;min-width:0}
  .query-input{width:100%;min-width:0;padding:.75rem .85rem;
   border:1px solid #aeb9c8;border-radius:4px 0 0 4px;color:var(--ink);
   font:inherit}
  .query-input:focus,select:focus,input[type=number]:focus,button:focus-visible,
  a:focus-visible{outline:3px solid rgba(43,108,176,.3);outline-offset:1px}
  .search-button,.feedback-button,.reset-button{font:inherit;cursor:pointer;
   border-radius:4px}
  .search-button{padding:.65rem 1.2rem;background:var(--navy);color:#fff;
   border:1px solid var(--navy);font-weight:600}
  .search-button:hover{background:var(--navy-dark)}
  .search-options{grid-column:1/-1;display:flex;align-items:end;gap:1rem;
   flex-wrap:wrap;padding-top:.35rem}
  .field{display:grid;gap:.25rem;color:var(--muted);font-size:.82rem}
  .field select,.field input[type=number]{min-height:2.35rem;padding:.4rem .55rem;
   border:1px solid #aeb9c8;border-radius:4px;background:#fff;color:var(--ink);
   font:inherit}
  .field select{min-width:8rem}
  .field input[type=number]{width:5rem}
  .check-field{display:flex;align-items:center;gap:.45rem;min-height:2.35rem;
   color:var(--ink);font-size:.9rem}
  .check-field input{width:1rem;height:1rem;accent-color:var(--navy)}
  .section-heading{display:flex;justify-content:space-between;align-items:center;
   gap:1rem;margin:2rem 0 .75rem}
  .section-heading h2{margin:0;color:var(--navy-dark);font-size:1.05rem}
  .result-count{color:var(--muted);font-size:.88rem}
  .result-list{display:grid;gap:.75rem}
  .result-card{padding:1rem 1.1rem}
  .result-title{color:var(--link);font-size:1.05rem;font-weight:600;
   text-decoration:none}
  .result-title:hover{text-decoration:underline}
  .result-url{overflow-wrap:anywhere;margin:.2rem 0 .55rem;color:#39734d;
   font-size:.84rem}
  .snippet{margin:0}
  mark{background:#fff0bf;color:inherit;padding:0 .08em}
  .result-meta{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;
   margin-top:.8rem;color:var(--muted);font-size:.82rem}
  .feedback-button,.reset-button{padding:.35rem .65rem;background:#fff;
   color:var(--navy);border:1px solid #aeb9c8;font-size:.82rem}
  .feedback-button:hover,.reset-button:hover{background:#f1f5f9}
  .reset-button{margin-top:1rem}
  .notice,.error,.empty-state,.status{padding:.75rem 1rem;border-radius:4px}
  .notice{border:1px solid #e5cb7a;background:#fff9e8;color:#654f14}
  .error{border:1px solid #e6b9b9;background:#fff4f4;color:#8a2525}
  .empty-state{margin-top:1rem;border:1px solid var(--line);background:#fff;
   color:var(--muted)}
  .status{padding:.45rem 0;color:var(--navy);font-size:.88rem}
  footer{max-width:900px;margin:2rem auto 0;padding:1rem 1.5rem 1.5rem;
   border-top:1px solid var(--line);color:var(--muted);font-size:.8rem}
  @media(max-width:600px){
   main{margin:1.5rem auto;padding:0 1rem}
   .topbar-inner{padding:.8rem 1rem}
   .search-form{grid-template-columns:1fr}
   .query-wrap{display:grid;grid-template-columns:minmax(0,1fr) auto}
   .query-input{border-radius:4px 0 0 4px}
   .search-button{border-radius:0 4px 4px 0}
   .search-options{gap:.75rem}
   .section-heading{align-items:flex-start;flex-direction:column;gap:.2rem}
   footer{padding-left:1rem;padding-right:1rem}
  }
 </style>
</head>
<body>
 <header class="topbar">
  <div class="topbar-inner">
   <div class="brand-mark" aria-hidden="true">MS</div>
   <div><div class="brand-name">MINI SEARCH</div>
    <div class="brand-caption">Search portal</div></div>
  </div>
 </header>
 <main>
  <section class="intro" aria-labelledby="page-title">
   <h1 id="page-title">Search</h1>
   <p>Find relevant information across the indexed collection.</p>
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
     <h2 id="results-heading">Search results</h2>
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
        <span>Relevance score: {{ '%.4f'|format(r.score) }}</span>
        <button class="feedback-button" type="button"
         onclick="fb({{ r.doc_id }})">Mark relevant</button>
       </div>
      </article>
     {% endfor %}
    </div>
    {% if results %}<button class="reset-button" type="button" onclick="rs()">Reset feedback</button>{% endif %}
   </section>
  {% endif %}
  <p class="status" id="msg" role="status" aria-live="polite"></p>
 </main>
 <footer>Mini Search · Information retrieval portal</footer>
 <script>
 function fb(id){fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({doc_id:id})}).then(r=>r.json()).then(d=>{
  document.getElementById('msg').textContent=d.ok?'Feedback saved — search again to see personalised results.':'Could not use that document.';});}
 function rs(){fetch('/api/reset',{method:'POST'}).then(()=>{
  document.getElementById('msg').textContent='Feedback cleared.';});}
 </script>
</body>
</html>"""


def create_app(engine: QueryEngine | None = None, **engine_kwargs) -> Flask:
    """Application factory.  Pass a ready engine (tests) or let it be built."""
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
