"""
factpack.py  -  Turn the raw-report aggregates into the FACT PACK.

No AI. Every number here is exact, computed from the aggregated sums.

Direction (confirmed): Base = the NEWER month, Reference = the OLDER month, so
    growth = (Base - Reference) / Reference
    lift   = booked-group growth - not-booked-group growth   (quasi-control)

Coverage: overall + by zone / region / class / shoptype, split into
PR-booked vs not-booked, across Reference 1 (primary) and Reference 2/3 (recent
short windows), plus tag-wise (Upsell/Conventional/New/Focussed), a trend view,
data-quality facts, and rankings.
"""

import os
import json
import glob

from loader import read_report, PERIODS
from columns import TAGS, REFERENCES

# Indicative context only (NOT decision rules - data quality is a human call).
CONFIG = {
    "meaningful_growth": 0.05,     # +/-5% band we'd call "roughly flat"
    "short_window_days": 20,       # a reference shorter than this is a partial window
    "territory_min_outlets": 50,   # min booked outlets before a territory enters rankings
}

ACC_KEYS = None  # discovered from first accumulator


def growth(base, ref):
    """(base - ref) / ref  - base is the newer period."""
    if base is None or ref in (None, 0):
        return None
    return round((base - ref) / ref, 4)


def rnd(x, n=4):
    return round(x, n) if isinstance(x, (int, float)) else x


def _combine(*accs):
    """Field-wise sum of one or more accumulators (skip None)."""
    accs = [a for a in accs if a]
    if not accs:
        return None
    out = {k: 0 for k in accs[0]}
    for a in accs:
        for k, v in a.items():
            out[k] += v
    return out


def derive(acc):
    """Full derived metrics for one accumulator."""
    if not acc:
        return None
    d = {"outlets": acc["outlets"]}
    for p in PERIODS:
        n = acc[f"{p}_lpc_n"]
        d[f"lpc_{p}"] = round(acc[f"{p}_lpc_sum"] / n, 4) if n else None
        d[f"value_{p}"] = round(acc[f"{p}_value"], 2)
        d[f"orders_{p}"] = round(acc[f"{p}_orders"], 2)
    for ref in REFERENCES:
        d[f"lpc_growth_{ref}"] = growth(d.get("lpc_base"), d.get(f"lpc_{ref}"))
        d[f"value_growth_{ref}"] = growth(d.get("value_base"), d.get(f"value_{ref}"))
        d[f"orders_growth_{ref}"] = growth(d.get("orders_base"), d.get(f"orders_{ref}"))

    # AOV / drop size (value per order) and its growth
    d["aov_base"] = round(d["value_base"] / d["orders_base"], 2) if d.get("orders_base") else None
    d["aov_ref1"] = round(d["value_ref1"] / d["orders_ref1"], 2) if d.get("orders_ref1") else None
    d["aov_growth_ref1"] = growth(d.get("aov_base"), d.get("aov_ref1"))

    # outlet-level distribution: share of outlets that improved (of the both-valid ones)
    bv = acc["both_valid"]
    d["both_valid"] = bv
    d["lpc_up_rate"] = round(acc["lpc_up"] / bv, 4) if bv else None
    d["value_up_rate"] = round(acc["value_up"] / bv, 4) if bv else None
    d["orders_up_rate"] = round(acc["orders_up"] / bv, 4) if bv else None
    given, booked = acc["prs_given"], acc["prs_booked"]
    d["prs_given"] = round(given, 0)
    d["prs_booked"] = round(booked, 0)
    d["compliance"] = round(booked / given, 4) if given else None        # count conversion
    d["rec_qty"] = round(acc["rec_qty"], 0)
    d["booked_qty"] = round(acc["booked_qty"], 0)
    d["qty_conversion"] = round(acc["booked_qty"] / acc["rec_qty"], 4) if acc["rec_qty"] else None
    d["rec_value"] = round(acc["rec_value"], 2)
    d["booked_value"] = round(acc["booked_value"], 2)
    d["pr_value_conversion"] = round(acc["booked_value"] / acc["rec_value"], 4) if acc["rec_value"] else None
    d["missed_value"] = round(acc["rec_value"] - acc["booked_value"], 2)  # unrealised opportunity (headroom)
    # tag-wise, with mix (share of recommended and of booked value)
    tag_rec_total = sum(acc[f"rec_{t}"] for t in TAGS)
    tag_bk_total = sum(acc[f"booked_{t}"] for t in TAGS)
    tags = {}
    for t in TAGS:
        rec, bk = acc[f"rec_{t}"], acc[f"booked_{t}"]
        tags[t] = {
            "recommended": round(rec, 2), "booked": round(bk, 2),
            "conversion": round(bk / rec, 4) if rec else None,
            "missed": round(rec - bk, 2),
            "share_recommended": round(rec / tag_rec_total, 4) if tag_rec_total else None,
            "share_booked": round(bk / tag_bk_total, 4) if tag_bk_total else None,
        }
    d["tags"] = tags
    return d


def _lift(booked_d, nb_d):
    if not booked_d or not nb_d:
        return None
    out = {}
    for m in ("lpc", "value", "orders"):
        b, nb = booked_d.get(f"{m}_growth_ref1"), nb_d.get(f"{m}_growth_ref1")
        out[m] = round(b - nb, 4) if (b is not None and nb is not None) else None
    return out


def _compact(gval, bucket):
    """Rich per-group view for the by-dimension lists (analyst-level)."""
    b = bucket.get("booked")
    nb = bucket.get("not_booked")
    bd = derive(b) if b else None
    nbd = derive(nb) if nb else None
    alld = derive(_combine(b, nb))
    outlets = alld["outlets"] if alld else 0
    booked_outlets = bd["outlets"] if bd else 0
    lift = _lift(bd, nbd)
    # incremental value = booked group's base value x value-lift (estimate of PR-attributable rupees)
    incremental = None
    if bd and lift and lift.get("value") is not None and bd.get("value_base"):
        incremental = round(bd["value_base"] * lift["value"], 2)
    return {
        "group": gval,
        "outlets": outlets,
        "booked_outlets": booked_outlets,
        "penetration": round(booked_outlets / outlets, 4) if outlets else None,   # % of outlets that booked
        "incremental_value": incremental,
        "booked": None if not bd else {
            "lpc_growth_ref1": bd["lpc_growth_ref1"],
            "value_growth_ref1": bd["value_growth_ref1"],
            "orders_growth_ref1": bd["orders_growth_ref1"],
            "aov_growth_ref1": bd["aov_growth_ref1"],
            "compliance": bd["compliance"],
            "qty_conversion": bd["qty_conversion"],
            "pr_value_conversion": bd["pr_value_conversion"],
            "booked_value": bd["booked_value"],       # absolute contribution (PR booked value)
            "value_base": bd["value_base"],
            "missed_value": bd["missed_value"],        # headroom
            "lpc_up_rate": bd["lpc_up_rate"],          # share of booked outlets that improved
        },
        "not_booked": None if not nbd else {
            "lpc_growth_ref1": nbd["lpc_growth_ref1"],
            "value_growth_ref1": nbd["value_growth_ref1"],
            "orders_growth_ref1": nbd["orders_growth_ref1"],
        },
        "lift": lift,
    }


def _dim_list(agg, dim):
    out = [_compact(gval, bucket) for gval, bucket in agg[dim].items()]
    out.sort(key=lambda x: -(x["outlets"] or 0))
    return out


def _tags_by_dim(agg, dim):
    """Tag-wise booked conversion for each group in a dimension (lean)."""
    out = []
    for gval, bucket in agg[dim].items():
        bd = derive(bucket.get("booked")) if bucket.get("booked") else None
        if not bd:
            continue
        out.append({"group": gval, "booked_outlets": bd["outlets"],
                    "tags": {t: bd["tags"][t]["conversion"] for t in TAGS}})
    out.sort(key=lambda x: -x["booked_outlets"])
    return out


def derive_scope(aggregates, level="overall", value=None):
    """Full derived metrics for ANY slice - the basis for a scoped one-pager.

    level='overall' uses the whole report; otherwise pick a group value within a
    dimension (e.g. level='region', value='KARNATAKA'). Returns the same shape
    the one-pager consumes, so any scope renders identically.
    """
    if level == "overall":
        bucket = aggregates.get("overall", {}).get("ALL", {})
    else:
        bucket = aggregates.get(level, {}).get(value, {})
    b, nb = bucket.get("booked"), bucket.get("not_booked")
    bd, nbd = derive(b), derive(nb)
    alld = derive(_combine(b, nb))
    lift = _lift(bd, nbd)
    incremental = None
    if bd and lift and lift.get("value") is not None and bd.get("value_base"):
        incremental = round(bd["value_base"] * lift["value"], 2)
    return {
        "level": level, "value": value,
        "all": alld or {}, "booked": bd or {}, "not_booked": nbd or {},
        "lift": lift or {},
        "outlet_universe": (alld or {}).get("outlets", 0),
        "booked_outlets": (bd or {}).get("outlets", 0),
        "incremental_value": incremental,
    }


def build_fact_pack(report, source_file):
    agg = report["aggregates"]
    tl = report["timelines"]

    # ----- overall (full detail) -----
    ov = agg["overall"]["ALL"]
    ob, onb = ov.get("booked"), ov.get("not_booked")
    ov_all = _combine(ob, onb)
    overall = {
        "all": derive(ov_all),
        "booked": derive(ob),
        "not_booked": derive(onb),
        "lift": _lift(derive(ob), derive(onb)),
    }
    # incremental value = booked base value x value-lift (estimate of PR-attributable rupees)
    _obd, _lft = overall["booked"] or {}, overall["lift"] or {}
    overall_incremental = (round(_obd["value_base"] * _lft["value"], 2)
                           if _obd.get("value_base") and _lft.get("value") is not None else None)

    # ----- data-quality facts (NOT a verdict) -----
    dq_acc = ov_all
    total = report["total_rows"]
    dq = {
        "total_outlets": total,
        "base_lpc_invalid": dq_acc["base_invalid"],
        "ref1_lpc_invalid": dq_acc["ref1_invalid"],
        "usable_base_vs_ref1": dq_acc["both_valid"],
        "pct_usable_base_vs_ref1": round(dq_acc["both_valid"] / total, 4) if total else None,
        "note": "Counts only. Whether this is acceptable is a human judgement, not a decision the metric makes.",
    }

    # ----- trend across references (business-level = all outlets) -----
    all_d = overall["all"]
    trend = []
    for ref in REFERENCES:
        w = tl.get(ref, {})
        days = w.get("days")
        trend.append({
            "reference": ref,
            "window": f"{w.get('start')}..{w.get('end')}",
            "days": days,
            "short_window": (days is not None and days < CONFIG["short_window_days"]),
            "lpc_growth": all_d.get(f"lpc_growth_{ref}"),
            "value_growth": all_d.get(f"value_growth_{ref}"),
            "orders_growth": all_d.get(f"orders_growth_{ref}"),
        })

    # ----- rankings, concentration, booked trend -----
    regions = _dim_list(agg, "region")
    territories = _dim_list(agg, "territory")

    def _has_lift(x):
        return x.get("lift") and x["lift"].get("lpc") is not None

    reg_lift = [r for r in regions if _has_lift(r)]
    terr_lift = [t for t in territories if _has_lift(t) and t["booked_outlets"] >= CONFIG["territory_min_outlets"]]

    def rank_by(lst, keyfn, reverse, field):
        rows = []
        for x in sorted([r for r in lst if keyfn(r) is not None], key=keyfn, reverse=reverse)[:5]:
            rows.append({"group": x["group"], "booked_outlets": x["booked_outlets"], field: keyfn(x)})
        return rows

    liftkey = lambda x: x["lift"]["lpc"] if _has_lift(x) else None
    bookedval = lambda x: (x["booked"] or {}).get("booked_value")
    missedval = lambda x: (x["booked"] or {}).get("missed_value")
    valgrowth = lambda x: (x["booked"] or {}).get("value_growth_ref1")

    rankings = {
        "region_best_lift":  rank_by(reg_lift, liftkey, True, "lift_lpc"),
        "region_worst_lift": rank_by(reg_lift, liftkey, False, "lift_lpc"),
        "region_top_booked_value": rank_by(regions, bookedval, True, "booked_value"),
        "region_top_headroom":     rank_by(regions, missedval, True, "missed_value"),
        "region_best_value_growth":  rank_by(regions, valgrowth, True, "value_growth_ref1"),
        "region_worst_value_growth": rank_by(regions, valgrowth, False, "value_growth_ref1"),
        "territory_best_lift":  rank_by(terr_lift, liftkey, True, "lift_lpc"),
        "territory_worst_lift": rank_by(terr_lift, liftkey, False, "lift_lpc"),
    }

    # concentration: how much booked value sits in the top regions
    reg_by_val = sorted([r for r in regions if bookedval(r)], key=bookedval, reverse=True)
    total_bv = sum(bookedval(r) or 0 for r in regions)
    def cum_share(n):
        return round(sum(bookedval(r) or 0 for r in reg_by_val[:n]) / total_bv, 4) if total_bv else None
    concentration = {
        "total_booked_value_all_regions": round(total_bv, 2),
        "top5_regions_share": cum_share(5),
        "top10_regions_share": cum_share(10),
    }

    # booked-group trend across references
    bd = overall["booked"] or {}
    trend_booked = []
    for ref in REFERENCES:
        w = tl.get(ref, {}); days = w.get("days")
        trend_booked.append({
            "reference": ref, "days": days,
            "short_window": (days is not None and days < CONFIG["short_window_days"]),
            "lpc_growth": bd.get(f"lpc_growth_{ref}"),
            "value_growth": bd.get(f"value_growth_{ref}"),
            "orders_growth": bd.get(f"orders_growth_{ref}"),
        })

    return {
        "source_file": source_file,
        "direction": "growth = (Base - Reference)/Reference; Base = recent month, Reference = older.",
        "timelines": tl,
        "config_context": CONFIG,
        "coverage": {
            "total_outlets": total,
            "zones": len(agg["zone"]), "regions": len(agg["region"]),
            "territories": len(agg["territory"]), "shoptypes": len(agg["shoptype"]),
            "classes": len(agg["class"]),
            "booked_outlets": (derive(ob) or {}).get("outlets"),
            "not_booked_outlets": (derive(onb) or {}).get("outlets"),
        },
        "data_quality": dq,
        "overall": overall,
        "overall_incremental_value": overall_incremental,
        "tag_wise_overall_booked": (overall["booked"] or {}).get("tags"),
        "tags_by_zone": _tags_by_dim(agg, "zone"),
        "tags_by_class": _tags_by_dim(agg, "class"),
        "concentration": concentration,
        "trend": trend,
        "trend_booked": trend_booked,
        "by_zone": _dim_list(agg, "zone"),
        "by_region": regions,
        "by_class": _dim_list(agg, "class"),
        "by_shoptype": _dim_list(agg, "shoptype"),
        "rankings": rankings,
    }


def _brief(fp):
    o = fp["overall"]
    b = o["booked"] or {}
    print("  Source:", fp["source_file"])
    print("  Timelines:", {k: f"{v['start']}..{v['end']} ({v['days']}d)" for k, v in fp["timelines"].items()})
    dq = fp["data_quality"]
    print(f"  Data quality (fact): usable base-vs-ref1 = {dq['usable_base_vs_ref1']:,}/{dq['total_outlets']:,} "
          f"({dq['pct_usable_base_vs_ref1']:.0%})")
    print(f"  OVERALL booked: LPC growth(ref1)={b.get('lpc_growth_ref1')}, "
          f"value growth={b.get('value_growth_ref1')}, orders growth={b.get('orders_growth_ref1')}, "
          f"compliance={b.get('compliance')}")
    print(f"  OVERALL lift(ref1): {o['lift']}")
    print("  Tag-wise (booked conversion):",
          {t: v["conversion"] for t, v in (fp["tag_wise_overall_booked"] or {}).items()})
    print(f"  Coverage: {fp['coverage']['regions']} regions, {fp['coverage']['zones']} zones, "
          f"booked {fp['coverage']['booked_outlets']:,} / not-booked {fp['coverage']['not_booked_outlets']:,}")
    print("  Region best lift:", [(r["group"], r["lift_lpc"]) for r in fp["rankings"]["region_best_lift"][:3]])
    print("  Region worst lift:", [(r["group"], r["lift_lpc"]) for r in fp["rankings"]["region_worst_lift"][:3]])


def run_analysis(path, out_dir=None, keep=None):
    """Read a report, compute everything, and write all analysis artifacts.
    `keep` = ordered reference keys to use (e.g. ['ref1']); the rest are ignored.
    Returns the fact pack. Raises ValueError if the file isn't a valid report.
    Artifacts written: factpack.json, aggregates.json, scope_index.json,
    PR_Impact_Analysis.xlsx.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = out_dir or os.path.join(root, "output")
    os.makedirs(out_dir, exist_ok=True)

    report = read_report(path, keep=keep)
    if not report.get("format_ok"):
        raise ValueError("Cannot read report: " + "; ".join(report.get("problems", [])))

    fp = build_fact_pack(report, os.path.basename(path))
    with open(os.path.join(out_dir, "factpack.json"), "w", encoding="utf-8") as fh:
        json.dump(fp, fh, indent=2, ensure_ascii=False)
    # raw aggregates → any scope can be derived later without re-reading the report
    with open(os.path.join(out_dir, "aggregates.json"), "w", encoding="utf-8") as fh:
        json.dump({"timelines": report["timelines"], "aggregates": report["aggregates"]},
                  fh, ensure_ascii=False)
    scope_index = {dim: sorted(g for g in groups if g and g not in ("ALL", "(blank)"))
                   for dim, groups in report["aggregates"].items() if dim != "overall"}
    with open(os.path.join(out_dir, "scope_index.json"), "w", encoding="utf-8") as fh:
        json.dump(scope_index, fh, indent=2, ensure_ascii=False)

    from excel_report import write_excel_report
    write_excel_report(fp, os.path.join(out_dir, "PR_Impact_Analysis.xlsx"))
    return fp


if __name__ == "__main__":
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) > 1:
        path = os.path.join(root, "data", sys.argv[1])
    else:
        files = glob.glob(os.path.join(root, "data", "*.xlsx"))
        if not files:
            raise SystemExit("No report found in data/")
        path = max(files, key=os.path.getmtime)   # always use the latest report added

    fp = run_analysis(path)
    print("=" * 78)
    _brief(fp)
    print("  -> wrote output/factpack.json + aggregates.json + scope_index.json + PR_Impact_Analysis.xlsx")
