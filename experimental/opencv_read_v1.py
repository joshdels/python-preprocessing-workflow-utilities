# sample workflow from claude

import fitz
import cv2
import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union, polygonize


# 1 convert pdf to image
doc = fitz.open("../data/sample.pdf")
pix = doc[0].get_pixmap(matrix=fitz.Matrix(3, 3))
pix.save("map.png")

# 2 isolate colors using opencv
img = cv2.imread("map.png")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
mask = cv2.inRange(hsv, np.array([90, 30, 30]), np.array([140, 255, 255]))
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# 
lines = [LineString(c.reshape(-1, 2).tolist()) for c in contours if len(c) > 2]
polygons = list(polygonize(unary_union(lines)))

gdf = gpd.GeoDataFrame(geometry=polygons)
gdf.to_file("parcels.geojson", driver="GeoJSON")
print(f"Done! {len(polygons)} parcels found")