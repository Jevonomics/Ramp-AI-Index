"""
Exhibit layout in the style of Ramp Economics Lab charts: off-white background, large bold
headline (key words can take a series color), bold gray subtitle, square-swatch legend,
light horizontal grid, gray tick labels, source line at the bottom left.

    ex = Exhibit(height=6.4)
    ex.title([[("Ramp", ORANGE), ("'s rate is", INK)], [("more than double", INK)]])
    ex.subtitle("Share of U.S. businesses using AI, %")
    ex.legend([("Ramp", ORANGE), ("Census", NAVY)])
    ax = ex.axes(left=0.12, right=0.92)
    ...
    ex.source("Source: ...")
    ex.save("charts/name")

Fonts: Inter (SIL Open Font License), bundled in fonts/.
"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "*.ttf")):
    font_manager.fontManager.addfont(f)

BG, INK, SUB, TICK = "#fbfaf7", "#1c1c1a", "#6f6e6a", "#8f8e8a"
GRID, BASE = "#dddbd6", "#3a3a38"
ORANGE, NAVY, GRAY = "#e0702f", "#3f5ea6", "#b3b2ad"   # orange/navy validated as a pair

plt.rcParams.update({
    "font.family": "Inter", "font.size": 13, "text.color": INK,
    "axes.facecolor": BG, "figure.facecolor": BG, "savefig.facecolor": BG,
    "axes.edgecolor": BASE, "axes.linewidth": 1.2,
    "xtick.color": TICK, "ytick.color": TICK, "xtick.labelsize": 14, "ytick.labelsize": 14,
    "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 8, "ytick.major.pad": 8,
    "svg.fonttype": "path",   # embed glyph outlines so SVGs look the same without Inter
})

MARGIN = 0.32  # inches, left/right page margin
DPI = 200


class Exhibit:
    def __init__(self, width=6.2, height=6.4):
        # Measure text at the output resolution, or headline pieces drift apart.
        self.fig = plt.figure(figsize=(width, height), dpi=DPI)
        self.w, self.h = width, height
        self.cursor = 0.30            # inches from the top for the next header element
        self.footer = 0.0             # inches reserved at the bottom by source lines
        self._r = self.fig.canvas.get_renderer()

    # header ------------------------------------------------------------------
    def _y(self):
        return 1 - self.cursor / self.h

    def _width(self, t):
        return t.get_window_extent(self._r).width / self.fig.bbox.width

    def title(self, lines, size=23):
        """lines: list of lines, each a list of (text, color) pieces."""
        for line in lines:
            x = MARGIN / self.w
            for text, color in line:
                t = self.fig.text(x, self._y(), text, color=color, fontsize=size,
                                  family="Inter Display", weight="bold", va="top")
                x += self._width(t)
            self.cursor += size * 1.18 / 72
        self.cursor += 0.16

    def subtitle(self, text, size=12.5):
        self.fig.text(MARGIN / self.w, self._y(), text, color=SUB, fontsize=size,
                      weight="semibold", va="top")
        self.cursor += size * 1.3 / 72 + 0.2

    def legend(self, items, size=13):
        """items: (label, color) pairs, laid out in one row with square swatches."""
        x, side = MARGIN / self.w, size * 0.8 / 72
        y = self._y()
        for label, color in items:
            self.fig.add_artist(Rectangle((x, y - side / self.h * 1.05), side / self.w,
                                          side / self.h, color=color,
                                          transform=self.fig.transFigure))
            t = self.fig.text(x + (side + 0.07) / self.w, y, label, fontsize=size, va="top",
                              color=INK)
            x += (side + 0.07) / self.w + self._width(t) + 0.17 / self.w
        self.cursor += size * 1.3 / 72 + 0.3

    # body and footer ---------------------------------------------------------
    def _wrap(self, text, size):
        """Split text into lines that fit between the page margins."""
        avail = 1 - 2 * MARGIN / self.w
        probe = self.fig.text(0, 0, "", fontsize=size)
        lines, cur = [], ""
        for word in text.split():
            probe.set_text(f"{cur} {word}".strip())
            if cur and self._width(probe) > avail:
                lines.append(cur)
                cur = word
            else:
                cur = f"{cur} {word}".strip()
        probe.remove()
        return lines + [cur]

    def source(self, *paragraphs, size=9.5):
        """Notes and source at the bottom left, wrapped to the page; first paragraph on top."""
        lines = [l for p in paragraphs for l in self._wrap(p, size)]
        y = 0.22
        for line in reversed(lines):
            self.fig.text(MARGIN / self.w, y / self.h, line, color=SUB, fontsize=size,
                          va="bottom")
            y += size * 1.35 / 72
        self.footer = y + 0.25

    def axes(self, left=0.1, right=0.95, bottom_pad=0.55):
        """Axes filling the space between the header and the footer reserve (set source()
        first). bottom_pad: inches for x tick labels."""
        top = self._y() - 0.1 / self.h
        bottom = (self.footer + bottom_pad) / self.h
        ax = self.fig.add_axes([left, bottom, right - left, top - bottom])
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.grid(axis="y", color=GRID, lw=1)
        ax.set_axisbelow(True)
        return ax

    def save(self, path):
        for ext in ("png", "svg"):
            self.fig.savefig(f"{path}.{ext}", dpi=DPI)
        plt.close(self.fig)
