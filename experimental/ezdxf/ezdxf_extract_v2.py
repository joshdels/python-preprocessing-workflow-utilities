import ezdxf
import json
import pathlib

# Only downside of this code is that its too lag since geojson are too lag to have hehe
# So Ill use this for the case study. Did not put a try catch block for handling errors


def extract_to_gis_features(file_path: str, output_name: str = "output.geojson"):
    '''Extract's all the layer lines and nodes except the polygons
      This includes the LINES, POINTS, CIRCLE
    '''
    input_path = pathlib.Path(file_path)
    output_dir = input_path.parent / "output"
    output_dir.mkdir(exist_ok=True)

    final_output_path = output_dir / output_name

    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()
    features = []

    for entity in msp:
        layer_name = entity.dxf.layer
        etype = entity.dxftype()

        if etype in ("INSERT", "POINT"):
            coords = entity.dxf.insert if etype == "INSERT" else entity.dxf.location
            geometry = {"type": "Point", "coordinates": [coords.x, coords.y]}

        elif etype == "LINE":
            geometry = {
                "type": "LineString",
                "coordinates": [
                    (entity.dxf.start.x, entity.dxf.start.y),
                    (entity.dxf.end.x, entity.dxf.end.y),
                ],
            }

        elif etype == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points()]
            geometry = {"type": "LineString", "coordinates": points}
        else:
            continue

        feature = {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "layer": layer_name,
                "dxf_type": etype,
                "project": "TopMap_Sync",
            },
        }
        features.append(feature)

    gis_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:26910"}},
        "features": features,
    }

    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(gis_data, f, indent=4)

    print(f"Extraction successful!")
    print(f"Saved {len(features)} features to: {final_output_path}")

    return final_output_path


# Execution
extract_to_gis_features("../data/sample.dxf", "utility_infrastructure.geojson")
