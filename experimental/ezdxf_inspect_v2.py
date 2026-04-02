import pathlib
import ezdxf
from ezdxf.units import unit_name
from datetime import datetime


def get_dxf_metadata(doc, msp) -> dict:
    """Extracts raw info. No printing, no saving. Just data."""
    geodata = msp.get_geodata()
    epsg = "N/A"
    if geodata:
        try:
            code, _ = geodata.get_crs()
            epsg = f"EPSG:{code}"
        except:
            epsg = "Unknown CRS"

    layers_by_type = {}
    for e in msp:
        etype = e.dxftype().upper()
        layers_by_type.setdefault(etype, set()).add(e.dxf.layer)

    return {
        "units": unit_name(doc.units),
        "epsg": epsg,
        "layers": layers_by_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def format_text_report(filename: str, data: dict) -> str:
    """Turns the data dictionary into a pretty string."""
    report = [
        "=" * 50,
        f"  INFRALENS(TopMap Solutions) REPORT: {filename}  ",
        "=" * 50,
        f"Generated: {data['timestamp']}",
        f"Units    : {data['units']}",
        f"Project  : {data['epsg']}",
        "-" * 50,
    ]

    for etype, layers in sorted(data["layers"].items()):
        report.append(f"\n{etype} ({len(layers)} Layers)")
        report.extend([f"  - {l}" for l in sorted(layers)])

    return "\n".join(report)


def run_inspection(file_path: str, output_dir: str = "reports"):
    """
    Inspect the DXF file if its valid and its CRS
    Return A report both via print and a text file
    """
    path = pathlib.Path(file_path).resolve()

    if not path.exists():
        return print(f"File missing: {path}")

    try:
        doc = ezdxf.readfile(path)
        raw_data = get_dxf_metadata(doc, doc.modelspace())
        report_text = format_text_report(path.name, raw_data)

        out_folder = pathlib.Path(output_dir)
        out_folder.mkdir(exist_ok=True)
        report_file = out_folder / f"{path.stem}_report.txt"

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_text)

        print(f"Success! Manifest saved to: {report_file}")

    except Exception as e:
        print(f"Failed to process {path.name}: {e}")


# One Line Run
run_inspection("../data/sample.dxf")
