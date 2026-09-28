"""Country outlines as SVG paths, so the page can draw its own interactive maps without a mapping library."""

import geopandas as gpd

from unga_speeches.config import RAW_DIR

NATURAL_EARTH = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
WIDTH = 1000  # the map's width in SVG units; its height follows from the projection
# detail finer than this, in metres, cannot be seen at page width and would only add weight
SIMPLIFY_METRES = 15000
# countries smaller than this, in km², also get a dot so they can be seen and clicked
SMALL_STATE_KM2 = 3000


def world() -> gpd.GeoDataFrame:
    from unga_speeches.http import Client

    dest = RAW_DIR / "naturalearth" / "ne_50m_admin_0_countries.zip"
    Client().fetch(NATURAL_EARTH, dest)
    frame = gpd.read_file(f"zip://{dest}")
    # plain ISO_A3 is blank for France and Norway, so take the "eh" column and fall back to the admin code
    frame["iso3"] = frame["ISO_A3_EH"].where(frame["ISO_A3_EH"] != "-99", frame["ADM0_A3"])
    frame = frame[frame["iso3"] != "ATA"].dissolve(by="iso3", as_index=False)[["iso3", "NAME", "geometry"]]
    return frame.to_crs("+proj=eqearth")


def _ring(coords, scale: float, x0: float, y1: float) -> str:
    points = [f"{(x - x0) * scale:.1f},{(y1 - y) * scale:.1f}" for x, y in coords]
    # consecutive points that round to the same place add nothing
    kept = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
    return "M" + "L".join(kept) + "Z" if len(kept) > 2 else ""


def paths() -> dict:
    """Every country as {iso3, name, d, dot}; dot is [x, y] for states too small to see, otherwise null."""
    frame = world()
    area_km2 = frame.area / 1e6
    frame["geometry"] = frame.geometry.simplify(SIMPLIFY_METRES, preserve_topology=True)
    x0, y0, x1, y1 = frame.total_bounds
    scale = WIDTH / (x1 - x0)
    shapes = []
    for (_, row), area in zip(frame.iterrows(), area_km2, strict=True):
        geom = row.geometry
        polygons = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        d = "".join(
            _ring(p.exterior.coords, scale, x0, y1) + "".join(_ring(i.coords, scale, x0, y1) for i in p.interiors) for p in polygons
        )
        point = row.geometry.representative_point()
        dot = [round((point.x - x0) * scale, 1), round((y1 - point.y) * scale, 1)] if area < SMALL_STATE_KM2 else None
        shapes.append({"iso3": row.iso3, "name": row.NAME, "d": d, "dot": dot})
    return {"width": WIDTH, "height": round((y1 - y0) * scale, 1), "shapes": shapes}
