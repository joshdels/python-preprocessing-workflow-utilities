import pathlib
import ezdxf
from ezdxf.units import unit_name


def inspect_dxf(file_path: str) -> str:
    """
    Returns entity layers and coordinate system info.
    """

    print("Inspecting running please wait...")
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

    # Analysis
    msp = doc.modelspace()
    geodata = msp.get_geodata()
    units = doc.units

    entity_layers = {}
    print(f"\n --- LAYER INFO ---")
    for e in msp:
        etype = e.dxftype().upper()
        layer = e.dxf.layer

        if etype not in entity_layers:
            entity_layers[etype] = set()

        entity_layers[etype].add(layer)

    for etype in sorted(entity_layers.keys()):
        layers = entity_layers[etype]
        print(f"{etype} ({len(layers)})")
        for l in sorted(layers):
            print(f"  {l}")
        print(f"Total unique names: {len(layers)}\n")

    # Inspect CRS
    if geodata:
        try:
            epsg, is_cartesian_order = geodata.get_crs()
            print(f"--- GEOSPATIAL INFO ---")
            print(f"EPSG Code: {epsg}")
            print(f"Standard Axis Order: {is_cartesian_order}")
        except Exception as e:
            print(f"Could not parse CRS XML: {e}")
            print("Possible No GeoData (CRS) found in this file.")

    # check units
    if units:
        unit = unit_name(units)
        print(f"\n --- MEASUREMENT INFO ---")
        print(f"Measurement used: {unit} | {units}")


inspect_dxf("../data/sample.dxf")
