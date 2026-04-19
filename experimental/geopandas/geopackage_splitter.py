import geopandas as gpd
import os

# 1  read files
input_file = r"C:\Users\deleo\Downloads\test\sampling.gpkg"
output_file = r"C:\Users\deleo\Downloads\test\output.gpkg"


def geopackage_splitter(input_file: str, output_file: str, column: str = "layer"):
    """Process splitting the geopackage into mutiple parts according to layer"""

    try:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")

        layers_df = gpd.list_layers(input_file)

        for lyr in layers_df["name"]:
            gdf = gpd.read_file(input_file, layer=lyr)

            if "layer" not in gdf.columns:
                gdf.to_file(output_file, layer=lyr, driver="GPKG")
                continue

            for layer_name in gdf[column].dropna().unique():
                subset = gdf[gdf[column] == layer_name]

                # geom type (optional)
                for geom in subset.geom_type.unique():
                    sub = subset[subset.geom_type == geom]

                    safe_name = f"{layer_name}"

                    sub.to_file(output_file, layer=safe_name, driver="GPKG")
                    
        print("GeoPackage split completed successfully.")

    except Exception as e:
        print(f"Error while splitting Geopackage: {e}")


geopackage_splitter(input_file, output_file)
