import fitz
import cv2
import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union, polygonize
import geopandas as gpd
import os

os.makedirs("debug", exist_ok=True)

# STEP 1 - PDF to image
doc = fitz.open("../data/sample.pdf")
pix = doc[0].get_pixmap(matrix=fitz.Matrix(5, 5))
pix.save("map.png")
print("✅ Step 1 done - PDF converted to map.png")

# STEP 2 - Load and preprocess
img = cv2.imread("map.png")
cv2.imwrite("debug/01_original.png", img)
print(f"✅ Step 2 done - image loaded {img.shape}")

# STEP 3 - Grayscale
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
cv2.imwrite("debug/02_gray.png", gray)
print("✅ Step 3 done - converted to grayscale")

# STEP 4 - Contrast
gray = cv2.equalizeHist(gray)
cv2.imwrite("debug/03_contrast.png", gray)
print("✅ Step 4 done - contrast enhanced")

# STEP 5 - Threshold
_, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
cv2.imwrite("debug/04_threshold.png", binary)
print("✅ Step 5 done - threshold applied")

# STEP 6 - Remove noise
kernel = np.ones((2, 2), np.uint8)
clean = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
cv2.imwrite("debug/05_denoise.png", clean)
print("✅ Step 6 done - noise removed")

# STEP 7 - Close gaps
clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel)
cv2.imwrite("debug/06_closed.png", clean)
print("✅ Step 7 done - gaps closed")

# STEP 8 - Find contours
contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"✅ Step 8 done - found {len(contours)} raw contours")

# STEP 9 - Draw ALL contours
debug_all = img.copy()
cv2.drawContours(debug_all, contours, -1, (0, 255, 0), 2)
cv2.imwrite("debug/07_all_contours.png", debug_all)
print("✅ Step 9 done - all contours drawn")

# STEP 10 - Filter small contours
contours_filtered = [c for c in contours if cv2.contourArea(c) > 100]
print(f"✅ Step 10 done - {len(contours_filtered)} contours after filter (removed {len(contours) - len(contours_filtered)} small ones)")

# STEP 11 - Draw filtered contours
debug_filtered = img.copy()
cv2.drawContours(debug_filtered, contours_filtered, -1, (255, 0, 0), 2)
cv2.imwrite("debug/08_filtered_contours.png", debug_filtered)
print("✅ Step 11 done - filtered contours drawn")

# STEP 12 - Convert to Shapely lines
lines = [LineString(c.reshape(-1, 2).tolist()) for c in contours_filtered if len(c) > 2]
print(f"✅ Step 12 done - {len(lines)} lines created")

# STEP 13 - Polygonize
polygons = list(polygonize(unary_union(lines)))
print(f"✅ Step 13 done - {len(polygons)} polygons created")

# STEP 14 - Draw final polygons
debug_poly = img.copy()
for poly in polygons:
    coords = np.array(poly.exterior.coords, dtype=np.int32)
    cv2.polylines(debug_poly, [coords], isClosed=True, color=(0, 0, 255), thickness=3)
cv2.imwrite("debug/09_final_polygons.png", debug_poly)
print("✅ Step 14 done - final polygons drawn")

# # STEP 15 - Save GeoJSON
# output = "parcels_v2.geojson"

# gdf = gpd.GeoDataFrame(geometry=polygons, crs=None)  # pixel coords for now

# try:
#     gdf.to_file(output, driver="GeoJSON")
#     print(f"✅ DONE! {len(polygons)} parcels saved to {output}")
# except PermissionError:
#     print("❌ File is open in another program (QGIS?). Close it first or rename output.")