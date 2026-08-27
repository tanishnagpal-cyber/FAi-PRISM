"""
loader.py  -  Read the REAL raw PR Impact Report and aggregate it in ONE pass.

No AI. Pure, exact, auditable computation. Because the raw report has no
pre-aggregated sheet, we build every aggregate ourselves here, streaming the
~170k rows so memory stays small.

Output of read_report():
    {
      "timelines": {base/ref1/ref2/ref3 windows + day-lengths},
      "total_rows": int,
      "aggregates": { dimension: { group_value: { split: accumulator } } },
    }
where dimension in DIMENSIONS, split in {"booked","not_booked"} (an outlet is
"booked" if it booked >=1 recommendation), and accumulator holds raw SUMS that
factpack.py turns into growth / lift / compliance / tag conversion.

Confidential outlet names are read but NEVER stored - only aggregates survive.
"""

import os
from datetime import datetime, date
from python_calamine import CalamineWorkbook

from columns import (
    resolve_headers, missing_required, DIMENSIONS, TAGS, REFERENCES,
)

GEO_FIELDS = ("shop_type", "class_", "territory", "region", "zone", "outlet_name")

PERIODS = ["base"] + REFERENCES            # base, ref1, ref2, ref3


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Format detection + timelines
# ---------------------------------------------------------------------------
def _sheetmap(cwb):
    return {s.lower(): s for s in cwb.sheet_names}


def is_raw_format(sm):
    return "pr impact report" in sm and "timelines" in sm


def _days(start, end):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).days + 1
        except (ValueError, TypeError):
            continue
    return None


def _celldate(v):
    if isinstance(v, (datetime, date)):
        return v.strftime("%d-%m-%Y")
    return str(v).strip() if v not in (None, "") else None


def parse_timelines(rows):
    """Map the Timelines sheet rows to canonical period keys base/ref1/ref2/ref3."""
    label_to_key = {
        "base period": "base",
        "reference period 1": "ref1",
        "reference period 2": "ref2",
        "reference period 3": "ref3",
    }
    out = {}
    for row in rows[1:]:
        if not row or row[0] in (None, ""):
            continue
        label = str(row[0]).strip()
        key = label_to_key.get(label.lower())
        if not key:
            continue
        start = _celldate(row[1]) if len(row) > 1 else None
        end = _celldate(row[2]) if len(row) > 2 else None
        out[key] = {"label": label, "start": start, "end": end, "days": _days(start, end)}
    return out


# ---------------------------------------------------------------------------
# Accumulator
# ---------------------------------------------------------------------------
def _new_acc():
    acc = {"outlets": 0, "prs_given": 0.0, "prs_booked": 0.0,
           "rec_qty": 0.0, "booked_qty": 0.0,
           "rec_value": 0.0, "booked_value": 0.0,
           "base_invalid": 0, "ref1_invalid": 0, "both_valid": 0,
           # per-outlet distribution: how many improved (base>ref1) among both-valid
           "lpc_up": 0, "value_up": 0, "orders_up": 0}
    for p in PERIODS:
        acc[f"{p}_lpc_sum"] = 0.0
        acc[f"{p}_lpc_n"] = 0
        acc[f"{p}_value"] = 0.0
        acc[f"{p}_orders"] = 0.0
    for t in TAGS:
        acc[f"rec_{t}"] = 0.0
        acc[f"booked_{t}"] = 0.0
    return acc


def _add(acc, vals):
    acc["outlets"] += 1
    for p in PERIODS:
        lpc = vals.get(f"lpc_{p}")
        if lpc is not None and lpc > 0:
            acc[f"{p}_lpc_sum"] += lpc
            acc[f"{p}_lpc_n"] += 1
        acc[f"{p}_value"] += vals.get(f"value_{p}") or 0.0
        acc[f"{p}_orders"] += vals.get(f"orders_{p}") or 0.0
    acc["prs_given"] += vals.get("prs_given") or 0.0
    acc["prs_booked"] += vals.get("prs_booked") or 0.0
    acc["rec_qty"] += vals.get("rec_qty") or 0.0
    acc["booked_qty"] += vals.get("booked_qty") or 0.0
    acc["rec_value"] += vals.get("rec_value") or 0.0
    acc["booked_value"] += vals.get("booked_value") or 0.0
    for t in TAGS:
        acc[f"rec_{t}"] += vals.get(f"rec_{t}") or 0.0
        acc[f"booked_{t}"] += vals.get(f"booked_{t}") or 0.0
    # data-quality facts (base vs ref1 usability)
    base_ok = bool(vals.get("lpc_base") and vals["lpc_base"] > 0)
    ref1_ok = bool(vals.get("lpc_ref1") and vals["lpc_ref1"] > 0)
    if not base_ok:
        acc["base_invalid"] += 1
    if not ref1_ok:
        acc["ref1_invalid"] += 1
    if base_ok and ref1_ok:
        acc["both_valid"] += 1
        # count outlets that improved Base vs Ref1 (base = newer month)
        if vals["lpc_base"] > vals["lpc_ref1"]:
            acc["lpc_up"] += 1
        if (vals.get("value_base") or 0) > (vals.get("value_ref1") or 0):
            acc["value_up"] += 1
        if (vals.get("orders_base") or 0) > (vals.get("orders_ref1") or 0):
            acc["orders_up"] += 1


# ---------------------------------------------------------------------------
# Main read + aggregate
# ---------------------------------------------------------------------------
def read_timelines(path):
    """Fast: read only the Timelines sheet (for the post-upload period picker)."""
    cwb = CalamineWorkbook.from_path(path)
    sm = _sheetmap(cwb)
    if not is_raw_format(sm):
        return None
    return parse_timelines(cwb.get_sheet_by_name(sm["timelines"]).to_python())


def read_report(path, keep=None):
    """keep = ordered list of reference keys to USE (e.g. ['ref1'] or ['ref2','ref1']).
    The chosen references are remapped into the ref1/ref2/ref3 slots in order, so
    the first chosen becomes the primary comparison and unchosen refs are ignored.
    keep=None uses all references as-is. Read via calamine + STREAMED row-by-row
    (iter_rows) so memory stays flat even on a small hosting instance.
    """
    cwb = CalamineWorkbook.from_path(path)
    sm = _sheetmap(cwb)
    if not is_raw_format(sm):
        return {"format_ok": False,
                "problems": [f"Not the expected raw PR report. Sheets: {cwb.sheet_names}"]}

    timelines = parse_timelines(cwb.get_sheet_by_name(sm["timelines"]).to_python())
    it = iter(cwb.get_sheet_by_name(sm["pr impact report"]).iter_rows())
    try:
        header = next(it)
    except StopIteration:
        return {"format_ok": False, "problems": ["The report sheet is empty."]}

    cmap = resolve_headers(header)
    missing = missing_required(cmap)
    if missing:
        return {"format_ok": False, "problems": [f"Missing required columns: {missing}"]}

    # remap the chosen references into the ref1/ref2/ref3 slots (ignore the rest)
    keep = [k for k in (keep or []) if k in ("ref1", "ref2", "ref3")]
    if keep:
        newmap = dict(cmap)
        for r in ("ref1", "ref2", "ref3"):
            for m in ("lpc", "value", "orders"):
                newmap.pop(f"{m}_{r}", None)
        for i, src in enumerate(keep):
            dst = f"ref{i+1}"
            for m in ("lpc", "value", "orders"):
                if f"{m}_{src}" in cmap:
                    newmap[f"{m}_{dst}"] = cmap[f"{m}_{src}"]
        cmap = newmap
        tl_new = {"base": timelines.get("base")}
        for i, src in enumerate(keep):
            if src in timelines:
                tl_new[f"ref{i+1}"] = timelines[src]
        timelines = {k: v for k, v in tl_new.items() if v is not None}

    # canonical fields we need to read per row
    needed = ["outlet_name", "shop_type", "class_", "territory", "region", "zone",
              "lpc_base", "value_base", "orders_base",
              "lpc_ref1", "value_ref1", "orders_ref1",
              "lpc_ref2", "value_ref2", "orders_ref2",
              "lpc_ref3", "value_ref3", "orders_ref3",
              "prs_given", "prs_booked", "rec_qty", "booked_qty",
              "rec_value", "booked_value"]
    for t in TAGS:
        needed += [f"rec_{t}", f"booked_{t}"]
    # pre-split the column map into geo (kept as text) and numeric, for a lean hot loop
    geo_idx = {k: cmap[k] for k in needed if k in cmap and k in GEO_FIELDS}
    num_idx = {k: cmap[k] for k in needed if k in cmap and k not in GEO_FIELDS}
    dims = list(DIMENSIONS.items())

    agg = {d: {} for d in DIMENSIONS}
    total = 0
    for row in it:
        if not row or (row[0] in (None, "") and all(c in (None, "") for c in row)):
            continue
        total += 1
        vals = {}
        for k, i in geo_idx.items():
            c = row[i]
            vals[k] = str(c).strip() if c not in (None, "") else ""
        for k, i in num_idx.items():
            vals[k] = _num(row[i])

        split = "booked" if (vals.get("prs_booked") or 0) > 0 else "not_booked"
        for dim, col in dims:
            gval = "ALL" if col is None else (vals.get(col) or "(blank)")
            bucket = agg[dim].get(gval)
            if bucket is None:
                bucket = agg[dim][gval] = {}
            acc = bucket.get(split)
            if acc is None:
                acc = bucket[split] = _new_acc()
            _add(acc, vals)

    return {"format_ok": True, "problems": [], "timelines": timelines,
            "total_rows": total, "aggregates": agg}


if __name__ == "__main__":
    import glob
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    f = max(glob.glob(os.path.join(root, "data", "*.xlsx")), key=os.path.getmtime)
    r = read_report(f)
    print("format_ok:", r["format_ok"])
    if r["format_ok"]:
        print("rows:", r["total_rows"])
        print("timelines:", {k: (v["label"], v["days"]) for k, v in r["timelines"].items()})
        print("dimensions:", {d: len(g) for d, g in r["aggregates"].items()})
    else:
        print(r["problems"])
