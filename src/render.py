"""
render.py  -  Turn block models into the one-pager (the clean panel/card style
from before the charts experiment). Blocks stay format-agnostic; this owns look.

Layouts: "onepager" (two-column tiles) and "multipage" (stacked sections).
"""

import html
from util import signed

CSS = """
:root { --navy:#10294e; --gold:#e0a53b; --primary:#2f5fe0; --ink:#1f2a3a; --muted:#6b7787; --line:#e3e8ef;
        --card:#f4f6f9; --green:#1f7a45; --red:#b5322b; --teal:#1f6f86; }
* { box-sizing:border-box; }
body { margin:0; font-family:'Inter','Segoe UI',Arial,sans-serif; color:var(--ink); background:#eef1f7; letter-spacing:.004em; }
.page { width:1160px; max-width:100%; margin:0 auto; background:#fff; box-shadow:0 20px 60px rgba(20,30,51,.12); padding:0 0 24px; }
.brandstrip { height:4px; background:linear-gradient(90deg,#3b6fe0,#8b5cf6,#ec4899,#f5b34a); }
.hd { background:linear-gradient(120deg,#0e2550,#10294e 55%,#132a63); color:#fff; padding:24px 36px; display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:18px; }
.brand { justify-self:start; display:flex; align-items:center; gap:12px; }
.brand .lk { display:flex; flex-direction:column; line-height:1.05; }
.brand .fw { font-size:16.5px; font-weight:700; letter-spacing:.005em; }
.brand .prtag { font-size:9px; font-weight:600; letter-spacing:.42em; color:#9dc0ff; margin-top:4px; }
.hcenter { text-align:center; }
.hcenter h1 { margin:0; font-size:26px; font-weight:700; letter-spacing:-.02em; }
.hcenter .cx { margin-top:6px; color:#9db4e6; font-size:12.5px; font-weight:400; }
.hcenter .cx b { color:#fff; font-weight:600; }
.hd .meta { justify-self:end; text-align:right; color:#aebdd8; }
.hd .meta .mscope { color:#d3ddec; font-weight:600; font-size:12px; margin-bottom:7px; }
.hd .meta .mrow { font-size:11.5px; margin-top:3px; font-weight:400; }
.hd .meta .ml { color:#7f92b5; font-weight:600; letter-spacing:.06em; text-transform:uppercase; font-size:9px; margin-right:7px; }
.panel h3 { color:var(--primary); font-weight:700; }
.card .big { font-weight:700; }
.wrap { padding:22px 34px 0; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.panel { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; }
.panel.full { grid-column:1 / -1; }
.panel h3 { margin:0 0 2px; font-size:16px; color:var(--navy); }
.panel .sub { color:var(--muted); font-size:12px; font-style:italic; margin-bottom:12px; }
.panel p { font-size:13px; line-height:1.5; color:#33404f; margin:6px 0 0; }
.cards { display:flex; gap:16px; flex-wrap:wrap; }
.card { flex:1; min-width:150px; text-align:center; background:#fff; border:1px solid var(--line); border-radius:10px; padding:14px; }
.card .big { font-size:30px; font-weight:800; color:var(--navy); line-height:1; }
.card .lbl { font-weight:700; margin-top:6px; font-size:13px; }
.card .csub { color:var(--muted); font-size:11.5px; margin-top:2px; }
.lpc-row { display:flex; align-items:center; gap:12px; margin:9px 0; }
.lpc-name { width:100px; font-weight:700; }
.chip { background:#e9edf3; border-radius:7px; padding:6px 14px; font-weight:700; min-width:60px; text-align:center; }
.chip-up { background:var(--green); color:#fff; } .chip-down { background:var(--red); color:#fff; } .chip-flat { background:#8894a5; color:#fff; }
.arrow { color:var(--gold); font-weight:800; font-size:18px; }
.d-up { color:var(--green); font-weight:800; } .d-down { color:var(--red); font-weight:800; } .d-flat { color:var(--muted); font-weight:800; }
.note { color:var(--muted); font-size:11.5px; font-style:italic; margin-top:12px; }
.vc { margin:11px 0; }
.vc-top { display:flex; justify-content:space-between; align-items:baseline; }
.vc-name { font-weight:700; } .vc-pct { font-weight:800; color:var(--navy); }
.vc-sub { color:var(--muted); font-size:12px; margin:2px 0 6px; }
.track { background:#e9edf3; border-radius:6px; height:15px; overflow:hidden; }
.fill { height:100%; background:var(--teal); }
.rows .r { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed var(--line); font-size:13px; }
.rows .r .rv { font-weight:800; color:var(--navy); }
.rows .r .rs { color:var(--muted); font-size:11.5px; }
.two { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
.two h4 { margin:0 0 6px; font-size:13px; color:var(--navy); }
.steps { display:grid; grid-template-columns:repeat(2,1fr); gap:14px; }
.step { display:flex; gap:12px; }
.step .n { flex:none; width:26px; height:26px; border-radius:50%; background:var(--navy); color:#fff; font-weight:800; display:flex; align-items:center; justify-content:center; }
.step .t { font-weight:700; font-size:13.5px; } .step .d { color:#42505f; font-size:12.5px; line-height:1.45; margin-top:2px; }
.verified { display:inline-flex; align-items:center; gap:7px; font-size:11.5px; font-weight:700; color:var(--green);
  border:1px solid rgba(31,122,69,.3); background:rgba(31,122,69,.07); padding:6px 12px; border-radius:20px; margin-top:12px; }
.tbl-wrap { overflow-x:auto; margin-top:6px; }
table.dt { width:100%; border-collapse:collapse; font-size:12.5px; }
table.dt th { text-align:left; color:var(--muted); font-weight:600; padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }
table.dt td { padding:8px 10px; border-bottom:1px solid rgba(120,160,255,.12); white-space:nowrap; }
table.dt td:first-child { font-weight:700; color:var(--navy); }
.mp .panel { margin-bottom:20px; }
</style>"""


def _cards(stats):
    out = '<div class="cards">'
    for s in stats:
        out += (f'<div class="card"><div class="big">{html.escape(str(s.get("value","-")))}</div>'
                f'<div class="lbl">{html.escape(s.get("label",""))}</div>'
                f'<div class="csub">{html.escape(s.get("sub","") or "")}</div></div>')
    return out + "</div>"


def _compare(rows):
    def one(r):
        d = r.get("delta")
        cls = "chip-up" if (isinstance(d, (int, float)) and d > 0) else ("chip-down" if (isinstance(d, (int, float)) and d < 0) else "chip-flat")
        dh = (f'<span class="d-up">{signed(d)}</span>' if (isinstance(d, (int, float)) and d > 0)
              else (f'<span class="d-down">{signed(d)}</span>' if (isinstance(d, (int, float)) and d < 0)
                    else '<span class="d-flat">-</span>'))
        fr = f"{r['from']:.2f}" if isinstance(r.get("from"), (int, float)) else "-"
        to = f"{r['to']:.2f}" if isinstance(r.get("to"), (int, float)) else "-"
        return (f'<div class="lpc-row"><div class="lpc-name">{html.escape(r["name"])}</div>'
                f'<div class="chip">{fr}</div><div class="arrow">&#8594;</div>'
                f'<div class="chip {cls}">{to}</div>{dh}</div>')
    return "".join(one(r) for r in rows)


def _bars(bars):
    mx = max([b.get("pct") or 0 for b in bars] + [0.0001])
    out = ""
    for b in bars:
        p = b.get("pct") or 0
        w = max(4, round(p / mx * 100))
        out += (f'<div class="vc"><div class="vc-top"><span class="vc-name">{html.escape(b["name"])}</span>'
                f'<span class="vc-pct">{p*100:.2f}%</span></div>'
                f'<div class="vc-sub">{html.escape(b.get("sub",""))}</div>'
                f'<div class="track"><div class="fill" style="width:{w}%"></div></div></div>')
    return out


def _rows(rows):
    out = '<div class="rows">'
    for r in rows:
        out += (f'<div class="r"><span>{html.escape(r["name"])}</span>'
                f'<span><span class="rv">{html.escape(str(r.get("value","-")))}</span> '
                f'<span class="rs">{html.escape(r.get("sub","") or "")}</span></span></div>')
    return out + "</div>"


def _rows_two(rt):
    def col(title, items):
        return f'<div><h4>{html.escape(title)}</h4>{_rows(items)}</div>'
    return f'<div class="two">{col(rt["left_title"], rt["left"])}{col(rt["right_title"], rt["right"])}</div>'


def _steps(items):
    out = '<div class="steps">'
    for i, it in enumerate(items, 1):
        out += (f'<div class="step"><div class="n">{i}</div><div>'
                f'<div class="t">{html.escape(it["title"])}</div><div class="d">{it["text"]}</div></div></div>')
    return out + "</div>"


def _table(t):
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in t.get("headers", []))
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in t.get("rows", []))
    return f'<div class="tbl-wrap"><table class="dt"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _panel(model, full=False):
    body = ""
    if model.get("stats"):
        body += _cards(model["stats"])
    if isinstance(model.get("narrative"), str):
        body += f"<p>{html.escape(model['narrative'])}</p>"
    if model.get("compare"):
        body += _compare(model["compare"])
    if model.get("bars"):
        body += _bars(model["bars"])
    if model.get("rows"):
        body += _rows(model["rows"])
    if model.get("rows_two"):
        body += _rows_two(model["rows_two"])
    if model.get("table"):
        body += _table(model["table"])
    if model.get("list"):
        body += _steps(model["list"])
    if model.get("note"):
        body += f'<div class="note">{model["note"]}</div>'
    if model.get("verified"):
        body += f'<div><span class="verified">&#10003; {html.escape(model["verified"])}</span></div>'
    sub = f'<div class="sub">{html.escape(model["subtitle"])}</div>' if model.get("subtitle") else ""
    cls = "panel full" if full else "panel"
    return f'<div class="{cls}"><h3>{html.escape(model.get("title",""))}</h3>{sub}{body}</div>'


FULL_WIDTH = {"headline", "recommendations", "caveats", "regional"}


def render_document(header, models, layout="onepager"):
    fa = ('<svg width="30" height="30" viewBox="0 0 40 40"><defs>'
          '<linearGradient id="fam" x1="0" y1="0" x2="1" y2="1">'
          '<stop offset="0" stop-color="#3f6fe3"/><stop offset="1" stop-color="#7c4de0"/></linearGradient></defs>'
          '<rect x="3" y="3" width="34" height="34" rx="9" fill="url(#fam)"/>'
          '<path d="M10 30 C 12.5 18, 22 12.5, 31 11 C 23 15.5, 16.5 21.5, 15.5 30 Z" fill="#fff"/></svg>')
    hd = ('<div class="brandstrip"></div>'
          '<div class="hd">'
          f'<div class="brand">{fa}<div class="lk"><span class="fw">FieldAssist</span>'
          '<span class="prtag">PRISM</span></div></div>'
          f'<div class="hcenter"><h1>{html.escape(header["title"])}</h1>'
          f'<div class="cx">Prepared for <b>{html.escape(header["client"])}</b></div></div>'
          f'<div class="meta"><div class="mscope">{html.escape(header["scope"])}</div>'
          f'<div class="mrow"><span class="ml">Base</span>{header["base"]}</div>'
          f'<div class="mrow"><span class="ml">Reference</span>{header["ref"]}</div></div>'
          '</div>')

    if layout == "multipage":
        body = '<div class="wrap mp">' + "".join(_panel(m, full=True) for m in models) + "</div>"
    else:
        cards = "".join(_panel(m, full=(m["id"] in FULL_WIDTH or bool(m.get("table")))) for m in models)
        body = '<div class="wrap"><div class="grid">' + cards + "</div></div>"

    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">'
            f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
            f'<title>{html.escape(header["title"])}</title><style>{CSS}</style></head>'
            f'<body><div class="page">{hd}{body}</div></body></html>')
