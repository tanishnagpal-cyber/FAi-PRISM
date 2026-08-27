"""
util.py  -  Small shared formatting helpers used by the block library and the
format exporters. Kept in one place so numbers look identical everywhere.
"""


def inr(v):
    """Indian-currency short form: ₹ / L (lakh) / Cr (crore)."""
    if not isinstance(v, (int, float)):
        return "-"
    v = float(v)
    if abs(v) >= 1e7:
        return f"₹{v/1e7:.2f} Cr"
    if abs(v) >= 1e5:
        return f"₹{v/1e5:.2f} L"
    return f"₹{v:,.0f}"


def num(v):
    return f"{v:,.0f}" if isinstance(v, (int, float)) else "-"


def pct(v, dp=2):
    return f"{v*100:.{dp}f}%" if isinstance(v, (int, float)) else "-"


def signed(v, dp=2):
    return f"{v:+.{dp}f}" if isinstance(v, (int, float)) else "-"


def f2(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "-"


def window(tl, key):
    w = (tl or {}).get(key, {}) or {}
    return f"{w.get('start')} → {w.get('end')}"


def safe_div(a, b):
    return (a / b) if (isinstance(a, (int, float)) and b) else None
