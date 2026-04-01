import ezdxf


def inspect_dxf(file_path: str) -> str:
    """This function e"""
    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    entity_layers = {}

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


inspect_dxf("../data/sample.dxf")


# -------------
