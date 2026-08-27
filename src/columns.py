"""
columns.py  -  The "common vocabulary" for the REAL PR Impact Report.

The real report (what product + CST fetch) is the RAW per-outlet export:
sheets 'PR Impact Report' (one row per outlet, ~170k rows) + 'Timelines'.
There is NO pre-aggregated Visual sheet and NO DQ sheet - we compute both
ourselves.

This file maps the report's real column headers onto stable canonical names,
and defines the geography hierarchy we aggregate along.

IMPORTANT (period direction): Base = the NEWER/recent month, Reference =
the OLDER month. Impact/growth = (Base - Reference) / Reference.
"""

# ---------------------------------------------------------------------------
# IDENTITY / GEOGRAPHY COLUMNS
# ---------------------------------------------------------------------------
IDENTITY_ALIASES = {
    "outlet_name":   ["Outlets Name", "Outlet Name"],
    "outlet_erp_id": ["OutletErpId", "Outlet ERP Id"],
    "shop_type":     ["ShopType", "Shop Type"],
    "class_":        ["Class"],              # outlet class/segment (A-PLUS/A/B/C/D/Undefined)
    "beat_name":     ["Beats Name", "Beat Name"],
    "territory":     ["Territory"],
    "region":        ["Region Name", "REGION"],   # state level (main storytelling level)
    "zone":          ["Zone"],               # top level (INDIA1/2/3, WEST)
}

# ---------------------------------------------------------------------------
# METRIC COLUMNS  (identical headers in the real report)
# ---------------------------------------------------------------------------
METRIC_ALIASES = {
    # Base period (the NEWER month)
    "lpc_base":    ["Avg_LPC x BasePeriod"],
    "value_base":  ["Gross_Value x BasePeriod"],
    "orders_base": ["Orders x BasePeriod (in units)"],
    # Reference periods (older). Ref1 = full previous month (primary compare);
    # Ref2/Ref3 are shorter recent windows.
    "lpc_ref1":    ["Avg_LPCxReferencePeriodx1"],
    "value_ref1":  ["Gross_ValuexTimePeriodx1"],
    "orders_ref1": ["OrdersxTimePeriodx1 (in units)"],
    "lpc_ref2":    ["Avg_LPCxReferencePeriodx2"],
    "value_ref2":  ["Gross_ValuexTimePeriodx2"],
    "orders_ref2": ["OrdersxTimePeriodx2 (in units)"],
    "lpc_ref3":    ["Avg_LPCxReferencePeriodx3"],
    "value_ref3":  ["Gross_ValuexTimePeriodx3"],
    "orders_ref3": ["OrdersxTimePeriodx3 (in units)"],
    # PR counts + conversion
    "prs_given":    ["Total_PRs_Given"],
    "prs_booked":   ["Total_PRs_Booked"],
    "rec_qty":      ["Recommended_Qty (in units)"],
    "booked_qty":   ["Booked_Qty (units)"],
    "rec_value":    ["Recommended_Gross_Value"],
    "booked_value": ["Booked_Gross_Value"],
    # Tag-wise recommended vs booked gross value
    "rec_upsell":          ["Recommended_Upsell_Gross_Value"],
    "booked_upsell":       ["Booked_Upsell_Gross_Value"],
    "rec_conventional":    ["Recommended_Conventional_Gross_Value"],
    "booked_conventional": ["Booked_Conventional_Gross_Value"],
    "rec_new":             ["Recommended_New_Product_Gross_Value"],
    "booked_new":          ["Booked_New_Product_Gross_Value"],
    "rec_focussed":        ["Recommended_Focussed_Gross_Value"],
    "booked_focussed":     ["Booked_Focussed_Gross_Value"],
}

ALL_ALIASES = {**IDENTITY_ALIASES, **METRIC_ALIASES}

# Metric columns that MUST exist for the sheet to be a valid PR report.
REQUIRED_METRICS = [
    "lpc_base", "value_base", "lpc_ref1", "value_ref1",
    "prs_given", "prs_booked", "rec_value", "booked_value",
]

# The four PR tags.
TAGS = ["upsell", "conventional", "new", "focussed"]

# The reference periods available, in order (primary first).
REFERENCES = ["ref1", "ref2", "ref3"]

# Geography dimensions we aggregate along.
#   name shown in output  ->  canonical column to group by (None = whole report)
DIMENSIONS = {
    "overall":  None,
    "zone":     "zone",
    "region":   "region",
    "territory": "territory",
    "shoptype": "shop_type",
    "class":    "class_",
}


def _norm(s):
    return " ".join(str(s).split()).strip().lower() if s is not None else ""


_REVERSE = {}
for _canon, _reals in ALL_ALIASES.items():
    for _real in _reals:
        _REVERSE[_norm(_real)] = _canon


def resolve_headers(header_row):
    """Map a sheet's header row onto canonical names -> {canonical: col_index}."""
    canon_to_index = {}
    for idx, raw in enumerate(header_row):
        canon = _REVERSE.get(_norm(raw))
        if canon is not None and canon not in canon_to_index:
            canon_to_index[canon] = idx
    return canon_to_index


def missing_required(canon_to_index):
    return [m for m in REQUIRED_METRICS if m not in canon_to_index]
