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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import build_dataset as b

CLEAN, CHARTS = b.CLEAN, b.CHARTS
RAMP_C, CENSUS_C = "#2a78d6", "#eb6834"        # validated pair (dataviz palette slots 1-2)
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
SOURCE_LINE = ("Sources: Ramp AI Index (FRED); U.S. Census Bureau, Business Trends and Outlook "
               "Survey; Census SUSB 2022 for weights.")
NOTES = []
plt.rcParams.update({"font.size": 11, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "svg.fonttype": "none",
                     "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]})


def note(msg):
    NOTES.append(msg)


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x" if ax.get_xlabel() else "y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def title(fig, text):
    """Title aligned to the figure's left edge (reads better at phone width)."""
    fig.text(0.02, 0.975, text, fontsize=14, color=INK, ha="left", va="top")


def save(fig, name, source=SOURCE_LINE):
    fig.text(0.015, 0.012, source, fontsize=8, color=INK2, ha="left", va="bottom", wrap=True)
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(CHARTS, f"{name}.{ext}"), dpi=200, facecolor="white")
    plt.close(fig)


# ------------------------------------------------------------- chart 1 ---
def chart_gap(tidy):
    ov = tidy[tidy.dimension == "overall"].copy()
    ov["t"] = pd.PeriodIndex(ov.month, freq="M").to_timestamp() + pd.Timedelta(days=14)
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    eras = [("paid_transactions", RAMP_C, "-", "Ramp: paid for AI tools"),
            ("goods_services", CENSUS_C, (0, (2, 2)), "Census: used AI 'in producing goods or services'"),
            ("any_function", CENSUS_C, "-", "Census: used AI 'in any business function'"),
            ("super_intelligence", CENSUS_C, "none", "Census: 'Super Intelligence' wording")]
    for w, col, ls, lab in eras:
        g = ov[ov.wording == w].sort_values("t")
        if g.empty:
            continue
        marker = "o" if len(g) == 1 else None
        ax.plot(g.t, g.rate, color=col, ls=ls, lw=2, marker=marker, ms=6, mfc="white",
                mew=2, label=lab)
        last = g.iloc[-1]
        if w in ("paid_transactions", "any_function"):
            ax.annotate(f"{last.rate:.0f}%", (last.t, last.rate), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=10, color=INK)
    for d in b.WORDING_BREAKS.values():
        ax.axvline(pd.Timestamp(d), color=INK2, lw=0.8, ls=(0, (4, 3)))
    ax.text(pd.Timestamp(b.WORDING_BREAKS["any_function"]), 74, "Census rewords\nthe question ",
            ha="right", va="top", fontsize=9, color=INK2)
    ax.text(pd.Timestamp(b.WORDING_BREAKS["super_intelligence"]), 74, "and again ",
            ha="right", va="top", fontsize=9, color=INK2)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.set_ylim(0, 75)
    ax.set_ylabel("% of businesses")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    style(ax)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, 1.0))
    title(fig, "Share of U.S. businesses using AI")
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    save(fig, "chart1_gap", SOURCE_LINE.replace("; Census SUSB 2022 for weights", "") +
         " Census biweekly periods averaged to months; no Census data Oct 6 - Nov 16, 2025 (shutdown).")


# ------------------------------------------------------------- chart 2 ---
SIZE_ORDER = ["Small (1-24)", "Medium (25-99)", "Large (100+)"]


def chart_groups(comp):
    blocks = [(None, comp[comp.dimension == "overall"]),
              ("By firm size (employees)", comp[comp.dimension == "size"].sort_values("ratio")),
              ("By sector", comp[comp.dimension == "sector"].sort_values("ratio"))]
    rows, y, heads = [], 0, []
    for head, g in reversed(blocks):          # build bottom-up
        for _, r in g.iterrows():
            rows.append((y, r)); y += 1
        if head:
            heads.append((y, head)); y += 1.3
        else:
            y += 0.6
    fig, ax = plt.subplots(figsize=(7.2, 7.4))
    for yy, r in rows:
        ax.plot([r.census_rate, r.ramp_rate], [yy, yy], color=GRID, lw=3, zorder=1,
                solid_capstyle="round")
        ax.scatter(r.census_rate, yy, s=70, color=CENSUS_C, edgecolor="white", lw=2, zorder=3)
        ax.scatter(r.ramp_rate, yy, s=70, color=RAMP_C, edgecolor="white", lw=2, zorder=3)
        ax.text(-2, yy, r.group.replace("Accommodation & Food", "Accommodation & food")
                .replace("Finance & Insurance", "Finance & insurance").replace("Retail Trade", "Retail"),
                ha="right", va="center", fontsize=10, color=INK)
        ax.text(101, yy, f"{r.ratio:.1f}×", ha="left", va="center", fontsize=10, color=INK)
    for yy, head in heads:
        ax.text(-2, yy - 0.35, head, ha="right", va="center", fontsize=10, color=INK2,
                fontweight="bold")
    ax.text(101, y - 0.6, "Ramp ÷\nCensus", ha="left", va="center", fontsize=9, color=INK2)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, y - 0.2)
    ax.set_yticks([])
    ax.set_xlabel("% of businesses using AI, " + comp.months.iloc[0].replace(" to ", " – ")
                  + " average")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.spines[["left"]].set_visible(False)
    style(ax)
    ax.scatter([], [], s=70, color=RAMP_C, label="Ramp (paid AI, share of Ramp customers)")
    ax.scatter([], [], s=70, color=CENSUS_C, label="Census BTOS (self-reported use)")
    fig.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0.01, 0.94), ncol=1)
    title(fig, "Ramp vs. Census, group by group")
    fig.subplots_adjust(left=0.36, right=0.86, top=0.84, bottom=0.12)
    save(fig, "chart2_groups", SOURCE_LINE + " Census size classes regrouped to Ramp's "
         "buckets with SUSB firm counts.")


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
    show = fw[~fw.measure.str.startswith("published")].iloc[::-1].reset_index(drop=True)
    labels = {"share of firms (rebuilt from size classes)": "Share of firms",
              "share of firms (size buckets, SUSB firm weights)": "Share of firms",
              "share of workers (approx.)": "Share of workers*"}
    ys = [0, 1, 2.6, 3.6]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    for yy, (_, r) in zip(ys, show.iterrows()):
        col = RAMP_C if r.source == "Ramp" else CENSUS_C
        ax.barh(yy, r.rate, height=0.62, color=col)
        ax.text(r.rate + 1, yy, f"{r.rate:.0f}%", va="center", fontsize=10, color=INK)
        ax.text(-1.5, yy, labels[r.measure], ha="right", va="center", fontsize=10, color=INK)
    for yy, src in [(1.65, "Ramp"), (4.25, "Census BTOS")]:
        ax.text(-1.5, yy, src, ha="right", va="center", fontsize=10, color=INK2, fontweight="bold")
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, 4.6)
    ax.set_yticks([])
    ax.set_xlabel("% using AI, " + fw.months.iloc[0].replace(" to ", " – ") + " average")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.spines[["left"]].set_visible(False)
    style(ax)
    title(fig, "Counting workers instead of firms raises both rates")
    fig.subplots_adjust(left=0.27, right=0.95, top=0.86, bottom=0.30)
    save(fig, "chart3_firms_workers", "*Approximation: each size class's AI rate weighted by "
         "its SUSB 2022 employment (Census: 7 BTOS classes; Ramp: 3 size buckets).\n" + SOURCE_LINE)


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

    chart_gap(tidy)
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
