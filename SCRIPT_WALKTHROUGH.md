# PR Impact Agent — Python Script Walkthrough
*For technical review. This covers the deterministic (non-AI) scripting layer that is complete.*

## What this script is
It reads a FieldAssist **PR Impact Report** (the "Summary" format Excel:
`Visual` + `DQ` + `Timelines` sheets) and produces a clean, verified
**fact pack** (`factpack.json`) — every impact number computed exactly, in
plain auditable code. **No AI is involved in this layer** — that is deliberate,
so every figure is exact and reproducible. The AI interpretation layer is the
next phase and sits *on top of* this output.

## The pipeline (4 files, run in order)

```
                                            ┌─▶ output/factpack.json  (for the AI agent)
  Excel report ─▶ loader.py ─▶ factpack.py ─┤
                   (columns.py)             └─▶ output/PR_Impact_Script_Output.xlsx  (for humans)
                                               (via excel_report.py)
```

| File | Responsibility |
|---|---|
| **src/columns.py** | The "common vocabulary." Maps the report's real column headers onto canonical names via an alias layer, so a renamed/re-spelled header can't silently break the pipeline. Also defines which metric columns are mandatory. |
| **src/loader.py** | Opens the workbook (read-only, streams 100k+ rows), confirms it's the expected Summary format, and parses the three sheets: **Timelines** (Base/Reference date windows), **Visual** (per-area impact, split into *PR Booked* vs *PR Not Booked*, plus the TOTAL row), and **DQ** (excluded rows, counted by reason). Runs **validation** — independently recomputes LPC growth from base vs reference and checks it matches the report, and checks PRs booked ≤ PRs given. |
| **src/factpack.py** | Takes the loaded data and computes the **derived decision metrics**, then writes `output/factpack.json` (the machine-readable fact pack) **and** the human-readable Excel below. |
| **src/excel_report.py** | Renders the same fact pack into a readable Excel workbook (`output/PR_Impact_Script_Output.xlsx`). This is a **visibility / audit view for people** — it is generated from the same fact pack, so the two can never disagree; it is *not* a second source of truth and *not* the agent's input. |

## What the fact pack contains (the output)
- **timelines** — exact Base vs Reference date windows.
- **data_quality** — excluded vs included outlets, **exclusion rate**, and the
  breakdown of exclusion reasons.
- **overall** — company-level booked vs not-booked: LPC growth, value growth,
  compliance (PRs booked / given), and **lift**.
- **areas[]** — the same metrics for each of the ~25 areas, each with its own
  rule-based **flags** (low_sample, low_compliance, lpc_declined, negative_lift).
- **coverage** — how many areas show positive vs negative lift.
- **rankings** — best/worst areas by lift.
- **report_flags** — report-level caveats (e.g. `high_exclusion_rate`).
- **validation_problems** — anything the internal cross-checks flagged
  (empty = clean).

### Key computed metrics (definitions)
- **compliance** = PRs booked ÷ PRs given (conversion of recommendations).
- **LPC / value growth** = (Base − Reference1) ÷ Reference1.
- **lift** = booked-outlet growth − not-booked-outlet growth. This is the
  quasi-control: did outlets that booked the recommendation outperform
  comparable outlets that got the same visits but didn't book it?
- **exclusion rate** = excluded rows ÷ (excluded + included outlets).

Thresholds used for flags live in `factpack.CONFIG` (indicative, easy to tune).

## The human-readable Excel output (for reviewers)
`output/PR_Impact_Script_Output.xlsx` presents the same results as four tabs:

1. **Input - Impact Report** — the input `Visual` sheet, copied as-is.
2. **Analysis (New)** — *only what the script computed/added*: LIFT, value
   growth, value lift, flags, exclusion rate, coverage. New (computed) columns
   are marked **[NEW]** and coloured green; blue columns come from the input.
   This tab is the quickest way to see what the script contributes beyond the
   raw report.
3. **Guide** — a one-line definition of every column in the Analysis tab.
4. **Data Quality (DQ)** — the exclusion-reason breakdown.

Open the **Analysis** tab next to the **Input** tab to verify any number
end-to-end.

## How to run it
```bash
# 1. create a virtual environment and install packages
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. put a PR Impact Report (Summary format) in  data/
#    then run:
.venv\Scripts\python.exe src\factpack.py
#    -> writes output/factpack.json + output/PR_Impact_Script_Output.xlsx
#       and prints a short summary
```
Samples of **both** outputs (`factpack.json` and `PR_Impact_Script_Output.xlsx`)
are included in `sample_output/` so the result can be reviewed without running
anything.

## Scope note
This is the **deterministic layer only** (the ~80% that must be exact). It does
the reading, validation, and all calculation. It does **not** interpret the
results or make recommendations — that is the next phase (the AI agent), which
reads this fact pack and never does arithmetic itself.
