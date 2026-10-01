"""Static charts for the page, drawn with matplotlib in a light and a dark version so each theme gets its own steps; maps are drawn in the browser."""

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# the reference palette's steps, chosen per surface
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "ink2": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "series": ["#2a78d6", "#eb6834", "#1baf7a"],
        "none": "#dcdbd4",
        "absent": "#fcfcfb",
        "edge": "#fcfcfb",
        "ordinal": ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#ffffff",
        "ink2": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "series": ["#3987e5", "#d95926", "#199e70"],
        "none": "#484844",
        "absent": "#1a1a19",
        "edge": "#1a1a19",
        "ordinal": ["#184f95", "#3987e5", "#86b6ef", "#cde2fb"],
    },
}


def _style(theme: dict) -> None:
    plt.rcParams.update(
        {
            "svg.fonttype": "none",  # keep text as text, so the page's own font renders it
            "font.family": "sans-serif",
            "font.sans-serif": ["system-ui", "-apple-system", "Segoe UI", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "text.color": theme["ink"],
            "axes.labelcolor": theme["ink2"],
            "xtick.color": theme["muted"],
            "ytick.color": theme["muted"],
            "axes.edgecolor": theme["axis"],
            "figure.facecolor": theme["surface"],
            "axes.facecolor": theme["surface"],
            "savefig.facecolor": theme["surface"],
            "svg.hashsalt": "unga-speeches",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _legend(ax, items: list[tuple[str, str]], theme: dict, loc: str = "lower left", **kwargs) -> None:
    handles = [
        Patch(facecolor=c, edgecolor=theme["axis"], linewidth=0.4, label=label, hatch="////" if c == theme["absent"] else None)
        for label, c in items
    ]
    ax.legend(handles=handles, frameon=False, loc=loc, fontsize=9, labelcolor=theme["ink2"], **kwargs)


def _save(fig, out_dir: Path, name: str, mode: str) -> None:
    # no timestamp and a fixed id salt, so the same data always gives the same file
    fig.savefig(out_dir / f"{name}-{mode}.svg", bbox_inches="tight", pad_inches=0.08, metadata={"Date": None})
    plt.close(fig)


def trend_multiples(trends: list[dict], out_dir: Path, issues: list[str]) -> None:
    """Small multiples, one line each, on a shared 0–100% axis so the panels compare directly."""
    frame = pd.DataFrame(trends)
    for mode, theme in THEMES.items():
        _style(theme)
        fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.2), sharex=True, sharey=True)
        for ax, issue in zip(axes.flat, issues, strict=True):
            ax.grid(axis="y", color=theme["grid"], linewidth=0.6)
            ax.plot(frame["year"], frame[issue], color=theme["series"][0], linewidth=2, solid_capstyle="round")
            last = frame.iloc[-1]
            ax.scatter([last["year"]], [last[issue]], s=28, color=theme["series"][0], edgecolors=theme["surface"], linewidths=1.5, zorder=3)
            ax.annotate(
                f"{last[issue]:.0%}",
                (last["year"], last[issue]),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=10,
                color=theme["ink"],
            )
            ax.set_title(issue, loc="left", fontsize=10.5, color=theme["ink"])
            ax.set_ylim(0, 1)
            ax.set_yticks([0, 0.5, 1], ["0", "50%", "100%"])
            ax.set_xticks([2012, 2016, 2020, 2024])
            ax.set_xlim(frame["year"].min() - 0.5, frame["year"].max() + 2.2)
        fig.subplots_adjust(wspace=0.12, hspace=0.35)
        _save(fig, out_dir, "trend-issues", mode)


def leaders_trend(trends: list[dict], out_dir: Path) -> None:
    frame = pd.DataFrame(trends)
    for mode, theme in THEMES.items():
        _style(theme)
        fig, ax = plt.subplots(figsize=(10, 3.2))
        ax.grid(axis="y", color=theme["grid"], linewidth=0.6)
        ax.plot(
            frame["year"],
            frame["g20_heads"],
            color=theme["series"][0],
            linewidth=2,
            marker="o",
            markersize=5,
            markeredgecolor=theme["surface"],
        )
        for _, r in frame.iterrows():
            if r["year"] in (2020, frame["year"].max(), frame["year"].max() - 1):
                note = " (virtual)" if r["year"] == 2020 else ""
                ax.annotate(
                    f"{int(r['g20_heads'])}{note}",
                    (r["year"], r["g20_heads"]),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    fontsize=9.5,
                    color=theme["ink"],
                )
        ax.set_ylim(0, 19)
        ax.set_yticks([0, 5, 10, 15, 19])
        ax.set_ylabel("G20 members sending their leader (of 19)")
        _save(fig, out_dir, "trend-leaders", mode)


def length_swarm(rows: list[dict], out_dir: Path, regions: list[str]) -> None:
    """Every speech as a dot, by region, with the outliers named."""
    frame = pd.DataFrame([r for r in rows if r["region"] in regions])
    for mode, theme in THEMES.items():
        _style(theme)
        fig, ax = plt.subplots(figsize=(10, 4.2))
        ax.grid(axis="x", color=theme["grid"], linewidth=0.6)
        sns.swarmplot(
            data=frame,
            x="words",
            y="region",
            order=regions,
            color=theme["series"][0],
            size=4.2,
            ax=ax,
            edgecolor=theme["surface"],
            linewidth=0.3,
        )
        for _, r in frame.nlargest(3, "words").iterrows():
            ax.annotate(
                r["delegation"].split(" (")[0].replace("United States of America", "United States"),
                (r["words"], regions.index(r["region"])),
                xytext=(-6, 10),
                textcoords="offset points",
                ha="right",
                fontsize=9,
                color=theme["ink2"],
            )
        median = frame["words"].median()
        ax.axvline(median, color=theme["ink2"], linewidth=1, linestyle=(0, (3, 3)))
        ax.annotate(
            f"median {median:,.0f} words", (median, -0.6), xytext=(4, 0), textcoords="offset points", fontsize=9, color=theme["ink2"]
        )
        ax.set_xlabel("Words in the speech")
        ax.set_ylabel("")
        _save(fig, out_dir, "swarm-length", mode)


def lens_dots(by_region: list[dict], out_dir: Path, lenses: list[str]) -> None:
    """A dot per region on each lens's line, so the spread between regions is the thing the eye reads."""
    for mode, theme in THEMES.items():
        _style(theme)
        fig, ax = plt.subplots(figsize=(10, 3.4))
        ax.grid(axis="x", color=theme["grid"], linewidth=0.6)
        highlight = {"Europe": theme["series"][0], "Africa": theme["series"][1]}
        for i, lens in enumerate(lenses):
            values = [g[lens] for g in by_region]
            ax.plot([min(values), max(values)], [i, i], color=theme["axis"], linewidth=2, solid_capstyle="round", zorder=1)
            for g in by_region:
                colour = highlight.get(g["group"], theme["muted"])
                ax.scatter(
                    g[lens], i, s=60 if g["group"] in highlight else 30, color=colour, edgecolors=theme["surface"], linewidths=1.2, zorder=3
                )
        # wrapped, because the browser's font runs wider than the one matplotlib measures with
        ax.set_yticks(
            range(len(lenses)), [lens.replace(" and ", " and\n").replace(" institutionalism", "\ninstitutionalism") for lens in lenses]
        )
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel("Words from the lens's vocabulary per 1,000 words")
        _legend(
            ax,
            [("Europe", highlight["Europe"]), ("Africa", highlight["Africa"]), ("Other regions", theme["muted"])],
            theme,
            loc="lower right",
        )
        _save(fig, out_dir, "dots-lenses", mode)
