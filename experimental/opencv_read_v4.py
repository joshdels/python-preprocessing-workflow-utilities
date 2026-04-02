import fitz
import cv2
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union, polygonize
import geopandas as gpd
import os

# Create debug folder to see where it fails
os.makedirs("debug", exist_ok=True)

# ============================================================
# CONFIGURATION
# ============================================================
PDF_PATH     = "../data/sample.pdf"
OUTPUT       = "parcels_fixed.geojson"
ZOOM         = 4                         # Higher zoom = more detail but slower
MIN_AREA     = 1000                      # Adjust based on parcel size in pixels

# ROI - Focus on the map area, ignore title blocks
ROI_LEFT, ROI_RIGHT = 0.05, 0.95
ROI_TOP, ROI_BOTTOM = 0.05, 0.85

# HSV Blue Filter - adjusted for typical scanned "Blue" ink
LOWER_BLUE   = np.array([80, 20, 20])    
UPPER_BLUE   = np.array([140, 255, 255])
MORPH_KERNEL = np.ones((3, 3), np.uint8)

# ============================================================
# STEP 1: PDF TO IMAGE
# ============================================================
print("🔄 Rendering PDF...")
doc = fitz.open(PDF_PATH)
page = doc[0]
pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
img_path = "debug/00_full_render.png"
pix.save(img_path)
img = cv2.imread(img_path)

# ============================================================
# STEP 2: CROP & COLOR FILTER
# ============================================================
h, w = img.shape[:2]
roi = img[int(h*ROI_TOP):int(h*ROI_BOTTOM), int(w*ROI_LEFT):int(w*ROI_RIGHT)]

hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
mask = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)
cv2.imwrite("debug/01_mask.png", mask)

# ============================================================
# STEP 3: SKELETONIZATION (Thinning for CAD accuracy)
# ============================================================
print("🔄 Thinning lines...")
# Close small gaps first
closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
# Skeletonize reduces lines to 1-pixel width
skeleton = cv2.ximgproc.thinning(closed)
cv2.imwrite("debug/02_skeleton.png", skeleton)

# ============================================================
# STEP 4: FIND CONTOURS (RETR_TREE is vital for inner parcels)
# ============================================================
print("🔄 Extracting geometry...")
# RETR_TREE gets the hierarchy (parcels inside the main frame)
contours, hierarchy = cv2.findContours(skeleton, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

# ============================================================
# STEP 5: POLYGONIZATION & CLEANUP
# ============================================================
polygons = []
for i, cnt in enumerate(contours):
    # Only process "inner" contours (level 1 or deeper in hierarchy) 
    # to avoid the big outer frame if possible
    area = cv2.contourArea(cnt)
    if area > MIN_AREA:
        # Simplify the shape (Douglas-Peucker) to make it CAD-friendly
        epsilon = 0.001 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        
        # Convert to Shapely Polygon
        if len(approx) >= 3:
            poly = Polygon(approx.reshape(-1, 2))
            if poly.is_valid:
                polygons.append(poly)

print(f"✅ Found {len(polygons)} potential parcels.")

# ============================================================
# STEP 6: FALLBACK (If polygons list is empty)
# ============================================================
if not polygons:
    print("⚠️ No closed polygons found. Attempting Line-to-Polygon conversion...")
    lines = [LineString(c.reshape(-1, 2)) for c in contours if len(c) > 1]
    merged = unary_union(lines)
    polygons = list(polygonize(merged))
    print(f"✅ Fallback created {len(polygons)} polygons.")

# ============================================================
# STEP 7: SAVE DATA
# ============================================================
if polygons:
    # Save a visual check
    debug_final = roi.copy()
    for i, p in enumerate(polygons):
        pts = np.array(p.exterior.coords, np.int32)
        cv2.polylines(debug_final, [pts], True, (0, 0, 255), 2)
        cv2.putText(debug_final, str(i), tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)
    cv2.imwrite("debug/03_final_check.png", debug_final)

    # Save to GeoJSON (Pixels)
    gdf = gpd.GeoDataFrame(geometry=polygons)
    gdf.to_file(OUTPUT, driver="GeoJSON")
    print(f"🚀 SUCCESS: Saved to {OUTPUT}")
else:
    print("❌ Critical Failure: No polygons detected. Check debug/01_mask.png")