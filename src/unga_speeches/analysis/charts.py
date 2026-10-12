"""The look shared by the analysis notebooks: the palette, the type, square figures for slides, and the world map."""

from functools import cache

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

from unga_speeches.config import PROJECT_ROOT

# a pastel UN blue and two partners that pass the colourblind checks, a UN blue ramp for magnitude, and neutral ink and fills
BLUE, ROSE, HONEY = "#5abdf2", "#df7a9b", "#d1ad41"
BLUE_INK, ROSE_INK = "#1d78ad", "#b04e74"  # darker steps of the same hues, for text and for the stronger of two shades
SURFACE, INK, INK_2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
NOT_RAISED, NO_SPEECH = "#ebe9e3", "#ffffff"
RAMP = LinearSegmentedColormap.from_list("un_blue", ["#f1f9fe", "#c9eaff", "#a4d9f9", "#74c2ee", "#3ea3d7", "#1d78ad"])
SQUARE = (9, 9)
FIG_DIR = PROJECT_ROOT / "notebooks/figures"
NATURAL_EARTH = PROJECT_ROOT / "data/raw/naturalearth/ne_50m_admin_0_countries.zip"
SMALL_AREA = 8e9  # square metres in the Robinson projection; smaller states are also drawn as a dot so they can be seen


def style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "text.color": INK,
            "axes.labelcolor": INK_2,
            "xtick.color": MUTED,
            "ytick.color": INK_2,
            "axes.edgecolor": GRID,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 10,
        }
    )


def finalize(ax, title: str, subtitle: str = "") -> None:
    """A bold headline that says the finding, and a muted line under it that says what is measured."""
    ax.set_title(title, loc="left", pad=22 if subtitle else 10)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=INK_2, fontsize=9, va="bottom")


@cache
def world() -> gpd.GeoDataFrame:
    shapes = gpd.read_file(f"zip://{NATURAL_EARTH}")
    return shapes[shapes.ADMIN != "Antarctica"].to_crs("ESRI:54030")


def world_map(ax, colour_of: dict[str, str], title: str | None = None) -> None:
    """Fill each country by colour_of[iso3]; countries left out stay white, and small states also get a dot."""
    shapes = world()
    fill = shapes.ISO_A3_EH.map(colour_of).fillna(NO_SPEECH)
    shapes.plot(ax=ax, color=fill, edgecolor="#cfccc4", linewidth=0.25)
    small = shapes[(shapes.area < SMALL_AREA) & shapes.ISO_A3_EH.isin(colour_of.keys())].representative_point()
    ax.scatter(small.x, small.y, s=9, c=fill[small.index], edgecolors="#8d8a82", linewidths=0.3, zorder=3)
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=10)


def legend(fig, items: list[tuple[str, str]], y: float = 0.01) -> None:
    fig.legend(
        handles=[Patch(facecolor=c, edgecolor="#bdb9b0", label=label) for label, c in items],
        loc="lower center",
        ncol=min(len(items), 4),
        frameon=False,
        bbox_to_anchor=(0.5, y),
        fontsize=9,
    )


def show(fig, name: str) -> None:
    """Save the figure as a square png for slides, then show it with its headline as alt text, which the site page copies onto the image."""
    from IPython.display import display

    FIG_DIR.mkdir(exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.png", dpi=200)  # no tight bounding box, so the png stays exactly 1:1
    title = fig._suptitle.get_text() if fig._suptitle else fig.axes[0].get_title(loc="left")
    display(fig, metadata={"image/png": {"alt": " ".join(title.split())}})
    plt.close(fig)
