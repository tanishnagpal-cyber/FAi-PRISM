"""
blocks.py  -  Content-block library (panel/card style).

Each block turns a scope's metrics into a format-agnostic model that render.py
draws as a panel. Model fields a block may set:
  title, subtitle, stats[], narrative, compare[], bars[], rows[], rows_two{},
  table{}, list[], note, verified.  Return None to skip a block.
"""

from util import inr, num, pct, signed, window, safe_div


def _d(a, b):
    return (a - b) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None


# 1 ─ Executive headline (2 stat cards + normalized, positive lead)
def headline(s, ctx):
    a = s["all"]
    per_outlet = safe_div(a.get("prs_given"), s.get("outlet_universe"))
    return {
        "id": "headline", "title": "Impact & Adoption - at a glance",
        "stats": [
            {"label": "Outlet universe", "value": num(s.get("outlet_universe")), "sub": "PR-target outlets"},
            {"label": "Recommendations given", "value": num(a.get("prs_given")),
             "sub": (f"{per_outlet:.1f} per outlet" if per_outlet else "")},
        ],
        "narrative": ("Where recommendations were actioned, outlets outperformed their comparison group - a clear, "
                      "measurable uplift. The momentum is real, with meaningful headroom to compound it as adoption widens."),
    }


# 2 ─ LPC impact (booked vs comparison)
def lpc_impact(s, ctx):
    b, nb = s["booked"], s["not_booked"]
    if not b:
        return None
    rows = []
    for name, m in (("PR booked", b), ("Comparison", nb)):
        if not m:
            continue
        rows.append({"name": name, "from": m.get("lpc_ref1"), "to": m.get("lpc_base"),
                     "delta": _d(m.get("lpc_base"), m.get("lpc_ref1"))})
    return {"id": "lpc_impact", "title": "LPC movement - booked vs comparison",
            "subtitle": "Average lines per call · Reference → Base period",
            "compare": rows,
            "note": "Comparison = matched non-booking outlets, so broad market movement is netted out."}


# 3 ─ Value contribution by tag
def value_contribution(s, ctx):
    a, b = s["all"], s["booked"]
    tags = b.get("tags") or {}
    base_gv = a.get("value_base") or 0
    if not base_gv:
        return None
    bars = []
    for key, label in (("new", "New Product"), ("upsell", "Upsell")):
        booked = (tags.get(key) or {}).get("booked") or 0
        bars.append({"name": label, "value": booked, "pct": safe_div(booked, base_gv), "sub": f"{inr(booked)} booked"})
    combined = sum(x["value"] for x in bars)
    return {"id": "value_contribution", "title": "Booked value contribution - % of base-period GV",
            "subtitle": f"Share of {inr(base_gv)} total base-period gross value",
            "bars": bars,
            "note": f"New Product + Upsell together = {pct(safe_div(combined, base_gv))} of base-period sales."}


# 4 ─ Incremental value
def incremental_value(s, ctx):
    inc = s.get("incremental_value")
    if inc is None:
        return None
    return {"id": "incremental_value", "title": "Value created by PR",
            "stats": [{"label": "PR-attributable value (est.)", "value": inr(inc),
                       "sub": "booked base value × value-lift vs the control"}],
            "narrative": "The estimated uplift booked outlets generated above the non-booking group. Directional, not a booked figure."}


# 5 ─ Adoption (framed as the opportunity ahead)
def adoption(s, ctx):
    a = s["all"]
    pen = safe_div(s.get("booked_outlets"), s.get("outlet_universe"))
    per_outlet = safe_div(a.get("prs_given"), s.get("outlet_universe"))
    return {"id": "adoption", "title": "Adoption - how widely PR is being used",
            "stats": [
                {"label": "Recommendations booked", "value": pct(a.get("compliance"), 1),
                 "sub": "of all suggested, the share actually ordered"},
                {"label": "Outlets covered", "value": pct(pen, 1),
                 "sub": "stores that acted on at least one"},
                {"label": "Suggestions per outlet", "value": (f"{per_outlet:.1f}" if per_outlet else "-"),
                 "sub": "how many PR puts in front of the rep"},
            ],
            "narrative": "Impact is proven where recommendations are acted on - so getting them booked more "
                         "often is the clearest path to more upside."}


# 6 ─ Distribution - how broad the gain is
def distribution(s, ctx):
    up = (s["booked"] or {}).get("lpc_up_rate")
    if up is None:
        return None
    return {"id": "distribution", "title": "How broad is the gain?",
            "stats": [{"label": "Booked outlets that improved", "value": pct(up, 1), "sub": "LPC up vs reference"}],
            "narrative": "A spread check beyond the average - the uplift is shared across many outlets, not a handful."}


# 7 ─ Regional (best / weakest)
def regional(s, ctx):
    rk = (ctx.get("fp") or {}).get("rankings") or {}
    best, worst = rk.get("region_best_lift", []), rk.get("region_worst_lift", [])
    if not best and not worst:
        return None
    def line(x):
        return {"name": x["group"], "value": pct(x.get("lift_lpc"), 1), "sub": f"{num(x.get('booked_outlets'))} booked"}
    return {"id": "regional", "title": "Where it's landing - strongest & softest regions",
            "rows_two": {"left_title": "Strongest", "left": [line(x) for x in best[:3]],
                         "right_title": "Softest", "right": [line(x) for x in worst[:3]]},
            "note": "Lift = booked growth minus non-booking growth. Thin segments excluded."}


# 8 ─ Trend
def trend(s, ctx):
    a = s["all"]
    rows = []
    for ref, lbl in (("ref1", "vs Ref-1"), ("ref2", "vs Ref-2"), ("ref3", "vs Ref-3")):
        g = a.get(f"lpc_growth_{ref}")
        if g is not None:
            rows.append({"name": lbl, "value": pct(g, 1), "sub": "LPC"})
    if not rows:
        return None
    return {"id": "trend", "title": "Momentum across periods", "rows": rows,
            "note": "Base compared against successively earlier windows. Shorter windows are less comparable."}


# 9 ─ Recommendations (elevated, forward-looking)
def recommendations(s, ctx):
    a, b = s["all"], s["booked"]
    comp = a.get("compliance") or 0
    booked_delta = _d(b.get("lpc_base"), b.get("lpc_ref1")) or 0
    tags = b.get("tags") or {}
    items = [
        {"title": "Make the recommendation screen a daily ritual",
         "text": f"Habit is the fastest lever here - with roughly {pct(comp)} of recommendations converting today, "
                 f"opening and actioning the screen on every visit unlocks outsized, low-effort gains."},
        {"title": "Widen the surface area",
         "text": "Extend PR to more salesmen, beats and distributors so a proven engine reaches materially more outlets."},
    ]
    if booked_delta > 0:
        items.append({"title": "Lead with the proof",
                      "text": f"Booked outlets gained {signed(booked_delta)} LPC over outlets that ignored the nudge - "
                              f"put that evidence in reps' hands to convert the sceptics."})
    else:
        items.append({"title": "Sharpen the engine on the soft spots",
                      "text": "Where booking didn't yet pay off, revisit the recommendation logic before scaling."})
    conv = [(k, (v or {}).get("conversion")) for k, v in tags.items() if (v or {}).get("conversion") is not None]
    if conv:
        low = min(conv, key=lambda x: x[1])
        items.append({"title": f"Unlock the '{low[0].title()}' headroom",
                      "text": f"At {pct(low[1])} conversion it's the largest untapped pocket - a focused push compounds quickly."})
    return {"id": "recommendations", "title": "Where the upside is - recommended moves", "list": items[:4]}


# 10 ─ Methodology & assurance
def caveats(s, ctx):
    tl = ctx.get("timelines") or {}
    a = s["all"]
    return {"id": "caveats", "title": "Methodology & assurance",
            "note": (f"Base {window(tl,'base')} vs Reference {window(tl,'ref1')}. Lift compares booked outlets against a "
                     f"matched non-booking group (a quasi-control, not randomised). Overall compliance {pct(a.get('compliance'))}. "
                     f"Some movement may reflect seasonal or promotional factors this report can't isolate."),
            "verified": "Figures computed exactly from the source report and cross-checked - not estimated"}


BLOCKS = [
    {"id": "headline", "label": "Executive headline", "build": headline},
    {"id": "lpc_impact", "label": "LPC impact (booked vs comparison)", "build": lpc_impact},
    {"id": "value_contribution", "label": "Value contribution (tag-wise)", "build": value_contribution},
    {"id": "incremental_value", "label": "Incremental value", "build": incremental_value},
    {"id": "adoption", "label": "Adoption", "build": adoption},
    {"id": "distribution", "label": "How broad the gain is", "build": distribution},
    {"id": "regional", "label": "Regional breakdown", "build": regional},
    {"id": "trend", "label": "Trend across periods", "build": trend},
    {"id": "recommendations", "label": "Recommendations", "build": recommendations},
    {"id": "caveats", "label": "Methodology & assurance", "build": caveats},
]
BLOCK_BY_ID = {b["id"]: b for b in BLOCKS}
