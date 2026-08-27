"""
assemble.py  -  The question-driven output engine.

This is what the UI calls: it takes the user's ANSWERS, builds only the chosen
blocks at the chosen scope, and exports the chosen format. Nothing heavy runs
for blocks the user didn't ask for.

    answers = {
      "client":  "Bajaj Consumer",
      "level":   "overall" | "zone" | "region" | "territory" | "shoptype" | "class",
      "value":   "KARNATAKA"      # required unless level == "overall"
      "include": ["headline","lpc_impact",...]   # or "all"
      "layout":  "onepager" | "multipage"
    }

Public API for the UI:
    list_questions()      -> the question spec (scope options, block choices, formats)
    build_report(answers) -> path to the generated HTML

Reads the analysis artifacts produced by factpack.py (output/aggregates.json,
output/factpack.json, output/scope_index.json).
"""

import os
import json

from factpack import derive_scope
from blocks import BLOCKS, BLOCK_BY_ID
from render import render_document
from util import window, pct, inr

# UI scope label -> canonical dimension
LEVELMAP = {"Overall": "overall", "Zone": "zone", "Region": "region",
            "Territory": "territory", "Channel": "shoptype", "Class": "class"}
# UI include label -> block id
INCLUDE_MAP = {"Impact proof": "lpc_impact", "Value contribution": "value_contribution",
               "Incremental ₹": "incremental_value", "Adoption": "adoption",
               "Regional breakdown": "regional", "Trend": "trend", "Recommendations": "recommendations"}
# canonical dimension -> fact-pack breakdown list
FP_LIST = {"zone": "by_zone", "region": "by_region", "shoptype": "by_shoptype", "class": "by_class"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")

SCOPE_NAMES = {"overall": "Overall", "zone": "Zone", "region": "Region",
               "territory": "Territory", "shoptype": "ShopType", "class": "Class"}
TITLE = "Impact, Refracted"   # the end-report title (see name options in chat)


def _load(out_dir=OUT):
    with open(os.path.join(out_dir, "aggregates.json"), encoding="utf-8") as fh:
        agg = json.load(fh)
    fp_path = os.path.join(out_dir, "factpack.json")
    fp = json.load(open(fp_path, encoding="utf-8")) if os.path.exists(fp_path) else {}
    return agg["aggregates"], agg["timelines"], fp


def scope_label(level, value):
    if level == "overall":
        return "Overall · All PR-target outlets"
    return f"{SCOPE_NAMES.get(level, level.title())} · {value}"


# ---------------------------------------------------------------------------
# API the UI reads to render its question flow
# ---------------------------------------------------------------------------
def list_questions(out_dir=OUT):
    idx_path = os.path.join(out_dir, "scope_index.json")
    scope_index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}
    return {
        "scope_levels": list(SCOPE_NAMES.keys()),
        "scope_values": scope_index,                       # per-level dropdown options
        "blocks": [{"id": b["id"], "label": b["label"]} for b in BLOCKS],
        "formats": ["onepager", "multipage"],              # + "ppt" later
    }


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------
def _breakdown_model(level, fp):
    """A table section for a whole dimension (used in multi-scope / 'All')."""
    canon = LEVELMAP.get(level, "region")
    key = FP_LIST.get(canon)
    if not key or not fp.get(key):
        return {"id": "breakdown_" + canon, "title": "Breakdown by " + level,
                "note": f"A segment-level breakdown for {level} isn't available in this summary."}
    data = sorted(fp[key], key=lambda x: -(x.get("booked_outlets") or 0))[:12]
    rows = []
    for d in data:
        b = d.get("booked") or {}
        lift = d.get("lift") or {}
        rows.append([d.get("group"), pct(lift.get("lpc"), 1), pct(b.get("value_growth_ref1"), 1),
                     pct(b.get("compliance"), 2), inr(b.get("booked_value"))])
    return {"id": "breakdown_" + canon, "title": "Breakdown by " + level,
            "table": {"headers": [level, "LPC lift", "Value growth", "Compliance", "Booked value"], "rows": rows},
            "note": f"Top {len(rows)} {level.lower()}s by booked outlets. Lift = booked minus non-booking growth."}


def build_report(answers, out_dir=OUT):
    aggregates, timelines, fp = _load(out_dir)
    client = answers.get("client", "Client")
    scope = answers.get("scope") or ["Overall"]
    if isinstance(scope, str):
        scope = [scope]
    value = answers.get("value")
    include = answers.get("include") or []
    block_ids = [INCLUDE_MAP[x] for x in include if x in INCLUDE_MAP]
    layout = "multipage" if str(answers.get("format", "")).lower() in ("detailed deck", "multipage", "multi-page") else "onepager"

    # a single concrete slice? (Overall, or one specific value)
    concrete = None
    if scope == ["Overall"]:
        concrete = ("overall", None)
    elif len(scope) == 1 and value and not str(value).startswith("All"):
        concrete = (LEVELMAP.get(scope[0], "overall"), value)

    ordered = [b["id"] for b in BLOCKS]
    models = []

    if concrete:
        level, val = concrete
        s = derive_scope(aggregates, level, val)
        ctx = {"client": client, "scope_label": scope_label(level, val), "timelines": timelines, "fp": fp}
        for bid in ["headline"] + [b for b in ordered if b in block_ids] + ["caveats"]:
            m = BLOCK_BY_ID[bid]["build"](s, ctx)
            if m:
                models.append(m)
        header_scope = ctx["scope_label"]
        suffix = "overall" if level == "overall" else f"{level}_{(val or '').replace(' ', '_')}"
    else:
        # breakdown mode: overall context + a table per chosen dimension
        s = derive_scope(aggregates, "overall", None)
        ctx = {"client": client, "scope_label": "Overall", "timelines": timelines, "fp": fp}
        for bid in ["headline"] + [b for b in ordered if b in block_ids and b != "regional"]:
            m = BLOCK_BY_ID[bid]["build"](s, ctx)
            if m:
                models.append(m)
        for lvl in scope:
            if lvl != "Overall":
                models.append(_breakdown_model(lvl, fp))
        cav = BLOCK_BY_ID["caveats"]["build"](s, ctx)
        if cav:
            models.append(cav)
        bd = " · ".join(l for l in scope if l != "Overall")
        header_scope = ("Overall + " + bd + " breakdown") if bd else "Overall"
        suffix = ("multi_" + "_".join(l.lower() for l in scope if l != "Overall")) if bd else "overall"

    header = {"title": TITLE, "client": client, "scope": header_scope,
              "base": window(timelines, "base"), "ref": window(timelines, "ref1")}
    doc = render_document(header, models, layout=layout)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"one_pager_{suffix}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return path


if __name__ == "__main__":
    # Demo: prove the engine with two different answer sets.
    q = list_questions()
    print("Scope levels:", q["scope_levels"])
    print("Blocks available:", [b["id"] for b in q["blocks"]])
    print("Region options (sample):", q["scope_values"].get("region", [])[:5])
    print()

    allblocks = ["Impact proof", "Value contribution", "Incremental ₹", "Adoption",
                 "Regional breakdown", "Trend", "Recommendations"]
    p1 = build_report({"client": "Bajaj Consumer", "scope": ["Overall"],
                       "include": allblocks, "format": "Concise one-pager"})
    print("Overall (all blocks)          ->", os.path.relpath(p1, ROOT))

    p2 = build_report({"client": "Bajaj Consumer", "scope": ["Region"], "value": "KARNATAKA",
                       "include": ["Impact proof", "Adoption", "Recommendations"], "format": "Concise one-pager"})
    print("Region · Karnataka (3 blocks) ->", os.path.relpath(p2, ROOT))

    p3 = build_report({"client": "Bajaj Consumer", "scope": ["Region", "Zone"],
                       "include": ["Impact proof", "Value contribution", "Trend"], "format": "Detailed deck"})
    print("Multi: Region + Zone breakdown->", os.path.relpath(p3, ROOT))
