import ezdxf
import geopandas as gpd
import pathlib
import logging
from shapely.geometry import Point, LineString
from typing import Optional, List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


logger.info("Extracting the DXF to GIS, Please Wait")


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


def parse_polyline(entity) -> Optional[LineString]:
    points = [(p[0], p[1]) for p in entity.get_points()]
    return LineString(points) if len(points) > 1 else None


def dxf_to_dataframe(doc: ezdxf.document.Drawing) -> gpd.GeoDataFrame:
    msp = doc.modelspace()
    rows = []

    parsers = {
        "POINT": parse_point,
        "INSERT": parse_point,
        "LINE": parse_line,
        "LWPOLYLINE": parse_polyline,
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
