"""
Build a clean dataset comparing Ramp AI Index with Census BTOS AI-use rates.

Run:   python build_dataset.py            (build everything)
       python build_dataset.py --inspect  (print the structure of your BTOS/SUSB files)

Ramp data downloads automatically from FRED (set FRED_API_KEY). Census files (BTOS, SUSB)
are in raw/ -- see README.md and raw/SOURCES.md.

Outputs:
  clean/tidy.csv               one row per source x dimension x group x month
  clean/btos_biweekly.csv      Census rates before averaging to months
  clean/comparison_latest.csv  Ramp vs Census by group, latest month both have
  clean/comparison_3mo.csv     the same, averaged over the latest 3 shared months
  clean/robustness_month_end.csv  3-month table dating BTOS periods by collection end
  clean/notes.txt              assumptions and anything that was skipped
Charts and the sensitivity check: python analysis.py
"""
import argparse, glob, io, json, os, re, sys, urllib.request
from datetime import date

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW, CLEAN, CHARTS = (os.path.join(ROOT, d) for d in ("raw", "clean", "charts"))
NOTES = []

# ---------------------------------------------------------------- config ---
# Known FRED IDs. If FRED_API_KEY is set, the script also discovers every
# series in the release automatically (recommended: free key at
# fred.stlouisfed.org/docs/api/api_key.html).
RAMP_SERIES = {
    "RAMPAIALL":           ("overall", "All businesses"),
    "RAMPAISMB":           ("size", "Small (1-24)"),
    "RAMPAIMIDMARKET":     ("size", "Medium (25-99)"),
    "RAMPAIENTERPRISE":    ("size", "Large (100+)"),
    "RAMPAITECH":          ("sector", "Information"),
    "RAMPAIMANUFACTURING": ("sector", "Manufacturing"),
    "RAMPAIRETAIL":        ("sector", "Retail Trade"),
    "RAMPAIFINANCE":       ("sector", "Finance & Insurance"),
    "RAMPAICONSTRUCTION":  ("sector", "Construction"),
    "RAMPAIHEALTHCARE":    ("sector", "Healthcare"),
    "RAMPAIHOSPITALITY":   ("sector", "Accommodation & Food"),
}
# Ramp size buckets (employees, inclusive). Source: Ramp spending reports.
RAMP_SIZE = {"Small (1-24)": (1, 24), "Medium (25-99)": (25, 99), "Large (100+)": (100, 10**9)}
# Ramp sector name -> 2-digit NAICS codes
SECTOR_NAICS = {
    "Information": ["51"], "Finance & Insurance": ["52"], "Manufacturing": ["31", "32", "33"],
    "Retail Trade": ["44", "45"], "Construction": ["23"], "Healthcare": ["62"],
    "Accommodation & Food": ["72"],
}
SECTOR_KEYWORDS = {  # for matching FRED titles / BTOS labels without codes
    "Information": ["information"], "Finance & Insurance": ["finance"],
    "Manufacturing": ["manufactur"], "Retail Trade": ["retail"], "Construction": ["construction"],
    "Healthcare": ["health"], "Accommodation & Food": ["accommodation", "food serv"],
}
WORDING_BREAKS = {"any_function": date(2025, 11, 17), "super_intelligence": date(2026, 10, 19)}


def note(msg):
    NOTES.append(msg)
    print("  note:", msg)


# ------------------------------------------------------------------ Ramp ---
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ramp-census-ai research script"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def classify_ramp_title(title):
    t = title.split(":", 1)[-1].strip() if "Ramp Businesses" in title else title
    if "Overall" in title:
        return "overall", "All businesses"
    if "Company Size" in title:
        for g in RAMP_SIZE:
            if g.split()[0].lower() in title.lower():
                return "size", g
    if "Industry" in title:
        for g, kws in SECTOR_KEYWORDS.items():
            if any(k in title.lower() for k in kws):
                return "sector", g
    return None


def fetch_ramp_csv(sid, key):
    """Series as 'date,value' CSV. Uses the FRED API when a key is set (fredgraph.csv
    blocks some scripted clients)."""
    if not key:
        return fetch(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
    obs = json.loads(fetch("https://api.stlouisfed.org/fred/series/observations?file_type=json"
                           f"&series_id={sid}&api_key={key}"))["observations"]
    return "observation_date," + sid + "\n" + "".join(
        f"{o['date']},{'' if o['value'] == '.' else o['value']}\n" for o in obs)


def discover_ramp_series(key):
    url = ("https://api.stlouisfed.org/fred/series/search?file_type=json&limit=200&api_key="
           f"{key}&search_text=Artificial%20Intelligence%20Adoption%20by%20Ramp%20Businesses")
    found = {}
    for s in json.loads(fetch(url)).get("seriess", []):
        c = classify_ramp_title(s["title"])
        if c and s["id"].startswith("RAMPAI"):
            found[s["id"]] = c
    return found


def load_ramp():
    series = dict(RAMP_SERIES)
    key = os.environ.get("FRED_API_KEY")
    if key:
        try:
            series.update(discover_ramp_series(key))
        except Exception as e:
            note(f"FRED discovery failed ({e}); using built-in series list only")
    else:
        note("FRED_API_KEY not set: only the built-in Ramp series were downloaded "
             "(some sectors may be missing)")
    os.makedirs(os.path.join(RAW, "ramp"), exist_ok=True)
    rows = []
    for sid, (dim, grp) in series.items():
        path = os.path.join(RAW, "ramp", f"{sid}.csv")
        try:
            text = fetch_ramp_csv(sid, key)
            open(path, "w").write(text)
        except Exception as e:
            if not os.path.exists(path):
                note(f"could not download {sid}: {e}")
                continue
            note(f"could not download {sid}; using cached copy")
            text = open(path).read()
        df = pd.read_csv(io.StringIO(text))
        df.columns = ["date", "rate"]
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
        for d, r in df.dropna().itertuples(index=False):
            rows.append(dict(source="Ramp", dimension=dim, group=grp,
                             month=pd.Timestamp(d).to_period("M"), rate=r,
                             wording="paid_transactions", series_id=sid))
    note("Ramp assigns firm size (revenue + employee models) and sector (NAICS model) "
         "internally; Ramp's Small 1-24 / Medium 25-99 / Large 100+ match Census employee "
         "size classes only approximately.")
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ BTOS ---
PERIOD_COL = re.compile(r"^\d{6}$")


def read_any(path):
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path, sheet_name=None, header=None, dtype=str)
    return {"csv": pd.read_csv(path, header=None, dtype=str)}


def with_header(raw, must_contain):
    """Find the first row containing all keywords and use it as the header."""
    for i in range(min(len(raw), 30)):
        cells = [str(x).strip().lower() for x in raw.iloc[i].tolist()]
        if all(any(k in c for c in cells) for k in must_contain):
            df = raw.iloc[i + 1:].copy()
            df.columns = [str(x).strip() for x in raw.iloc[i].tolist()]
            return df.reset_index(drop=True)
    return None


def wording_for(start):
    """Census wording era from a period's collection START date. The current files label
    every period with the newest question text, so the text alone can't tell eras apart."""
    if start >= WORDING_BREAKS["super_intelligence"]:
        return "super_intelligence"
    if start >= WORDING_BREAKS["any_function"]:
        return "any_function"
    return "goods_services"


def text_wording(q):
    """Era implied by a question's text (used only to cross-check wording_for)."""
    q = q.lower()
    if "producing goods or services" in q:
        return "goods_services"
    return "any_function"  # current files: "any of its business functions" (now worded as SI)


def is_ai_use_question(q):
    """The firm-level 'did this business use AI/SI' question. Excludes the six-months-ahead
    expectations question, the employees-use-generative-AI question and the headcount ones."""
    q = str(q).strip().lower()
    return q.startswith("in the last two weeks, did this business use ") and "intelligence" in q


def btos_sheets(path):
    """(dimension, sheet name) pairs to read. Current files keep estimates on a
    'Response Estimates' sheet; the archive 'AI Core Questions' file has one sheet per
    geography. Standard-error sheets are never read."""
    name = os.path.basename(path).lower()
    sheets = pd.ExcelFile(path).sheet_names
    if "Response Estimates" in sheets:
        if "sector" in name and "size" in name:
            return []
        dim = ("size" if "size" in name else "sector" if "sector" in name else
               "overall" if "national" in name else None)
        return [(dim, "Response Estimates")] if dim else []
    archive = {"National Estimates": "overall", "Sector Estimates": "sector",
               "Employment Size Estimates": "size"}
    return [(dim, s) for s, dim in archive.items() if s in sheets]


def load_btos_dates():
    """Map period IDs (e.g. 202524) to (collection start, collection end), from the
    'Collection and Reference Dates' sheet in each workbook."""
    mapping = {}
    for path in sorted(glob.glob(os.path.join(RAW, "btos", "*.xlsx"))):
        if "Collection and Reference Dates" not in pd.ExcelFile(path).sheet_names:
            continue
        raw = pd.read_excel(path, sheet_name="Collection and Reference Dates", header=None, dtype=str)
        df = with_header(raw, ["smpdt"])
        start = next(c for c in df.columns if re.match(r"col(lection)? start", c, re.I))
        end = next(c for c in df.columns if re.match(r"col(lection)? end", c, re.I))
        for pid, s, e in zip(df["Smpdt"], df[start], df[end]):
            if not re.fullmatch(r"\d{6}", str(pid).strip()):
                continue
            d = (pd.Timestamp(s).date(), pd.Timestamp(e).date())
            if mapping.setdefault(str(pid).strip(), d) != d:
                raise ValueError(f"BTOS period {pid} has different dates in different files")
    return mapping


def btos_size_codes(path):
    """Size letter -> (lo, hi) employees, read from the workbook's Data Dictionary."""
    raw = pd.read_excel(path, sheet_name="Data Dictionary", header=None, dtype=str)
    codes = {}
    for item, desc in zip(raw[0], raw[1]):
        if re.fullmatch(r"[A-Z]", str(item).strip()) and "employees" in str(desc):
            codes[str(item).strip()] = parse_size(desc)
    return codes


def parse_size(label):
    s = str(label).lower().replace(",", "")
    nums = [int(x) for x in re.findall(r"\d+", s)]
    # strip leading codes like "02:" that SUSB uses
    if re.match(r"^\s*\d{1,2}\s*:", s):
        nums = nums[1:]
    if not nums:
        return None
    if "+" in s or "or more" in s or "and over" in s:
        return (nums[0], 10**9)
    if "<" in s or "less than" in s or "fewer" in s:
        return (1, nums[0] - 1)
    if len(nums) >= 2:
        return (nums[0], nums[1])
    return None


def parse_sector(code):
    """BTOS sector code ('31' = 31-33, '44' = 44-45) -> Ramp sector name, or None."""
    c = str(code).strip()[:2]
    return next((g for g, codes in SECTOR_NAICS.items() if c in codes), None)


def pct(cell):
    """'17.3%' -> 17.3; '.', 'S' or blank -> NaN."""
    try:
        return float(str(cell).strip().rstrip("%"))
    except ValueError:
        return float("nan")


def btos_se_sheet(path, sheet, est):
    """The standard-error sheet matching an estimates sheet, row-aligned with it. Census
    publishes one per estimates sheet with identical rows and period columns."""
    name = ("Response Standard Errors" if sheet == "Response Estimates"
            else sheet.replace("Estimates", "SE"))
    se = with_header(pd.read_excel(path, sheet_name=name, header=None, dtype=str),
                     ["question", "answer"])
    keys = [c for c in est.columns if not PERIOD_COL.match(c)]
    if list(se.columns) != list(est.columns) or not se[keys].fillna("").equals(est[keys].fillna("")):
        raise ValueError(f"{os.path.basename(path)}: '{name}' rows don't match '{sheet}'")
    return se


def load_btos():
    files = sorted(glob.glob(os.path.join(RAW, "btos", "*.xlsx")))
    if not files:
        note("no BTOS files found in raw/btos/ -- see README for download steps")
        return None
    dates = load_btos_dates()
    rows = []
    for path in files:
        fname = os.path.basename(path)
        for dim, sheet in btos_sheets(path):
            raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)
            df = with_header(raw, ["question", "answer"])
            se = btos_se_sheet(path, sheet, df)
            pcols = [c for c in df.columns if PERIOD_COL.match(c)]
            gcol = {"size": "Empsize", "sector": "Sector"}.get(dim)
            sizes = btos_size_codes(path) if dim == "size" else {}
            sel = df[df["Question"].map(is_ai_use_question) & (df["Answer"].str.strip() == "Yes")]
            for _, r in sel.iterrows():
                if dim == "size":
                    lo, hi = sizes[r[gcol].strip()]
                    grp = f"{lo}-{hi}" if hi < 10**9 else f"{lo}+"
                elif dim == "sector":
                    grp = parse_sector(r[gcol])
                    if grp is None:
                        continue  # sector Ramp doesn't publish, or XX (multi-sector firms)
                else:
                    grp = "All businesses"
                for pc in pcols:
                    try:
                        val = float(str(r[pc]).strip().rstrip("%"))
                    except ValueError:
                        continue  # "." = not asked / not collected, "S" = suppressed
                    if val != val:
                        continue  # blank cell
                    if pc not in dates:
                        raise ValueError(f"{fname}: period {pc} missing from dates sheet")
                    start, end = dates[pc]
                    wording = wording_for(start)
                    if (wording == "goods_services") != (text_wording(r["Question"]) == "goods_services"):
                        raise ValueError(f"{fname}/{sheet}: period {pc} ({start}) has a value under "
                                         f"question text from a different wording era")
                    rows.append(dict(source="Census BTOS", dimension=dim, group=grp, period=pc,
                                     col_start=start, period_end=end, rate=val,
                                     se=pct(se.at[r.name, pc]), wording=wording,
                                     file=fname, question=r["Question"]))
    if not rows:
        note("BTOS files found but no AI-use rows parsed -- run with --inspect")
        return None
    bi = pd.DataFrame(rows)
    dup = bi.duplicated(["dimension", "group", "period"], keep=False)
    if dup.any():
        raise ValueError(f"same group/period found twice:\n{bi[dup].head()}")
    bi.to_csv(os.path.join(CLEAN, "btos_biweekly.csv"), index=False)
    note("BTOS wording era is assigned from each period's collection START date "
         "(goods/services before 2025-11-17; any business function from 2025-11-17; "
         "Super Intelligence from 2026-10-19), because the current Census files label all "
         "periods with the newest question text. Checked against the archive file's text.")
    note("BTOS biweekly periods are assigned to the month their collection period STARTS, then "
         "averaged (simple mean) within month and wording era. Respondents report on the two "
         "weeks before they answer, so a period's activity runs from about two weeks before "
         "collection starts to collection end; the collection start is roughly its midpoint. "
         "Dating by collection END would compare Ramp's month with older Census answers and, "
         "with adoption rising, widen the gap slightly. Robustness: the 3-month comparison "
         "under the end-date convention is in clean/robustness_month_end.csv.")
    note("BTOS rate = share answering 'Yes' among all respondents (denominator includes "
         "'Do not know'). BTOS asks about the last two weeks; Ramp counts any paid AI "
         "transaction in the month, so the windows differ.")
    note("Census standard errors come from each workbook's standard-error sheet (checked to "
         "be row- and column-aligned with the estimates). Averaging periods assumes they are "
         "independent samples (each BTOS period surveys a different panel); combining size "
         "classes assumes the classes are independent samples, with SUSB weights treated as "
         "fixed. Odds-ratio 95% intervals use the delta method on Census's log odds and ignore "
         "Ramp's own noise, which Ramp does not publish, so they are too narrow.")
    note("BTOS periods 202521-202523 (Oct 6 - Nov 16, 2025) were not collected (federal "
         "shutdown); there is no BTOS value for those weeks.")
    note("BTOS cells marked 'S' (suppressed) are skipped, not filled. Among the AI-use rows "
         "this affects only sectors 11, 21, 22, 55, none of which Ramp publishes.")
    note("BTOS sectors matched to Ramp's on 2-digit NAICS: Information 51, Finance & Insurance "
         "52, Manufacturing 31-33, Retail 44-45, Construction 23, Healthcare 62 (Health Care "
         "and Social Assistance, per the FRED series title), Accommodation & Food 72. BTOS "
         "sector 'XX' (multi-unit firms in several sectors) and sectors Ramp doesn't publish "
         "are dropped.")
    return bi


def btos_monthly(bi, datecol="col_start"):
    """Average biweekly BTOS periods to months, by the month of `datecol`. Standard error of
    the mean treats periods as independent (each period is a different BTOS panel)."""
    bi = bi.assign(month=pd.to_datetime(bi[datecol]).dt.to_period("M"), se2=bi.se ** 2)
    m = bi.groupby(["source", "dimension", "group", "month", "wording"], as_index=False).agg(
        rate=("rate", "mean"), se2=("se2", "sum"), n=("rate", "size"))
    m["se"] = m.se2 ** 0.5 / m.n
    return m.drop(columns=["se2", "n"])


# ------------------------------------------------------------------ SUSB ---
def load_susb():
    """US rows of the SUSB detailed-sizes table: naics, lo, hi, firms, employment. None if absent."""
    files = sorted(glob.glob(os.path.join(RAW, "susb", "*detailedsizes*.xlsx")))
    if not files:
        return None
    raw = pd.read_excel(files[-1], sheet_name=0, header=None, dtype=str)
    df = with_header(raw, ["naics", "enterprise size"])
    df = df[df["State Name"].str.strip() == "United States"]
    rng = df["Enterprise Size"].map(lambda s: (1, 10**9) if "total" in s.lower() else parse_size(s))
    out = pd.DataFrame({"naics": df["NAICS"].str.strip(),
                        "size_label": df["Enterprise Size"].str.strip(),
                        "lo": rng.map(lambda r: r[0] if r else None),
                        "hi": rng.map(lambda r: r[1] if r else None),
                        "firms": pd.to_numeric(df["Firms"]),
                        "employment": pd.to_numeric(df["Employment"])})
    note(f"SUSB weights are from {os.path.basename(files[-1])} (2022, the latest SUSB year "
         "published), applied to 2025-26 rates: the firm-size distribution is assumed stable.")
    note("SUSB's lowest bin '<5 employees' is treated as BTOS's 1-4 class. (Not yet checked: "
         "whether SUSB's '<5' also counts employer firms with zero employees in March.)")
    return out[out.lo.notna()].astype({"lo": int, "hi": int}).reset_index(drop=True)


def susb_total(susb, naics="--", col="firms"):
    """SUSB 'Total' row (all sizes) for one NAICS code."""
    return susb[(susb.naics == naics) & (susb.lo == 1) & (susb.hi == 10**9)][col].sum()


def susb_counts(susb, naics="--", col="firms"):
    """{(lo, hi): count} for one NAICS code ('--' = all industries), finest bins only."""
    sub = susb[susb.naics == naics]
    return finest_bins({(a, b): n for a, b, n in zip(sub.lo, sub.hi, sub[col])})


def finest_bins(counts):
    """Keep non-overlapping, narrowest size bins (drop subtotals like '<20')."""
    bins = sorted(counts, key=lambda b: (b[1] - b[0]))
    keep = []
    for b in bins:
        if b[0] == 1 and b[1] >= 10**9:
            continue
        if not any(not (b[1] < k[0] or b[0] > k[1]) for k in keep):
            keep.append(b)
    return {b: counts[b] for b in sorted(keep)}


def firms_in(counts, lo, hi):
    """Firm count in [lo, hi], assuming firms are spread evenly within a SUSB bin."""
    total = 0.0
    for (a, b), n in counts.items():
        ov = max(0, min(b, hi) - max(a, lo) + 1)
        if ov:
            total += n * ov / (min(b, 10**6) - a + 1) if b < 10**9 else (n if lo <= a else 0)
    return total


# ------------------------------------------------------------- combining ---
def btos_to_ramp_sizes(btos, susb):
    """Combine BTOS size classes into Ramp's 1-24 / 25-99 / 100+ buckets."""
    sz = btos[btos.dimension == "size"].copy()
    if sz.empty:
        return sz
    sz["rng"] = sz["group"].map(lambda g: tuple(int(x) for x in re.findall(r"\d+", g)) if "-" in g
                                else (int(g.rstrip("+")), 10**9))
    fine = susb_counts(susb) if susb is not None else None
    if fine is None:
        note("no SUSB file: BTOS size classes combined with EQUAL weights (unweighted). "
             "Add SUSB for firm-count weights.")
    else:
        note("BTOS size classes combined into Ramp buckets (1-24 / 25-99 / 100+) weighting each "
             "class by SUSB 2022 all-industry firm counts. The BTOS 20-49 class is split at "
             "24/25 using SUSB's 20-24 and 25-49 bins (exact SUSB bin edges, no within-bin "
             "interpolation needed). Assumes the AI-use rate is the same for 20-24 and 25-49 "
             "firms within the BTOS 20-49 class.")
    out = []
    for (month, wording), g in sz.groupby(["month", "wording"]):
        for name, (lo, hi) in RAMP_SIZE.items():
            num = den = var = 0.0
            for (a, b), rate, se in zip(g["rng"], g["rate"], g["se"]):
                ov_lo, ov_hi = max(a, lo), min(b, hi)
                if ov_lo > ov_hi:
                    continue
                w = firms_in(fine, ov_lo, ov_hi) if fine else 1.0
                num += w * rate
                den += w
                var += w ** 2 * se ** 2   # size classes are separate samples
            if den:
                out.append(dict(source="Census BTOS", dimension="size", group=name, month=month,
                                rate=num / den, se=var ** 0.5 / den, wording=wording))
    return pd.DataFrame(out)


def build_comparison(tidy, n_months=1):
    """Ramp vs Census by group, averaging the latest `n_months` months both sources have.
    Uses only the current Census wording; refuses a window that spans a wording change."""
    tidy = tidy[tidy.dimension.isin(["overall", "size", "sector"])]
    ramp = tidy[tidy.source == "Ramp"]
    cen = tidy[(tidy.source == "Census BTOS") & (tidy.wording != "goods_services")]
    common = sorted(set(ramp.month) & set(cen.month))
    if len(common) < n_months:
        note(f"Ramp and Census share fewer than {n_months} months -- comparison skipped")
        return pd.DataFrame()
    months = common[-n_months:]
    c = cen[cen.month.isin(months)]
    if c.wording.nunique() != 1:
        raise ValueError(f"comparison window {months} spans Census wording eras: "
                         f"{sorted(c.wording.unique())}")
    r = ramp[ramp.month.isin(months)]
    counts = pd.concat([r, c]).groupby(["source", "dimension", "group"]).month.nunique()
    if (counts != n_months).any():
        raise ValueError(f"some groups lack a value in every month of {months}:\n"
                         f"{counts[counts != n_months]}")
    r = r.groupby(["dimension", "group"], as_index=False).rate.mean().rename(
        columns={"rate": "ramp_rate"})
    c = (c.assign(se2=c.se ** 2)
          .groupby(["dimension", "group", "wording"], as_index=False)
          .agg(census_rate=("rate", "mean"), se2=("se2", "sum"))
          .rename(columns={"wording": "census_wording"}))
    c["census_se"] = c.se2 ** 0.5 / n_months
    c = c.drop(columns="se2")
    comp = r.merge(c, on=["dimension", "group"], how="inner")
    comp.insert(0, "months", f"{months[0]}" if n_months == 1 else f"{months[0]} to {months[-1]}")
    comp["gap_pts"] = (comp.ramp_rate - comp.census_rate).round(1)
    comp["ratio"] = (comp.ramp_rate / comp.census_rate).round(3)
    # The ratio can't exceed 100 / census_rate, so it is compressed where Census adoption
    # is high. The odds ratio has no such ceiling; reported for the footnote.
    comp["ratio_ceiling"] = (100 / comp.census_rate).round(2)
    odds = lambda p: p / (100 - p)
    comp["odds_ratio"] = (odds(comp.ramp_rate) / odds(comp.census_rate))
    # 95% CI from Census sampling error only (delta method on log odds). Ramp publishes no
    # standard errors, so these intervals are too narrow by whatever Ramp's own noise is.
    p = comp.census_rate / 100
    se_log = (comp.census_se / 100) / (p * (1 - p))
    comp["odds_ratio_lo"] = (comp.odds_ratio * np.exp(-1.96 * se_log)).round(3)
    comp["odds_ratio_hi"] = (comp.odds_ratio * np.exp(1.96 * se_log)).round(3)
    comp["odds_ratio"] = comp.odds_ratio.round(3)
    comp["census_se"] = comp.census_se.round(2)
    comp["ramp_rate"] = comp.ramp_rate.round(1)
    comp["census_rate"] = comp.census_rate.round(1)
    order = {"overall": 0, "size": 1, "sector": 2}
    return (comp.assign(_o=comp.dimension.map(order)).sort_values(["_o", "group"])
                .drop(columns="_o"))


def build_tidy(ramp, btos, susb):
    parts = [ramp]
    if btos is not None and len(btos):
        parts += [btos[btos.dimension != "size"], btos_to_ramp_sizes(btos, susb),
                  btos[btos.dimension == "size"].assign(dimension="size_btos_native")]
    tidy = pd.concat([p for p in parts if len(p)], ignore_index=True)
    return tidy[["source", "dimension", "group", "month", "rate", "se", "wording"]].sort_values(
        ["source", "dimension", "group", "month"])


# ------------------------------------------------------------------ main ---
def inspect():
    for folder in ("btos", "susb"):
        for path in sorted(glob.glob(os.path.join(RAW, folder, "*"))):
            print(f"\n=== {folder}/{os.path.basename(path)}")
            for sheet, raw in read_any(path).items():
                print(f"--- sheet {sheet!r}: {raw.shape[0]} rows x {raw.shape[1]} cols")
                print(raw.head(8).to_string(max_colwidth=40))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true")
    a = ap.parse_args()
    for d in (CLEAN, CHARTS, os.path.join(RAW, "btos"), os.path.join(RAW, "susb")):
        os.makedirs(d, exist_ok=True)
    if a.inspect:
        return inspect()

    print("1/4 Ramp (FRED)")
    ramp = load_ramp()
    print(f"    {len(ramp)} rows, groups: {sorted(ramp.group.unique()) if len(ramp) else []}")
    print("2/4 Census BTOS")
    bi = load_btos()
    print(f"    {0 if bi is None else len(bi)} biweekly rows")
    print("3/4 Census SUSB (optional)")
    susb = load_susb()
    print("    not provided" if susb is None else f"    loaded ({len(susb)} US rows)")

    print("4/4 combining")
    tidy = build_tidy(ramp, None if bi is None else btos_monthly(bi, "col_start"), susb)
    tidy.to_csv(os.path.join(CLEAN, "tidy.csv"), index=False)
    for n, name in [(1, "comparison_latest.csv"), (3, "comparison_3mo.csv")]:
        comp = build_comparison(tidy, n)
        if len(comp):
            comp.to_csv(os.path.join(CLEAN, name), index=False)
            print(f"\n{name}\n" + comp.to_string(index=False))
    note("comparison tables: ratio_ceiling = 100 / census_rate, the largest Ramp/Census ratio "
         "possible even if every Ramp customer in the group paid for AI. Ratios are therefore "
         "compressed in high-adoption groups (e.g. Information). odds_ratio = [r/(100-r)] / "
         "[c/(100-c)] has no such ceiling and is reported as a footnote check on which groups "
         "stand out; it is computed from unrounded rates.")
    if bi is not None:
        n_notes = len(NOTES)
        tidy_end = build_tidy(ramp, btos_monthly(bi, "period_end"), susb)
        del NOTES[n_notes:]  # same assumptions as above; don't repeat them
        build_comparison(tidy_end, 3).to_csv(
            os.path.join(CLEAN, "robustness_month_end.csv"), index=False)
    open(os.path.join(CLEAN, "notes.txt"), "w").write(
        f"Built {date.today()}\n" + "\n".join(f"- {n}" for n in NOTES) + "\n")
    print("\nDone. See clean/ and charts/.")


if __name__ == "__main__":
    sys.exit(main())
