"""
Charts and the reweighting sensitivity check. Run after build_dataset.py.

Run:   python analysis.py

Reads clean/tidy.csv, clean/comparison_3mo.csv and the SUSB table in raw/susb/.

Outputs:
  charts/chart1_gap.{png,svg}            Ramp vs Census over time, wording breaks marked
  charts/chart2_groups.{png,svg}         Ramp vs Census by size and sector (main chart)
  charts/chart3_firms_workers.{png,svg}  share of firms vs share of workers (approximation)
  clean/chart3_firms_workers.csv         the numbers behind chart 3
  clean/sensitivity.csv, clean/sensitivity.md   reweighted national rates (footnote only)
  clean/notes.txt                        analysis assumptions appended
"""
import os

import matplotlib.dates as mdates
import pandas as pd

import build_dataset as b
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory

from exhibit import Exhibit, MARGIN, ORANGE, NAVY, GRAY, INK, SUB, GRID, TICK

BAND = "#f1eee6"  # row highlight, a shade darker than the page background

CLEAN, CHARTS = b.CLEAN, b.CHARTS
SOURCE = ("Source: Ramp AI Index (Ramp Business Corporation, via FRED); U.S. Census Bureau, "
          "Business Trends and Outlook Survey.")
CREDIT = "Analysis: Atharv Joshi"
NOTES = []


def note(msg):
    NOTES.append(msg)


def pct_ticks(ax, axis="y"):
    """Plain numbers on the axis, with % on the top (or rightmost) tick only."""
    ticks = ax.get_yticks() if axis == "y" else ax.get_xticks()
    lo, hi = ax.get_ylim() if axis == "y" else ax.get_xlim()
    top = max(t for t in ticks if lo <= t <= hi)
    fmt = lambda v, _: f"{v:.0f}%" if v == top else f"{v:.0f}"
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


# ------------------------------------------------------------- chart 1 ---
def chart_gap(tidy, bi):
    """bi: BTOS biweekly rows. Ramp months are drawn at mid-month; each Census month at the
    average collection start of its periods (so no Census point sits before a wording break)."""
    ov = tidy[(tidy.dimension == "overall") & (tidy.source == "Ramp")].copy()
    ov["t"] = pd.PeriodIndex(ov.month, freq="M").to_timestamp() + pd.Timedelta(days=14)
    cen = bi[bi.dimension == "overall"].assign(col_start=lambda d: pd.to_datetime(d.col_start))
    cen = (cen.groupby([cen.col_start.dt.to_period("M"), "wording"])
              .agg(t=("col_start", "mean"), rate=("rate", "mean")).reset_index())
    ov = pd.concat([ov, cen], ignore_index=True)
    ex = Exhibit(height=6.8)
    ex.title([[("Ramp", ORANGE), (" AI adoption rate is", INK)],
              [("more than double the ", INK), ("Census", NAVY), (" rate", INK)]])
    ex.subtitle("Share of U.S. businesses using AI, monthly")
    ex.legend([("Ramp: paid for AI", ORANGE), ("Census: used AI", NAVY),
               ("Census, old wording", GRAY)])
    ex.source("Census old wording: AI use \"in producing goods or services\" (to Oct 2025). "
              "Current: \"in any of its business functions\" (from Nov 17, 2025). Not shown: "
              "the Oct 19, 2026 rewording (one period so far).", SOURCE, credit=CREDIT)
    ax = ex.axes(left=0.1, right=0.9)
    for w, col, ls in [("goods_services", GRAY, (0, (2.5, 1.5))), ("any_function", NAVY, "-"),
                       ("paid_transactions", ORANGE, "-")]:
        g = ov[ov.wording == w].sort_values("t")
        ax.plot(g.t, g.rate, color=col, ls=ls, lw=2.6, solid_capstyle="round")
        if w != "goods_services":
            last = g.iloc[-1]
            ax.annotate(f"{last.rate:.0f}%", (last.t, last.rate), xytext=(7, 0),
                        textcoords="offset points", va="center", fontsize=14, weight="bold",
                        color=INK)
    brk = pd.Timestamp(b.WORDING_BREAKS["any_function"])
    ax.axvline(brk, color=TICK, lw=1, ls=(0, (3, 3)))
    ax.annotate("Census rewords\nthe question", (brk, 66), xytext=(-8, 0),
                textcoords="offset points", ha="right", va="top", fontsize=11, color=SUB)
    ax.set_ylim(0, 70)
    ax.set_yticks(range(0, 71, 20))
    pct_ticks(ax)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ex.save(os.path.join(CHARTS, "chart1_gap"))


# ------------------------------------------------------------- chart 2 ---
SHORT = {"Accommodation & Food": "Accommodation & food", "Finance & Insurance":
         "Finance & insurance", "Retail Trade": "Retail"}


def chart_groups(comp):
    """Sorted by odds ratio: the plain ratio is capped at 100 / Census rate, so sorting by it
    mostly ranks groups by Census adoption."""
    blocks = [(None, comp[comp.dimension == "overall"]),
              ("By firm size (employees)", comp[comp.dimension == "size"].sort_values("odds_ratio")),
              ("By sector", comp[comp.dimension == "sector"].sort_values("odds_ratio"))]
    rows, y, heads = [], 0, []
    for head, g in reversed(blocks):          # build bottom-up
        for _, r in g.iterrows():
            rows.append((y, r)); y += 1
        if head:
            heads.append((y + 0.2, head)); y += 1.8
        else:
            y += 0.5
    m0, m1 = comp.months.iloc[0].split(" to ")
    period = f"{pd.Period(m0):%b}–{pd.Period(m1):%b %Y}"
    ci = ((comp.odds_ratio_hi - comp.odds_ratio_lo) / 2).max()
    ex = Exhibit(height=8.2)
    ex.title([[("Healthcare has the smallest gap,", INK)], [("manufacturing the largest", INK)]])
    ex.subtitle(f"Share of businesses using AI, {period} average")
    ex.legend([("Ramp: paid for AI", ORANGE), ("Census: used AI", NAVY)])
    ex.source("Sorted by odds ratio = (Ramp odds) ÷ (Census odds). Unlike the ratio, it isn't "
              f"capped where Census adoption is high. 95% intervals are within ±{ci:.1f} "
              "(Census sampling error only; Ramp publishes no standard errors). Census size "
              "classes regrouped to Ramp's buckets with Census SUSB 2022 firm counts.",
              SOURCE, credit=CREDIT)
    ax = ex.axes(left=0.405, right=0.765, bottom_pad=0.5)
    ax.grid(False)
    ax.grid(axis="x", color=GRID, lw=1)
    cols = {"ratio": 115, "odds": 139}        # data-x positions of the two number columns
    for yy, r in rows:
        ax.plot([r.census_rate, r.ramp_rate], [yy, yy], color=GRID, lw=4, zorder=1,
                solid_capstyle="round")
        ax.scatter(r.census_rate, yy, s=95, color=NAVY, edgecolor="white", lw=1.8, zorder=3)
        ax.scatter(r.ramp_rate, yy, s=95, color=ORANGE, edgecolor="white", lw=1.8, zorder=3)
        if r.group in ("Healthcare", "Manufacturing"):   # the two outliers in the headline
            ax.add_patch(Rectangle((MARGIN / ex.w, yy - 0.5), 1 - 2 * MARGIN / ex.w, 1,
                                   transform=blended_transform_factory(ex.fig.transFigure,
                                                                       ax.transData),
                                   color=BAND, lw=0, zorder=0, clip_on=False))
        ax.text(-3, yy, SHORT.get(r.group, r.group), ha="right", va="center", fontsize=13)
        ax.text(cols["ratio"], yy, f"{r.ratio:.1f}×", ha="center", va="center", fontsize=13)
        ax.text(cols["odds"], yy, f"{r.odds_ratio:.1f}", ha="center", va="center", fontsize=13,
                weight="bold")
    for yy, head in heads:
        ax.text(-3, yy, head, ha="right", va="center", fontsize=12, color=SUB, weight="semibold")
    for key, label in [("ratio", "Ratio"), ("odds", "Odds\nratio")]:
        ax.text(cols[key], y + 0.15, label, ha="center", va="center", fontsize=11, color=SUB,
                weight="semibold")
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_ylim(-0.7, y - 0.3)
    ax.set_yticks([])
    pct_ticks(ax, "x")
    ex.save(os.path.join(CHARTS, "chart2_groups"))


# ------------------------------------------------------------- chart 3 ---
def class_range(g):
    return ((int(g.split("-")[0]), int(g.split("-")[1])) if "-" in g
            else (int(g.rstrip("+")), 10**9))


def weighted(rates, counts):
    """Average of {(lo, hi): rate} weighted by SUSB counts falling in each range."""
    w = {k: b.firms_in(counts, *k) for k in rates}
    return sum(rates[k] * w[k] for k in rates) / sum(w.values())


def firms_vs_workers(tidy, susb, months):
    win = tidy[tidy.month.isin(months)]
    btos = (win[(win.dimension == "size_btos_native")].groupby("group").rate.mean())
    btos = {class_range(g): v for g, v in btos.items()}
    ramp = win[(win.source == "Ramp") & (win.dimension == "size")].groupby("group").rate.mean()
    ramp = {b.RAMP_SIZE[g]: v for g, v in ramp.items()}
    firms, emp = b.susb_counts(susb), b.susb_counts(susb, col="employment")
    published = win[(win.source == "Census BTOS") & (win.dimension == "overall")].rate.mean()
    ramp_all = win[(win.source == "Ramp") & (win.dimension == "overall")].rate.mean()
    out = pd.DataFrame([
        ("Census BTOS", "published national rate", published),
        ("Census BTOS", "share of firms (rebuilt from size classes)", weighted(btos, firms)),
        ("Census BTOS", "share of workers (approx.)", weighted(btos, emp)),
        ("Ramp", "published overall index", ramp_all),
        ("Ramp", "share of firms (size buckets, SUSB firm weights)", weighted(ramp, firms)),
        ("Ramp", "share of workers (approx.)", weighted(ramp, emp)),
    ], columns=["source", "measure", "rate"])
    out.insert(0, "months", f"{months[0]} to {months[-1]}")
    out["rate"] = out.rate.round(1)
    note("Chart 3 (firms vs workers) is an APPROXIMATION. Worker-weighted rate = sum over size "
         "classes of (class AI rate x SUSB 2022 employment in that class) / total employment. "
         "It assumes AI-using and non-using firms within a size class have the same average "
         "employment, and it applies each source's in-class rate to all U.S. firms in the class "
         "(for Ramp, that treats Ramp customers as representative within each size bucket).")
    note("BTOS 100-249 / 250+ boundary falls inside SUSB's 200-299 bin; that bin's firms and "
         "employment are split evenly by width (half to each side). All other BTOS and Ramp "
         "size boundaries line up with SUSB bin edges exactly.")
    return out


def chart_firms_workers(fw):
    get = lambda src, start: fw[(fw.source == src) & fw.measure.str.startswith(start)].rate.iloc[0]
    m0, m1 = fw.months.iloc[0].split(" to ")
    period = f"{pd.Period(m0):%b}–{pd.Period(m1):%b %Y}"
    ex = Exhibit(height=6.2)
    ex.title([[("Counting workers instead of firms", INK)], [("raises both rates", INK)]])
    ex.subtitle(f"Share using AI, {period} average")
    ex.legend([("Ramp: paid for AI", ORANGE), ("Census: used AI", NAVY)])
    ex.source("*Approximation: each size class's AI rate weighted by its employment (Census SUSB "
              "2022). Census uses its 7 size classes; Ramp's 3 size-bucket rates are applied to "
              "all U.S. firms in each bucket.", SOURCE, credit=CREDIT)
    ax = ex.axes(left=0.1, right=0.95, bottom_pad=0.5)
    groups = [("share of firms", "Share of firms"), ("share of workers", "Share of workers*")]
    width = 0.36
    for i, (key, _) in enumerate(groups):
        for dx, src, col in [(-width / 2 - 0.01, "Ramp", ORANGE), (width / 2 + 0.01, "Census BTOS", NAVY)]:
            v = get(src, key)
            ax.bar(i + dx, v, width=width, color=col)
            ax.text(i + dx, v - 2, f"{v:.0f}", ha="center", va="top", fontsize=14,
                    color="white", style="italic", weight="semibold")
    ax.set_xticks(range(len(groups)), [lab for _, lab in groups])
    ax.tick_params(axis="x", labelsize=14, labelcolor=INK)
    ax.set_xlim(-0.6, len(groups) - 0.4)
    ax.set_ylim(0, 75)
    ax.set_yticks(range(0, 76, 25))
    pct_ticks(ax)
    ex.save(os.path.join(CHARTS, "chart3_firms_workers"))


# --------------------------------------------------------- sensitivity ---
def sensitivity(tidy, susb, months):
    win = tidy[tidy.month.isin(months)]
    mean = lambda src, dim: win[(win.source == src) & (win.dimension == dim)].groupby("group").rate.mean()
    total = b.susb_total(susb)
    size_w = {g: b.firms_in(b.susb_counts(susb), lo, hi) / total for g, (lo, hi) in b.RAMP_SIZE.items()}
    sec_n = {g: sum(b.susb_total(susb, n) for n in susb_sector_codes(codes))
             for g, codes in b.SECTOR_NAICS.items()}
    sec_w = {g: n / sum(sec_n.values()) for g, n in sec_n.items()}
    rows = []
    for src in ("Ramp", "Census BTOS"):
        published = win[(win.source == src) & (win.dimension == "overall")].rate.mean()
        sz, sc = mean(src, "size"), mean(src, "sector")
        rows += [(src, "published overall", published),
                 (src, "size rates reweighted to SUSB firm-size distribution",
                  sum(sz[g] * w for g, w in size_w.items())),
                 (src, "sector rates reweighted to SUSB sector distribution (7 sectors)",
                  sum(sc[g] * w for g, w in sec_w.items()))]
    out = pd.DataFrame(rows, columns=["source", "measure", "rate"]).round({"rate": 1})
    out.insert(0, "months", f"{months[0]} to {months[-1]}")
    coverage = sum(sec_n.values()) / total
    v = {(s, m.split()[0]): r for s, m, r in zip(out.source, out.measure, out.rate)}
    txt = (f"**Sensitivity (footnote).** Averaging {months[0]}–{months[-1]}, Ramp's published "
           f"overall index is {v['Ramp', 'published']:.1f}%. Reweighting Ramp's three size-bucket "
           f"rates to the U.S. firm-size distribution (SUSB 2022: "
           + ", ".join(f"{g.split()[0].lower()} {w:.1%}" for g, w in size_w.items())
           + f") gives {v['Ramp', 'size']:.1f}%. Separately, reweighting Ramp's seven sector "
           f"rates to those sectors' SUSB firm shares gives {v['Ramp', 'sector']:.1f}%; those seven "
           f"sectors hold {coverage:.0%} of U.S. employer firms, so this figure describes only "
           f"them. The same weights applied to Census's rates give {v['Census BTOS', 'size']:.1f}% "
           f"and {v['Census BTOS', 'sector']:.1f}% (published: {v['Census BTOS', 'published']:.1f}%). "
           "The two reweightings are not combined: neither corrects for Ramp customers being "
           "more tech-forward than other firms of the same size or sector, so neither is a "
           "\"true\" national rate.")
    open(os.path.join(CLEAN, "sensitivity.md"), "w").write(txt + "\n")
    note("Sensitivity: SUSB sector firm counts are 'Total' rows by NAICS sector. SUSB counts a "
         "firm in every sector it operates in, so sector counts sum to slightly more than the "
         "national firm total (6,461,497 vs 6,395,635 across all sectors).")
    return out


def susb_sector_codes(codes):
    """SUSB writes combined sectors as '31-33' / '44-45'."""
    return {"31": ["31-33"], "44": ["44-45"]}.get(codes[0], codes)


# ---------------------------------------------------------------- main ---
def main():
    tidy = pd.read_csv(os.path.join(CLEAN, "tidy.csv"))
    comp = pd.read_csv(os.path.join(CLEAN, "comparison_3mo.csv"))
    start, end = comp.months.iloc[0].split(" to ")
    months = [str(p) for p in pd.period_range(start, end, freq="M")]
    susb = b.load_susb()

    chart_gap(tidy, pd.read_csv(os.path.join(CLEAN, "btos_biweekly.csv")))
    chart_groups(comp)
    fw = firms_vs_workers(tidy, susb, months)
    fw.to_csv(os.path.join(CLEAN, "chart3_firms_workers.csv"), index=False)
    chart_firms_workers(fw)
    sens = sensitivity(tidy, susb, months)
    sens.to_csv(os.path.join(CLEAN, "sensitivity.csv"), index=False)
    note(f"Charts 2-3 and the sensitivity check use the 3-month window {start} to {end} "
         "(clean/comparison_3mo.csv).")

    path = os.path.join(CLEAN, "notes.txt")
    marker = "\n## analysis.py\n"
    base = open(path).read().split(marker)[0]
    open(path, "w").write(base.rstrip("\n") + "\n" + marker + "".join(f"- {n}\n" for n in NOTES))
    print(fw.to_string(index=False), "\n")
    print(sens.to_string(index=False), "\n")
    print(open(os.path.join(CLEAN, "sensitivity.md")).read())


if __name__ == "__main__":
    main()
