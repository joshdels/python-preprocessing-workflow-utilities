import fitz
import cv2
import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union, polygonize
import geopandas as gpd
import os

os.makedirs("debug", exist_ok=True)

# ============================================================
# CONFIG - tweak these if results are wrong
# ============================================================
PDF_PATH     = "../data/sample.pdf"
OUTPUT       = "parcels_v22.geojson"
ZOOM         = 5                        # PDF render resolution
MIN_AREA     = 5000                     # minimum contour area to keep (filter noise)
ROI_LEFT     = 0.10                     # crop left  (0.0 - 1.0)
ROI_RIGHT    = 0.75                     # crop right (0.0 - 1.0)
ROI_TOP      = 0.05                     # crop top   (0.0 - 1.0)
ROI_BOTTOM   = 0.95                     # crop bottom(0.0 - 1.0)
LOWER_BLUE   = np.array([90, 20, 20])   # HSV lower bound for blue lines
UPPER_BLUE   = np.array([130, 180, 180])# HSV upper bound for blue lines
MORPH_KERNEL = np.ones((3, 3), np.uint8)
# ============================================================

# STEP 1 - PDF to image
print("🔄 Step 1 - converting PDF to image...")
doc = fitz.open(PDF_PATH)
pix = doc[0].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
pix.save("map.png")
print("✅ Step 1 done - PDF converted to map.png")

# STEP 2 - Load image
print("🔄 Step 2 - loading image...")
img = cv2.imread("map.png")
cv2.imwrite("debug/01_original.png", img)
print(f"✅ Step 2 done - image loaded {img.shape}")

# STEP 3 - Crop to ROI (remove noisy edges + title box)
print("🔄 Step 3 - cropping to map area...")
h, w = img.shape[:2]
x1 = int(w * ROI_LEFT)
x2 = int(w * ROI_RIGHT)
y1 = int(h * ROI_TOP)
y2 = int(h * ROI_BOTTOM)
roi = img[y1:y2, x1:x2]
cv2.imwrite("debug/02_roi.png", roi)
print(f"✅ Step 3 done - cropped to region [{x1}:{x2}, {y1}:{y2}]")

# STEP 4 - Blue color filter (isolate parcel lines only)
print("🔄 Step 4 - isolating blue lines...")
hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
mask = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)
cv2.imwrite("debug/03_blue_mask.png", mask)
print("✅ Step 4 done - blue mask created")
print("   👉 CHECK debug/03_blue_mask.png - lines should be WHITE, background BLACK")

# STEP 5 - Remove noise (small dots/speckles)
print("🔄 Step 5 - removing noise...")
clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, MORPH_KERNEL)
cv2.imwrite("debug/04_denoise.png", clean)
print("✅ Step 5 done - noise removed")

# STEP 6 - Close gaps in lines
print("🔄 Step 6 - closing line gaps...")
clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, MORPH_KERNEL)
cv2.imwrite("debug/05_closed.png", clean)
print("✅ Step 6 done - gaps closed")
print("   👉 CHECK debug/05_closed.png - lines should be solid and connected")

# STEP 7 - Dilate slightly to connect near-broken lines
print("🔄 Step 7 - dilating lines...")
clean = cv2.dilate(clean, MORPH_KERNEL, iterations=1)
cv2.imwrite("debug/06_dilated.png", clean)
print("✅ Step 7 done - lines dilated")

# STEP 8 - Find all contours
print("🔄 Step 8 - finding contours...")
contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"✅ Step 8 done - found {len(contours)} raw contours")

# STEP 9 - Draw ALL contours (before filter)
debug_all = roi.copy()
cv2.drawContours(debug_all, contours, -1, (0, 255, 0), 2)
cv2.imwrite("debug/07_all_contours.png", debug_all)
print("✅ Step 9 done - all contours drawn (green)")
print("   👉 CHECK debug/07_all_contours.png - see everything detected")

# STEP 10 - Filter small noise contours by area
print(f"🔄 Step 10 - filtering contours smaller than {MIN_AREA}px area...")
contours_filtered = [c for c in contours if cv2.contourArea(c) > MIN_AREA]
removed = len(contours) - len(contours_filtered)
print(f"✅ Step 10 done - {len(contours_filtered)} contours kept, {removed} removed")

# STEP 11 - Draw filtered contours
debug_filtered = roi.copy()
cv2.drawContours(debug_filtered, contours_filtered, -1, (255, 0, 0), 2)
cv2.imwrite("debug/08_filtered_contours.png", debug_filtered)
print("✅ Step 11 done - filtered contours drawn (blue)")
print("   👉 CHECK debug/08_filtered_contours.png - only real parcels should remain")

# STEP 12 - Convert contours to Shapely LineStrings
print("🔄 Step 12 - converting to Shapely lines...")
lines = [LineString(c.reshape(-1, 2).tolist()) for c in contours_filtered if len(c) > 2]
print(f"✅ Step 12 done - {len(lines)} lines created")

# STEP 13 - Polygonize
print("🔄 Step 13 - polygonizing...")
polygons = list(polygonize(unary_union(lines)))
print(f"✅ Step 13 done - {len(polygons)} polygons created")
if len(polygons) == 0:
    print("   ⚠️  0 polygons! Lines may not be closed.")
    print("   👉 Try increasing MORPH_KERNEL size or check debug/05_closed.png")

# STEP 14 - Draw final polygons on original ROI
print("🔄 Step 14 - drawing final polygons...")
debug_poly = roi.copy()
for i, poly in enumerate(polygons):
    coords = np.array(poly.exterior.coords, dtype=np.int32)
    cv2.polylines(debug_poly, [coords], isClosed=True, color=(0, 0, 255), thickness=3)
    # label each polygon with its index
    cx = int(poly.centroid.x)
    cy = int(poly.centroid.y)
    cv2.putText(debug_poly, str(i+1), (cx, cy),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
cv2.imwrite("debug/09_final_polygons.png", debug_poly)
print("✅ Step 14 done - final polygons drawn (red)")
print("   👉 CHECK debug/09_final_polygons.png - final result!")

# STEP 15 - Save GeoJSON
print("🔄 Step 15 - saving GeoJSON...")
gdf = gpd.GeoDataFrame(geometry=polygons, crs=None)  # pixel coords, no georef yet
try:
    gdf.to_file(OUTPUT, driver="GeoJSON")
    print(f"✅ DONE! {len(polygons)} parcels saved to {OUTPUT}")
except PermissionError:
    print(f"❌ Cannot save - '{OUTPUT}' is open in QGIS or another program. Close it first!")
