import ezdxf
import geopandas as gpd
import pathlib
from shapely.geometry import Point, LineString


def extract_to_geopackage(
    file_path: str,
    output_dir: str = "output",
    output_name: str = "utilities.gpkg",
    crs="EPSG:26910",
):
    """
    Returns as Geopackage of a file
    1. a linestring
    2. a node (points)
    """

    print("-- PROCESSING EXTRACTION -- \n Inspecting file status \n")
    path = pathlib.Path(file_path)

    if not path.exists():
        print(
            f"Error: File not found at '{file_path}' \n please check you file name/path "
        )
        return None

    if not path.is_file() or path.suffix.lower() != ".dxf":
        print(f"Error: {file_path} is not a valid DXF file")
        return None

    try:
        doc = ezdxf.readfile(file_path)
    except IOError:
        print(f"ERROR: Permission denied. Is the file open in another program?")
        return None
    except ezdxf.DXFStructureError:
        print(f"ERROR: {file_path} is a corrupted or invalid DXF structure.")
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        return None

    print(
        f"File exist at '{file_path}' and with proper format! \nStarting to Processing please wait for a while \n"
    )

    final_output_dir = pathlib.Path(output_dir)
    final_output_dir.mkdir(parents=True, exist_ok=True)
    final_output_path = final_output_dir / output_name

    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    data_rows = []

    # Entities Layers
    for entity in msp:
        layer = entity.dxf.layer
        etype = entity.dxftype()
        geometry = None

        if etype in ("INSERT", "POINT"):
            coords = entity.dxf.insert if etype == "INSERT" else entity.dxf.location
            geometry = Point(coords.x, coords.y)

        elif etype == "LINE":
            geometry = LineString(
                [
                    (entity.dxf.start.x, entity.dxf.start.y),
                    (entity.dxf.end.x, entity.dxf.end.y),
                ]
            )

        elif etype == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points()]
            if len(points) > 1:
                geometry = LineString(points)

        if geometry:
            data_rows.append(
                {
                    "geometry": geometry,
                    "layer": layer,
                    "dxf_type": etype,
                }
            )

    if not data_rows:
        print("No valid geometry found.")
        return None

    # GeoPandas
    gdf = gpd.GeoDataFrame(data_rows, crs=crs)
    gdf.to_file(final_output_path, layer="dx_entities", driver="GPKG")

    print(f"Success! GeoPackage created at: {final_output_path}")

    return final_output_path


extract_to_geopackage(
    "../data/sample.dxf", "../data/gis_data", "city_infrastructure.gpkg"
)
