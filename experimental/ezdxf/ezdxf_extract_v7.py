import ezdxf
import geopandas as gpd
import pathlib
import logging
from shapely.geometry import Point, LineString, Polygon
from typing import Optional, List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_point(entity) -> Optional[Point]:
    try:
        coords = (
            entity.dxf.insert if entity.dxftype() == "INSERT" else entity.dxf.location
        )
        return Point(coords.x, coords.y)
    except AttributeError:
        return None


def parse_line(entity) -> Optional[LineString]:
    return LineString(
        [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
    )


def parse_polygon(entity) -> Optional[Polygon]:
    """
    Parse a polygon-like entity from DXF.
    Supports:
    - Closed LWPOLYLINE
    - HATCH boundary paths
    """
    try:
        etype = entity.dxftype()
        if etype == "LWPOLYLINE" and entity.closed:
            points = [(p[0], p[1]) for p in entity.get_points()]
            if len(points) >= 3:
                return Polygon(points)
        elif etype == "HATCH":
            if entity.paths:
                path = entity.paths[0]
                points = [(pt[0], pt[1]) for pt in path.vertices]
                if len(points) >= 3:
                    return Polygon(points)
        return None
    except AttributeError:
        return None


def parse_polyline(entity) -> Optional[LineString]:
    points = [(p[0], p[1]) for p in entity.get_points()]
    return LineString(points) if len(points) > 1 else None



# def parse_entity(entity) -> Optional[object]:
#     """
#     Universal parser for DXF entities:
#     - POINT / INSERT -> Point
#     - LINE -> LineString
#     - LWPOLYLINE -> Polygon if closed, else LineString
#     - HATCH -> Polygon
#     """
#     etype = entity.dxftype()
    
#     try:
#         if etype == "POINT" or etype == "INSERT":
#             coords = entity.dxf.insert if etype == "INSERT" else entity.dxf.location
#             return Point(coords.x, coords.y)

#         elif etype == "LINE":
#             return LineString([(entity.dxf.start.x, entity.dxf.start.y),
#                                (entity.dxf.end.x, entity.dxf.end.y)])

#         elif etype == "LWPOLYLINE":
#             points = [(p[0], p[1]) for p in entity.get_points()]
#             if entity.closed and len(points) >= 3:
#                 return Polygon(points)
#             elif len(points) > 1:
#                 return LineString(points)
#             else:
#                 return None

#         elif etype == "HATCH":
#             if entity.paths:
#                 path = entity.paths[0]
#                 points = [(pt[0], pt[1]) for pt in path.vertices]
#                 if len(points) >= 3:
#                     return Polygon(points)
#             return None

#         else:
#             return None

#     except AttributeError:
#         return None




def dxf_to_dataframe(doc: ezdxf.document.Drawing) -> gpd.GeoDataFrame:
    msp = doc.modelspace()
    rows = []

    parsers = {
        "POINT": parse_point,
        "INSERT": parse_point,
        "LINE": parse_line,
        "LWPOLYLINE": parse_polyline,
        "POLYGON": parse_polygon,
        "HATCH": parse_polygon,
    }

    for entity in msp:
        etype = entity.dxftype().upper()
        if etype in parsers:
            geom = parsers[etype](entity)
            if geom:
                rows.append(
                    {"geometry": geom, "layer": entity.dxf.layer, "cad_type": etype}
                )

    return gpd.GeoDataFrame(rows)

# def dxf_to_dataframe(doc: ezdxf.document.Drawing) -> gpd.GeoDataFrame:
#     msp = doc.modelspace()
#     rows = []

#     for entity in msp:
#         geom = parse_entity(entity)
#         if geom:
#             rows.append({
#                 "geometry": geom,
#                 "layer": entity.dxf.layer,
#                 "cad_type": entity.dxftype().upper()
#             })

#     return gpd.GeoDataFrame(rows)

def extract_to_geopackage(
    file_path: str,
    output_dir: str = "output",
    output_name: str = "utilities.gpkg",
    crs: str = "EPSG:26910",
) -> Optional[pathlib.Path]:
    """
    Return a process conversion from dxf to geopackage
    Ready for use for the analyst

    Example:
    - extract_to_geopackage("../data/sample.dxf", "../data/gis_data")"""

    logger.info("Extracting the DXF to GIS, Please Wait")

    input_path = pathlib.Path(file_path)

    if not input_path.exists() or input_path.suffix.lower() != ".dxf":
        logger.error(f"Invalid file path or format: {file_path}")
        return None

    try:
        doc = ezdxf.readfile(file_path)

        logger.info(f"Extracting geometry from {input_path.name}...")
        gdf = dxf_to_dataframe(doc)

        if gdf.empty:
            logger.warning("No valid geometry found in Modelspace.")
            return None

        gdf.crs = crs
        out_dir = pathlib.Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / output_name

        gdf.to_file(out_path, layer="entities", driver="GPKG")
        logger.info(f"Successfully exported to {out_path.resolve()}")

        return out_path

    except Exception as e:
        logger.error(f"Critical failure: {e}")
        return None
