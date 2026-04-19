import ezdxf
import geopandas as gpd
import pathlib
import logging
from shapely.geometry import Point, LineString
from typing import Optional, List, Dict, Any

# 1. Setup Logging (Better than print for production/servers)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# 2. Individual Geometry Parsers (Easier to test and maintain)
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


# 3. The Core Processing Engine
def dxf_to_dataframe(doc: ezdxf.document.Drawing) -> gpd.GeoDataFrame:
    msp = doc.modelspace()
    rows = []

    # Mapping table for cleaner logic
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
                    {"geometry": geom, "layer": entity.dxf.layer, "dxf_type": etype}
                )

    return gpd.GeoDataFrame(rows)


# 4. The Main Entry Point
def extract_to_geopackage(
    file_path: str,
    output_dir: str = "output",
    output_name: str = "utilities.gpkg",
    crs: str = "EPSG:26910",
) -> Optional[pathlib.Path]:

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
        logger.info(f"Successfully exported to {out_path}")

        return out_path

    except Exception as e:
        logger.error(f"Critical failure: {e}")
        return None


# Simple usage
if __name__ == "__main__":
    extract_to_geopackage("../data/sample.dxf", "../data/gis_data")
