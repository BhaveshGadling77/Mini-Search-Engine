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
<html lang="en"><head><meta charset="utf-8"><title>Mini Search Engine</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#222}
 form{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1.5rem}
 input[type=text]{flex:1;min-width:220px;padding:.5rem}
 .r{margin-bottom:1.2rem} .r a{font-size:1.1rem} .u{color:#080;font-size:.85rem}
 .s{color:#555;font-size:.8rem} mark{background:#ffe58a}
 button{padding:.4rem .8rem;cursor:pointer} .msg{color:#06c;font-size:.85rem}
</style></head><body>
<h1>Mini Search Engine</h1>
<form method="get" action="/">
 <input type="text" name="q" value="{{ q }}" placeholder="Search..." autofocus>
 <select name="mode">{% for m in ('tfidf','bm25','vector') %}
  <option value="{{ m }}" {{ 'selected' if m == mode }}>{{ m }}</option>{% endfor %}</select>
 <input type="number" name="k" value="{{ k }}" min="1" max="50" style="width:4rem">
 <label><input type="checkbox" name="mmr" value="1" {{ 'checked' if mmr }}> diversify (MMR)</label>
 <button>Search</button>
</form>
{% if error %}<p style="color:#b00">{{ error }}</p>{% endif %}
{% if notice %}<p class="msg" id="notice">{{ notice }}</p>{% endif %}
{% if searched and not results and not error and not notice %}<p>No results.</p>{% endif %}
{% for r in results %}
 <div class="r">
  <a href="{{ r.url }}">{{ r.rank }}. {{ r.title }}</a>
  <div class="u">{{ r.url }}</div>
  <div>{{ r.snippet_html|safe }}</div>
  <div class="s">score {{ '%.4f'|format(r.score) }} ·
   <button onclick="fb({{ r.doc_id }}, this)">Mark relevant</button></div>
 </div>
{% endfor %}
<p class="msg" id="msg"></p>
{% if results %}<button onclick="rs()">Reset feedback</button>{% endif %}
<script>
function fb(id, btn){fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({doc_id:id})}).then(r=>r.json()).then(d=>{
 document.getElementById('msg').textContent=d.ok?'Feedback saved — search again to see personalised results.':'Could not use that document.';});}
function rs(){fetch('/api/reset',{method:'POST'}).then(()=>{document.getElementById('msg').textContent='Feedback cleared.';});}
</script></body></html>"""


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
