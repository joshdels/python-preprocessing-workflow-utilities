import ezdxf
import geopandas as gpd
import pathlib
import logging
from shapely.geometry import Polygon, LineString
from shapely.ops import polygonize, snap
from typing import Optional, List

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------
# BASIC PARSERS
# -------------------------


def lwpolyline_to_polygon(entity) -> Optional[Polygon]:
    points = [(p[0], p[1]) for p in entity.get_points()]
    if len(points) < 3:
        return None
    if entity.closed or points[0] == points[-1]:
        return Polygon(points)
    return None


def polyline_to_polygon(entity) -> Optional[Polygon]:
    if not entity.is_closed:
        return None
    points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    if len(points) >= 3:
        return Polygon(points)
    return None


def hatch_to_polygon(entity) -> List[Polygon]:
    polygons = []
    for path in entity.paths:
        if hasattr(path, "vertices"):
            pts = [(pt[0], pt[1]) for pt in path.vertices]
            if len(pts) >= 3:
                polygons.append(Polygon(pts))
    return polygons


def line_to_linestring(entity) -> Optional[LineString]:
    try:
        return LineString(
            [
                (entity.dxf.start.x, entity.dxf.start.y),
                (entity.dxf.end.x, entity.dxf.end.y),
            ]
        )
    except:
        return None


# -------------------------
# SNAP LINES
# -------------------------


def snap_lines(lines: List[LineString], tolerance: float = 0.01) -> List[LineString]:
    """
    Snap nearby line endpoints to each other to fix tiny gaps.
    """
    snapped = []
    for i, line in enumerate(lines):
        l = line
        for j, other in enumerate(lines):
            if i != j:
                l = snap(l, other, tolerance)
        snapped.append(l)
    return snapped


# -------------------------
# DXF → POLYGONS
# -------------------------


def dxf_to_polygons(
    doc: ezdxf.document.Drawing, snap_tolerance: float = 0.01
) -> gpd.GeoDataFrame:
    msp = doc.modelspace()
    polygons = []
    lines = []

    for e in msp:
        etype = e.dxftype()

        # --- DIRECT POLYGONS ---
        if etype == "LWPOLYLINE":
            poly = lwpolyline_to_polygon(e)
            if poly:
                polygons.append(poly)
                continue

        elif etype == "POLYLINE":
            poly = polyline_to_polygon(e)
            if poly:
                polygons.append(poly)
                continue

        elif etype == "HATCH":
            polygons.extend(hatch_to_polygon(e))
            continue

        # --- COLLECT LINES (for polygonize) ---
        elif etype == "LINE":
            ls = line_to_linestring(e)
            if ls:
                lines.append(ls)

    # 🔥 Snap and polygonize loose lines
    if lines:
        logger.info("Snapping and polygonizing loose LINE entities...")
        snapped_lines = snap_lines(lines, snap_tolerance)
        generated = list(polygonize(snapped_lines))
        polygons.extend(generated)

    # Build GeoDataFrame
    gdf = gpd.GeoDataFrame(geometry=polygons)

    if gdf.empty:
        logger.warning("No polygons recovered.")
        return gdf

    # Clean geometry
    gdf["geometry"] = gdf["geometry"].buffer(0)
    # Remove duplicates
    gdf = gdf.drop_duplicates(subset=["geometry"])

    return gdf


# -------------------------
# EXPORT FUNCTION
# -------------------------


def extract_parcels(
    file_path: str,
    output_dir: str = "output",
    output_name: str = "parcels.gpkg",
    crs: str = "EPSG:4326",
    snap_tolerance: float = 0.01,
) -> Optional[pathlib.Path]:
    """
    Robust DXF → parcel polygons extraction pipeline
    """
    logger.info("Processing parcels (robust mode)...")

    input_path = pathlib.Path(file_path)
    if not input_path.exists():
        logger.error("DXF not found")
        return None

    try:
        doc = ezdxf.readfile(file_path)
        gdf = dxf_to_polygons(doc, snap_tolerance=snap_tolerance)

        if gdf.empty:
            logger.warning("No polygons recovered.")
            return None

        gdf.set_crs(crs, inplace=True)

        out_dir = pathlib.Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        out_path = out_dir / output_name
        gdf.to_file(out_path, layer="parcels", driver="GPKG")

        logger.info(f"Saved parcels to: {out_path}")
        return out_path

    except Exception as e:
        logger.error(f"Error during extraction: {e}")
        return None


