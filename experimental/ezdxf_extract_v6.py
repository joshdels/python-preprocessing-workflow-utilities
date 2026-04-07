import math
import pathlib
import logging
from typing import Optional

import ezdxf
import ezdxf.lldxf.const
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _close_ring(points: list) -> list:
    """Ensure a point list forms a closed ring (first == last)."""
    if points and points[0] != points[-1]:
        points.append(points[0])
    return points


def _is_geometrically_closed(points: list, tol: float = 1e-6) -> bool:
    """
    True if the first and last vertices are within *tol* of each other.
    Catches polylines that are spatially closed but lack the 'closed' flag.

    Tolerance guide:
      1e-6  → metres / degrees (default, real-world coordinates)
      1e-2  → millimetre DXF drawings
      1e-1  → survey files with floating-point drift
    """
    if len(points) < 3:
        return False
    p0, p1 = points[0], points[-1]
    return math.hypot(p0[0] - p1[0], p0[1] - p1[1]) <= tol


# ── Entity parser ─────────────────────────────────────────────────────────────

def parse_entity(entity, snap_tolerance: float = 1e-6) -> Optional[object]:
    """
    Convert a DXF entity to a Shapely geometry.

    Polygon sources
    ---------------
    - LWPOLYLINE   : closed flag OR geometrically closed (first ≈ last vertex)
    - POLYLINE     : closed flag OR geometrically closed
    - HATCH        : PolylinePath (vertices) and EdgePath (edge list) boundaries
    - SOLID/3DFACE : quadrilateral / triangular faces
    - CIRCLE       : approximated with 64 segments

    LineString sources
    ------------------
    - LINE
    - LWPOLYLINE   : open
    - POLYLINE     : open
    - ARC          : approximated with 32 segments
    - SPLINE       : open (fit points preferred, falls back to control points)

    Point sources
    -------------
    - POINT
    - INSERT       (block reference — origin only)

    Parameters
    ----------
    entity         : ezdxf entity object
    snap_tolerance : distance threshold for geometric closure detection
    """
    etype = entity.dxftype()

    try:

        # ── Points ──────────────────────────────────────────────────────────
        if etype in ("POINT", "INSERT"):
            coords = (
                entity.dxf.insert if etype == "INSERT" else entity.dxf.location
            )
            return Point(coords.x, coords.y)

        # ── LINE ─────────────────────────────────────────────────────────────
        elif etype == "LINE":
            return LineString([
                (entity.dxf.start.x, entity.dxf.start.y),
                (entity.dxf.end.x,   entity.dxf.end.y),
            ])

        # ── LWPOLYLINE ───────────────────────────────────────────────────────
        elif etype == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points()]
            if not points:
                return None
            closed = entity.closed or _is_geometrically_closed(points, snap_tolerance)
            if closed and len(points) >= 3:
                return Polygon(_close_ring(points))
            return LineString(points) if len(points) > 1 else None

        # ── Old-style POLYLINE (2-D / 3-D / mesh) ────────────────────────────
        elif etype == "POLYLINE":
            pts = [
                (v.dxf.location.x, v.dxf.location.y)
                for v in entity.vertices
                if hasattr(v.dxf, "location")
            ]
            if not pts:
                return None
            is_closed = (
                bool(entity.dxf.flags & ezdxf.lldxf.const.POLYLINE_CLOSED)
                or _is_geometrically_closed(pts, snap_tolerance)
            )
            if is_closed and len(pts) >= 3:
                return Polygon(_close_ring(pts))
            return LineString(pts) if len(pts) > 1 else None

        # ── HATCH (filled area / boundary) ───────────────────────────────────
        elif etype == "HATCH":
            polys = []
            for path in entity.paths:
                # EdgePath: boundary stored as individual edge objects
                if hasattr(path, "edges"):
                    pts = []
                    for edge in path.edges:
                        if hasattr(edge, "start"):
                            pts.append((edge.start.x, edge.start.y))
                        if hasattr(edge, "end"):
                            pts.append((edge.end.x, edge.end.y))
                    if len(pts) >= 3:
                        polys.append(Polygon(_close_ring(pts)))
                # PolylinePath: boundary stored as a vertex list
                elif hasattr(path, "vertices"):
                    pts = [(v[0], v[1]) for v in path.vertices]
                    if len(pts) >= 3:
                        polys.append(Polygon(_close_ring(pts)))
            if not polys:
                return None
            return unary_union(polys) if len(polys) > 1 else polys[0]

        # ── SOLID / 3DFACE (quadrilateral / triangle faces) ──────────────────
        elif etype in ("SOLID", "3DFACE"):
            corners = []
            for attr in ("vtx0", "vtx1", "vtx2", "vtx3"):
                if entity.dxf.hasattr(attr):
                    v = getattr(entity.dxf, attr)
                    corners.append((v.x, v.y))
            # DXF SOLID stores vtx2 and vtx3 swapped — fix the bowtie
            if etype == "SOLID" and len(corners) == 4:
                corners[2], corners[3] = corners[3], corners[2]
            if len(corners) >= 3:
                return Polygon(_close_ring(corners))
            return None

        # ── CIRCLE → polygon approximation ───────────────────────────────────
        elif etype == "CIRCLE":
            cx, cy = entity.dxf.center.x, entity.dxf.center.y
            r      = entity.dxf.radius
            n      = 64  # segments — increase for smoother circles
            pts = [
                (cx + r * math.cos(2 * math.pi * i / n),
                 cy + r * math.sin(2 * math.pi * i / n))
                for i in range(n)
            ]
            return Polygon(pts)

        # ── ARC → open LineString approximation ──────────────────────────────
        elif etype == "ARC":
            cx, cy  = entity.dxf.center.x, entity.dxf.center.y
            r       = entity.dxf.radius
            start_a = math.radians(entity.dxf.start_angle)
            end_a   = math.radians(entity.dxf.end_angle)
            if end_a < start_a:
                end_a += 2 * math.pi
            n = 32
            pts = [
                (cx + r * math.cos(start_a + (end_a - start_a) * i / n),
                 cy + r * math.sin(start_a + (end_a - start_a) * i / n))
                for i in range(n + 1)
            ]
            return LineString(pts)

        # ── SPLINE ────────────────────────────────────────────────────────────
        elif etype == "SPLINE":
            # Prefer fit points; fall back to control points
            pts = (
                [(p.x, p.y) for p in entity.fit_points]
                if entity.fit_points
                else [(p.x, p.y) for p in entity.control_points]
            )
            if not pts:
                return None
            is_closed = (
                bool(entity.dxf.flags & ezdxf.lldxf.const.SPLINE_CLOSED)
                or _is_geometrically_closed(pts, snap_tolerance)
            )
            if is_closed and len(pts) >= 3:
                return Polygon(_close_ring(pts))
            return LineString(pts) if len(pts) > 1 else None

        else:
            return None

    except AttributeError as exc:
        logger.debug(f"Skipping {etype}: {exc}")
        return None


# ── DXF → GeoDataFrame ───────────────────────────────────────────────────────

def dxf_to_dataframe(
    doc: ezdxf.document.Drawing,
    snap_tolerance: float = 1e-6,
) -> gpd.GeoDataFrame:
    """
    Extract all supported entities from the DXF modelspace and return a
    GeoDataFrame with columns: geometry, layer, cad_type, geom_type.
    """
    msp  = doc.modelspace()
    rows = []

    for entity in msp:
        geom = parse_entity(entity, snap_tolerance=snap_tolerance)
        if geom:
            rows.append({
                "geometry":  geom,
                "layer":     entity.dxf.layer,
                "cad_type":  entity.dxftype().upper(),
                "geom_type": geom.geom_type,   # handy for downstream filtering
            })

    return gpd.GeoDataFrame(rows)


# ── Main export function ──────────────────────────────────────────────────────

def extract_to_geopackage(
    file_path: str,
    output_dir: str  = "output",
    output_name: str = "utilities.gpkg",
    crs: str         = "EPSG:26910",
    polygons_only: bool  = False,
    snap_tolerance: float = 1e-6,
) -> Optional[pathlib.Path]:
    """
    Convert a DXF file to a GeoPackage.

    Parameters
    ----------
    file_path      : Path to the source .dxf file.
    output_dir     : Directory to write the output file.
    output_name    : Output filename — must end in .gpkg.
    crs            : CRS string, e.g. 'EPSG:32651' for PH Zone 51N.
    polygons_only  : If True, only Polygon / MultiPolygon features are written.
    snap_tolerance : Vertex distance threshold for geometric closure detection.
                     1e-6 (default) suits metre / degree coordinates.
                     Loosen to 1e-2 for mm drawings or 1e-1 for survey drift.

    Returns
    -------
    pathlib.Path to the written .gpkg, or None on failure.

    Example
    -------
    >>> extract_to_geopackage(
    ...     "data/sample.dxf",
    ...     output_dir="data/gis_output",
    ...     crs="EPSG:32651",
    ...     polygons_only=True,
    ...     snap_tolerance=1e-2,
    ... )
    """
    logger.info("Extracting DXF to GIS — please wait…")

    input_path = pathlib.Path(file_path)
    if not input_path.exists() or input_path.suffix.lower() != ".dxf":
        logger.error(f"Invalid file path or format: {file_path}")
        return None

    try:
        doc = ezdxf.readfile(str(input_path))
        logger.info(f"Parsing geometry from {input_path.name}…")

        gdf = dxf_to_dataframe(doc, snap_tolerance=snap_tolerance)

        if gdf.empty:
            logger.warning("No valid geometry found in Modelspace.")
            return None

        if polygons_only:
            gdf = gdf[gdf["geom_type"].isin(["Polygon", "MultiPolygon"])].copy()
            logger.info(f"Polygon filter applied — {len(gdf)} polygon features retained.")
            if gdf.empty:
                logger.warning("No polygon features found after filtering.")
                return None

        gdf = gdf.set_geometry("geometry")
        gdf.crs = crs

        out_dir  = pathlib.Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / output_name

        gdf.to_file(str(out_path), layer="entities", driver="GPKG")
        logger.info(f"Exported {len(gdf)} features → {out_path.resolve()}")

        return out_path

    except Exception as exc:
        logger.error(f"Critical failure: {exc}")
        return None