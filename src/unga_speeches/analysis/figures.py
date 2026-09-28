"""Static figures for the page, drawn with matplotlib in a light and a dark version so each theme gets its own steps."""

from pathlib import Path

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from unga_speeches.config import RAW_DIR  # noqa: E402

NATURAL_EARTH = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
# countries smaller than this, in km², also get a dot so they can be seen
SMALL_STATE_KM2 = 3000
SIMPLIFY_METRES = 8000

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
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def world() -> gpd.GeoDataFrame:
    from unga_speeches.http import Client

    dest = RAW_DIR / "naturalearth" / "ne_50m_admin_0_countries.zip"
    Client().fetch(NATURAL_EARTH, dest)
    frame = gpd.read_file(f"zip://{dest}")
    # plain ISO_A3 is blank for France and Norway, so take the "eh" column and fall back to the admin code
    frame["iso3"] = frame["ISO_A3_EH"].where(frame["ISO_A3_EH"] != "-99", frame["ADM0_A3"])
    frame = frame[frame["iso3"] != "ATA"].dissolve(by="iso3", as_index=False)[["iso3", "geometry"]].to_crs("+proj=eqearth")
    # detail finer than this, in metres, is invisible at page width and would make each map several megabytes
    frame["geometry"] = frame.geometry.simplify(SIMPLIFY_METRES, preserve_topology=True)
    return frame


def _map(ax, world_frame: gpd.GeoDataFrame, colours: dict[str, str], theme: dict) -> None:
    """Fill each state by its colour; states without a colour are drawn as absent; small states also get a dot."""
    frame = world_frame.assign(fill=world_frame["iso3"].map(colours))
    # places with no speech, including territories that are not members, are hatched so they never read as "neither"
    absent = frame[frame["fill"].isna()]
    absent.plot(ax=ax, color=theme["absent"], edgecolor=theme["axis"], linewidth=0.2, hatch="////")
    frame = frame[frame["fill"].notna()]
    frame.plot(ax=ax, color=frame["fill"], edgecolor=theme["edge"], linewidth=0.3)
    small = frame[(frame.area / 1e6 < SMALL_STATE_KM2) & frame["iso3"].isin(colours)]
    points = small.representative_point()
    ax.scatter(points.x, points.y, s=14, c=small["fill"], edgecolors=theme["edge"], linewidths=0.6, zorder=3)
    ax.set_axis_off()


def _legend(ax, items: list[tuple[str, str]], theme: dict, loc: str = "lower left", **kwargs) -> None:
    handles = [
        Patch(facecolor=c, edgecolor=theme["axis"], linewidth=0.4, label=label, hatch="////" if c == theme["absent"] else None)
        for label, c in items
    ]
    ax.legend(handles=handles, frameon=False, loc=loc, fontsize=9, labelcolor=theme["ink2"], **kwargs)


# maps are raster, since a vector coastline runs to megabytes; charts stay vector so their text stays sharp
MAP_DPI = 170


def _save(fig, out_dir: Path, name: str, mode: str) -> None:
    raster = name.startswith("map-")
    fig.savefig(
        out_dir / f"{name}-{mode}.{'png' if raster else 'svg'}", bbox_inches="tight", pad_inches=0.08, dpi=MAP_DPI if raster else "figure"
    )
    plt.close(fig)


def wars_map(rows: list[dict], world_frame, out_dir: Path) -> None:
    for mode, theme in THEMES.items():
        _style(theme)
        blue, orange, aqua = theme["series"]
        colours = {}
        for r in rows:
            if not r["iso3"]:
                continue
            ukraine, gaza = "Ukraine" in r["issues"], "Gaza and Palestine" in r["issues"]
            colours[r["iso3"]] = aqua if ukraine and gaza else blue if ukraine else orange if gaza else theme["none"]
        fig, ax = plt.subplots(figsize=(10, 5.2))
        _map(ax, world_frame, colours, theme)
        _legend(
            ax,
            [
                ("Ukraine and Gaza", aqua),
                ("Ukraine only", blue),
                ("Gaza only", orange),
                ("Neither", theme["none"]),
                ("No speech", theme["absent"]),
            ],
            theme,
            ncol=5,
            bbox_to_anchor=(0, -0.06),
        )
        _save(fig, out_dir, "map-wars", mode)


def issue_map(rows: list[dict], world_frame, out_dir: Path, issue: str, name: str) -> None:
    for mode, theme in THEMES.items():
        _style(theme)
        colours = {r["iso3"]: theme["series"][0] if issue in r["issues"] else theme["none"] for r in rows if r["iso3"]}
        fig, ax = plt.subplots(figsize=(10, 5.2))
        _map(ax, world_frame, colours, theme)
        _legend(
            ax,
            [
                (f"Mentions {issue.lower() if issue != 'Artificial intelligence' else 'AI'}", theme["series"][0]),
                ("Does not", theme["none"]),
                ("No speech", theme["absent"]),
            ],
            theme,
            ncol=3,
            bbox_to_anchor=(0, -0.06),
        )
        _save(fig, out_dir, name, mode)


RANK_ORDER = [
    ("Head of state or government", {"head_of_state_or_government"}),
    ("Deputy head", {"deputy_head"}),
    ("Foreign minister", {"foreign_minister"}),
    ("Other minister or diplomat", {"other_minister", "diplomat", "other"}),
]


def rank_map(rows: list[dict], world_frame, out_dir: Path) -> None:
    for mode, theme in THEMES.items():
        _style(theme)
        # an ordered scale: the more senior the speaker, the stronger the step
        steps = dict(zip([label for label, _ in RANK_ORDER], reversed(theme["ordinal"]), strict=True))
        colours = {}
        for r in rows:
            for label, groups in RANK_ORDER:
                if r["iso3"] and r["role_group"] in groups:
                    colours[r["iso3"]] = steps[label]
        fig, ax = plt.subplots(figsize=(10, 5.2))
        _map(ax, world_frame, colours, theme)
        _legend(
            ax,
            [(label, steps[label]) for label, _ in RANK_ORDER] + [("No speech", theme["absent"])],
            theme,
            ncol=5,
            bbox_to_anchor=(0, -0.06),
        )
        _save(fig, out_dir, "map-rank", mode)


def lens_maps(rows: list[dict], world_frame, out_dir: Path, lenses: list[str]) -> None:
    """One small map per lens, highlighting the states whose speech leans that way."""
    for mode, theme in THEMES.items():
        _style(theme)
        fig, axes = plt.subplots(2, 2, figsize=(11, 6.2))
        for ax, lens in zip(axes.flat, lenses, strict=True):
            colours = {r["iso3"]: theme["series"][0] if r["lean"] == lens else theme["none"] for r in rows if r["iso3"]}
            _map(ax, world_frame, colours, theme)
            count = sum(r["lean"] == lens for r in rows)
            ax.set_title(f"{lens} ({count})", loc="left", fontsize=11, color=theme["ink"], pad=2)
        fig.subplots_adjust(wspace=0.02, hspace=0.12)
        _save(fig, out_dir, "map-lenses", mode)


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
