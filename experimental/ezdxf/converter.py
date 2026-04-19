import ezdxf

doc = ezdxf.readfile("../data/sample.dxf")
msp = doc.modelspace()


# Collect Unique Layers
layers = {e.dxf.layer for e in msp}
print("Unique layers:", layers)


# Collect unique block names
blocks = {e.dxf.name for e in msp.query("INSERT")}
print("Unique blocks:", blocks)

# -----------------------------
# Guess coordinates UTM?
def guess_crs_from_coords(x, y):
    if 100000 <= x <= 900000 and 0 <= y <= 10000000:
        return "EPSG:32651"  # likely UTM zone 51N
    elif -180 <= x <= 180 and -90 <= y <= 90:
        return "EPSG:4326"   # WGS84 lat/lon
    else:
        return None  # unknown

# Query actual LINE entities (uppercase!)
circle = [(e.dxf.start, e.dxf.end) for e in msp.query("circle")]

if circle:  # check if there are any lines
    first_point = circle[0][0]
    crs_guess = guess_crs_from_coords(first_point.x, first_point.y)
    print("Guessed CRS:", crs_guess)
else:
    print("No LINE entities found in the DXF")