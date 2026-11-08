# Ramp AI Index vs. Census BTOS: where is the gap?

The Ramp AI Index says about 56% of U.S. businesses on Ramp paid for AI in September 2026.
The Census Bureau's Business Trends and Outlook Survey (BTOS) says about 24% of U.S.
businesses used AI. This repo compares the two **group by group** (firm size and sector)
to see where the gap is large and where it is small.

The logic: if Ramp's rate were a roughly constant multiple of Census's in every group, the
gap would mostly be about *what* is measured (paid transactions vs. self-reported use). If
the multiple varies a lot across groups, *who* uses Ramp matters too.

Ramp customers are probably more tech-forward than other firms of the same size and
sector. Nothing here can correct for that, so whatever gap remains within a group is an
**upper bound** on the pure measurement effect.

## Results at a glance (July–September 2026 average)

| Group | Ramp | Census | Gap (pts) | Ramp ÷ Census |
|---|---|---|---|---|
| All businesses | 55.3% | 22.8% | 32.6 | 2.4 |
| Small (1–24 employees) | 49.5% | 22.3% | 27.2 | 2.2 |
| Medium (25–99) | 61.6% | 24.7% | 36.9 | 2.5 |
| Large (100+) | 65.3% | 35.7% | 29.6 | 1.8 |
| Information | 79.9% | 45.9% | 33.9 | 1.7 |
| Healthcare | 42.2% | 24.1% | 18.2 | 1.8 |
| Finance & insurance | 73.0% | 38.3% | 34.7 | 1.9 |
| Construction | 41.8% | 15.2% | 26.5 | 2.7 |
| Manufacturing | 60.3% | 20.6% | 39.7 | 2.9 |
| Retail | 48.7% | 15.8% | 32.9 | 3.1 |
| Accommodation & food | 32.4% | 9.3% | 23.1 | 3.5 |

From `clean/comparison_3mo.csv`, which also has the odds ratio for each group. A ratio
of percentages can't exceed 100 ÷ the Census rate, so it is compressed where Census
adoption is high; the odds ratio has no such cap.

The ratio varies more across sectors (1.7–3.5) than across firm sizes (1.8–2.5).
Healthcare has the smallest gap in points (18) and in odds (2.3), and ties with
Information for the smallest ratio (1.75 vs. 1.74). Manufacturing and Retail rank in the
top four of the seven sectors on all three measures.

## Reproduce

Requires Python 3.10+ and a free FRED API key
(https://fred.stlouisfed.org/docs/api/api_key.html).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export FRED_API_KEY=your_key_here
.venv/bin/python build_dataset.py   # data and comparison tables -> clean/
.venv/bin/python analysis.py        # charts -> charts/, sensitivity -> clean/
```

`python build_dataset.py --inspect` prints the first rows of every Census file.

Without `FRED_API_KEY`, the script falls back to FRED's `fredgraph.csv` download, which
FRED may block for scripted requests.

## Data sources

Full URLs and download dates are in [`raw/SOURCES.md`](raw/SOURCES.md).

| Source | What | In this repo? |
|---|---|---|
| **Ramp AI Index** (FRED release "Ramp AI Index") | Monthly share of businesses on Ramp with a paid AI transaction (card, invoice, ACH), overall, 3 size buckets, 7 sectors | **No.** Copyright Ramp Business Corporation, "Citation required" on FRED; downloaded again on each run into `raw/ramp/` (git-ignored). |
| **Census BTOS** (census.gov/hfp/btos) | Biweekly survey; share of firms answering "Yes" to the AI-use question, national, by sector, by employment size class | **Yes**, `raw/btos/`. U.S. government work, public domain. Census overwrites these files every two weeks, so the repo keeps the snapshot used here (downloaded 2026-11-08). |
| **Census SUSB 2022** | Firm counts and employment by NAICS sector × detailed enterprise size; used only for weights | **Yes**, `raw/susb/`. Public domain. 2022 is the latest year published. |

Cite as: Ramp AI Index, Ramp Business Corporation, via FRED, Federal Reserve Bank of St.
Louis; U.S. Census Bureau, Business Trends and Outlook Survey; U.S. Census Bureau,
Statistics of U.S. Businesses 2022.

## Method

- **Census wording is three separate series, never joined.** Before Nov 17, 2025 BTOS
  asked about AI use "in producing goods or services"; from Nov 17, 2025, "in any of its
  business functions"; from Oct 19, 2026, "Super Intelligence or SI (formerly referred to
  as Artificial Intelligence or AI) in any of its business functions". Comparisons use
  only the "any business function" wording. The six-months-ahead expectations question
  is excluded.
- **Wording era comes from collection dates.** The current Census files print every
  period under the newest question text, so the era is assigned from each period's
  collection start date and checked against the archive file's text.
- **Biweekly to monthly.** Each BTOS period is assigned to the month its collection
  starts (roughly the midpoint of the two weeks respondents describe), then averaged
  within the month. Dating by collection end instead changes the national rate by
  0.4 points; see `clean/robustness_month_end.csv`.
- **Size buckets.** Census size classes (1–4, 5–9, 10–19, 20–49, 50–99, 100–249, 250+)
  are combined into Ramp's buckets (1–24, 25–99, 100+) weighting by SUSB firm counts.
  The 20–49 class is split at 24/25 using SUSB's 20–24 and 25–49 bins. Check: rebuilding
  Census's national rate from its size classes this way gives 22.7% against Census's
  published 22.8%.
- **Sectors** are matched on 2-digit NAICS (Healthcare = 62, Health Care and Social
  Assistance).
- **Main table** averages the latest three months both sources have, to smooth biweekly
  noise. `clean/comparison_latest.csv` has the single latest month.

Every assumption, with its reasoning, is listed in `clean/notes.txt`.

## Outputs

| File | What it is |
|---|---|
| `clean/comparison_3mo.csv` | Main table: Ramp vs. Census by group, 3-month average: gap, ratio, ratio ceiling, odds ratio |
| `clean/comparison_latest.csv` | Same, latest shared month only |
| `clean/robustness_month_end.csv` | Main table with BTOS periods dated by collection end |
| `clean/tidy.csv` | Every monthly rate: source, dimension, group, month, rate, wording |
| `clean/btos_biweekly.csv` | Census rates before monthly averaging, with source file and question text |
| `clean/chart3_firms_workers.csv` | Firm-weighted vs. worker-weighted rates (approximation) |
| `clean/sensitivity.csv`, `clean/sensitivity.md` | Ramp rates reweighted to the U.S. firm-size and sector mix (footnote only) |
| `clean/notes.txt` | Every assumption made |
| `charts/chart1_gap` | Ramp vs. Census over time, with the Census wording changes marked |
| `charts/chart2_groups` | Ramp vs. Census by size and sector, with ratios (main chart) |
| `charts/chart3_firms_workers` | Share of firms vs. share of workers using AI (approximation) |

Charts are saved as PNG (200 dpi) and SVG.

## Limitations

- **Selection.** Ramp customers are a self-selected, likely more tech-forward set of
  firms. Within-group gaps are an upper bound on the measurement effect, not an estimate
  of it.
- **Different questions.** Ramp counts any paid AI transaction in a month. BTOS asks
  whether the business used AI in the last two weeks; its "Yes" share includes
  "Do not know" answers in the denominator. Free AI tools count for Census but not Ramp;
  AI bought by employees on personal cards counts for neither.
- **Approximate group matching.** Ramp assigns size (from revenue and employee models) and
  sector (from a NAICS model) internally, so its buckets line up with Census's
  employee-based classes only roughly.
- **Ratios are capped.** Ramp ÷ Census can't exceed 100 ÷ the Census rate, so ratios are
  compressed where Census adoption is high. The tables report odds ratios as a check.
- **Weights are from 2022.** SUSB 2022 is applied to 2025–26 rates.
- **No "true" national rate.** The reweighted figures in `clean/sensitivity.md` show how
  much the composition of Ramp's customer base matters. They are not combined into a
  single corrected estimate, because no reweighting fixes selection within groups.
- **Firms vs. workers** (chart 3) assumes AI-using and non-using firms in the same size
  class have the same average employment.
- **Census gaps.** No BTOS data for Oct 6 – Nov 16, 2025 (federal shutdown).
  Suppressed cells are skipped, not filled; none fall in sectors used here.
