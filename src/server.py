"""
app.py  -  The PRISM web server (Flask).

Serves the 3 dashboard pages and exposes the engine as a small API. It only
CALLS the existing analysis/assembly code - nothing in the engine changes.

Endpoints:
  GET  /                     -> landing page
  GET  /<page>.html          -> analysis / recommendation pages
  GET  /output/<file>        -> generated artifacts (one-pagers, analysis xlsx)
  POST /api/upload  (file)   -> saves the .xlsx, runs the full analysis
  GET  /api/summary          -> headline numbers for the analysis page
  GET  /api/questions        -> scope options + block menu + formats
  POST /api/generate (json)  -> builds the recommendation, returns its URL

Run:  .venv\\Scripts\\python.exe src\\app.py   ->  http://127.0.0.1:5000
"""

import os
import re
import sys
import json
import traceback

from flask import Flask, request, jsonify, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # make src importable
from factpack import run_analysis
from loader import read_timelines
from util import pct, inr
import assemble

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
OUT = os.path.join(ROOT, "output")
DATA = os.path.join(ROOT, "data")
os.makedirs(OUT, exist_ok=True)
os.makedirs(DATA, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB uploads


def _sid(raw):
    """Sanitise a per-user session id (isolates concurrent users; blocks path traversal)."""
    s = re.sub(r"[^A-Za-z0-9_-]", "", str(raw or ""))[:64]
    return s or "default"


def _dirs(sid):
    """Per-session data + output folders."""
    ddir = os.path.join(DATA, sid)
    odir = os.path.join(OUT, sid)
    os.makedirs(ddir, exist_ok=True)
    os.makedirs(odir, exist_ok=True)
    return ddir, odir


# ---------------------------------------------------------------- pages
@app.get("/")
def home():
    return send_from_directory(WEB, "Homepage.html")


@app.get("/<page>.html")
def page(page):
    fname = page + ".html"
    if os.path.exists(os.path.join(WEB, fname)):
        return send_from_directory(WEB, fname)
    return ("Not found", 404)


@app.get("/output/<path:fn>")
def output(fn):
    resp = send_from_directory(OUT, fn)
    resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    return resp


@app.after_request
def _no_cache(resp):
    # dev: never let the browser serve a stale page/artifact
    resp.headers.setdefault("Cache-Control", "no-store, max-age=0")
    return resp


# ---------------------------------------------------------------- api
def _summary(fp):
    o = fp.get("overall", {}) or {}
    b = o.get("booked") or {}
    lift = o.get("lift") or {}
    cov = fp.get("coverage", {}) or {}
    total = cov.get("total_outlets")
    return {
        "outlets": f"{total:,}" if isinstance(total, (int, float)) else "-",
        "lpc_lift": pct(lift.get("lpc"), 1),
        "value_lift": pct(lift.get("value"), 1),
        "incremental": inr(fp.get("overall_incremental_value")),
        "compliance": pct(b.get("compliance"), 1),
        "source": fp.get("source_file"),
    }


@app.post("/api/upload")
def upload():
    """Save the file (per session) and read ONLY its timelines (fast) so the user
    can pick which reference window(s) to compare against, before the heavy analysis."""
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".xlsx"):
        return jsonify(ok=False, error="Please upload a .xlsx PR Impact report."), 400
    ddir, _ = _dirs(_sid(request.form.get("sid")))
    path = os.path.join(ddir, "input.xlsx")
    f.save(path)
    tl = read_timelines(path)
    if not tl or "base" not in tl:
        return jsonify(ok=False, error="Couldn't read the report's Timelines sheet."), 400
    return jsonify(ok=True, timelines=tl)


@app.post("/api/analyze")
def analyze():
    """Run the full analysis for this session, using only the chosen reference
    windows (keep=['ref1', ...]); the rest are ignored."""
    body = request.get_json(force=True, silent=True) or {}
    keep = body.get("keep") or ["ref1"]
    ddir, odir = _dirs(_sid(body.get("sid")))
    path = os.path.join(ddir, "input.xlsx")
    if not os.path.exists(path):
        return jsonify(ok=False, error="No uploaded report found - please upload again."), 400
    try:
        fp = run_analysis(path, out_dir=odir, keep=keep)     # the real ~10s compute
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True, summary=_summary(fp))


@app.get("/api/summary")
def summary():
    _, odir = _dirs(_sid(request.args.get("sid")))
    p = os.path.join(odir, "factpack.json")
    if not os.path.exists(p):
        return jsonify(ok=False, error="No analysis run yet."), 404
    with open(p, encoding="utf-8") as fh:
        fp = json.load(fh)
    return jsonify(ok=True, summary=_summary(fp))


@app.get("/api/questions")
def questions():
    _, odir = _dirs(_sid(request.args.get("sid")))
    return jsonify(assemble.list_questions(out_dir=odir))


@app.post("/api/generate")
def generate():
    answers = request.get_json(force=True, silent=True) or {}
    _, odir = _dirs(_sid(answers.get("sid")))
    try:
        path = assemble.build_report(answers, out_dir=odir)
    except Exception as e:
        traceback.print_exc()
        return jsonify(ok=False, error=str(e)), 400
    rel = os.path.relpath(path, OUT).replace("\\", "/")
    return jsonify(ok=True, url="/output/" + rel)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("PRISM running ->  http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
