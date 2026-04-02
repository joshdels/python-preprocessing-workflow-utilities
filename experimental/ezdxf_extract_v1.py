import ezdxf

doc = ezdxf.readfile("../data/sample.dxf")
msp = doc.modelspace()

# Dictionary: entity_type -> set of unique layer names
entity_layers = {}

for e in msp:
    etype = e.dxftype().upper()  # e.g., LINE, CIRCLE, INSERT
    layer = e.dxf.layer

    if etype not in entity_layers:
        entity_layers[etype] = set()

    entity_layers[etype].add(layer)


def extract_layers(entity_types=None, layer_names=None) -> list:
    """
    Extracts a list of layer names based on entity types or specific layer names.

    :param entity_types: list of entity type strings (e.g., ['LINE', 'LWPOLYLINE'])
    :param layer_names: list of layer names to filter (e.g., ['Water Control Valves'])
    :return: list of matching layer names
    """
    result = set()

    # Filter by entity types
    if entity_types:
        for etype in entity_types:
            etype_upper = etype.upper()
            if etype_upper in entity_layers:
                result.update(entity_layers[etype_upper])

    # Filter by specific layer names
    if layer_names:
        for lname in layer_names:
            for layers in entity_layers.values():
                if lname in layers:
                    result.add(lname)

    return sorted(result)


# Example usage:
polyline_layers = extract_layers(entity_types=["POLYLINE", "LWPOLYLINE"])
print("Polyline layers:", polyline_layers)

water_valve_layers = extract_layers(layer_names=["Water Control Valves"])
print("Water valve layers:", water_valve_layers)
