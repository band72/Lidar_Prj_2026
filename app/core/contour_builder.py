"""
High-Precision Vector Contour Generator
Generates large scale contours from DEM rasters into GeoJSON, ESRI Shapefiles (zipped),
AutoCAD DXF, and GeoPackage formats with customizable contour intervals and index contours.
"""

import os
import json
import zipfile
import subprocess
import shutil
from typing import Dict, Any, List, Optional, Tuple, Callable
from osgeo import gdal, ogr, osr
import pyproj
from pyproj import Transformer
from shapely.geometry import shape, mapping, MultiLineString, LineString


def generate_contours(
    dem_raster_path: str,
    output_base_dir: str,
    contour_interval: float = 2.0,
    index_multiplier: int = 5,
    base_elevation: float = 0.0,
    smooth_tolerance: float = 0.0,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Generates multi-format vector contours (GeoJSON, Shapefile, DXF, GeoPackage)
    from a DEM raster.
    """
    os.makedirs(output_base_dir, exist_ok=True)
    
    if progress_callback:
        progress_callback(88.0, f"Generating {contour_interval}-unit contours from DEM...")

    dem_ds = gdal.Open(dem_raster_path)
    if not dem_ds:
        raise FileNotFoundError(f"Cannot open DEM raster: {dem_raster_path}")

    srs_wkt = dem_ds.GetProjection()
    dem_ds = None # Close dataset

    # Temporary raw contours GeoJSON
    raw_geojson = os.path.join(output_base_dir, "_raw_contours.geojson")
    if os.path.exists(raw_geojson):
        os.remove(raw_geojson)

    # Use native gdal_contour utility
    cmd = [
        "gdal_contour",
        "-a", "elevation",
        "-i", str(contour_interval),
        "-off", str(base_elevation),
        "-snodata", "-9999.0",
        "-f", "GeoJSON",
        dem_raster_path,
        raw_geojson
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(raw_geojson):
        raise RuntimeError(f"gdal_contour failed: {res.stderr}")

    with open(raw_geojson, "r") as f:
        raw_data = json.load(f)

    raw_features = raw_data.get("features", [])
    if not raw_features:
        raise RuntimeError("Contour generation resulted in 0 contours. Check elevation range and interval.")

    if progress_callback:
        progress_callback(91.0, f"Categorizing {len(raw_features):,} contour lines (Index vs Intermediate)...")

    # Coordinate transformer to WGS84 for web map visualization
    wgs84_transformer = None
    try:
        if srs_wkt:
            pyproj_crs = pyproj.CRS.from_wkt(srs_wkt)
            wgs84_transformer = Transformer.from_crs(pyproj_crs, "EPSG:4326", always_xy=True)
    except Exception:
        pass

    native_features = []
    wgs84_features = []
    total_length_native = 0.0
    index_count = 0
    intermediate_count = 0
    elevations = []

    index_interval = contour_interval * index_multiplier

    for feat in raw_features:
        props = feat.get("properties", {})
        elev = float(props.get("elevation", 0.0))
        elevations.append(elev)

        # Check if index contour
        is_index = abs(round(elev / index_interval) * index_interval - elev) < (contour_interval * 0.05)
        if is_index:
            index_count += 1
            ctype = "index"
        else:
            intermediate_count += 1
            ctype = "intermediate"

        geom_dict = feat.get("geometry", {})
        if not geom_dict:
            continue

        shapely_geom = shape(geom_dict)
        if smooth_tolerance > 0:
            shapely_geom = shapely_geom.simplify(smooth_tolerance, preserve_topology=True)

        total_length_native += shapely_geom.length

        out_props = {
            "elevation": round(elev, 2),
            "type": ctype,
            "is_index": is_index
        }

        # Native feature
        native_feature = {
            "type": "Feature",
            "geometry": mapping(shapely_geom),
            "properties": out_props
        }
        native_features.append(native_feature)

        # WGS84 feature for Leaflet
        if wgs84_transformer:
            try:
                if shapely_geom.geom_type == "LineString":
                    wgs84_coords = []
                    for x, y in shapely_geom.coords:
                        lon, lat = wgs84_transformer.transform(x, y)
                        wgs84_coords.append([round(lon, 7), round(lat, 7)])
                    wgs84_geom = {"type": "LineString", "coordinates": wgs84_coords}
                elif shapely_geom.geom_type == "MultiLineString":
                    wgs84_multi = []
                    for line in shapely_geom.geoms:
                        line_coords = []
                        for x, y in line.coords:
                            lon, lat = wgs84_transformer.transform(x, y)
                            line_coords.append([round(lon, 7), round(lat, 7)])
                        wgs84_multi.append(line_coords)
                    wgs84_geom = {"type": "MultiLineString", "coordinates": wgs84_multi}
                else:
                    wgs84_geom = mapping(shapely_geom)

                wgs84_features.append({
                    "type": "Feature",
                    "geometry": wgs84_geom,
                    "properties": out_props
                })
            except Exception:
                pass

    if progress_callback:
        progress_callback(94.0, "Writing GeoJSON and ESRI Shapefile vector formats...")

    # 1. Native GeoJSON
    geojson_path = os.path.join(output_base_dir, "contours.geojson")
    native_fc = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": srs_wkt if srs_wkt else "EPSG:4326"}
        },
        "features": native_features
    }
    with open(geojson_path, "w") as f:
        json.dump(native_fc, f)

    # 2. WGS84 GeoJSON for Web Preview
    wgs84_geojson_path = os.path.join(output_base_dir, "contours_wgs84.geojson")
    wgs84_fc = {
        "type": "FeatureCollection",
        "features": wgs84_features if wgs84_features else native_features
    }
    with open(wgs84_geojson_path, "w") as f:
        json.dump(wgs84_fc, f)

    # Clean up temporary raw GeoJSON
    if os.path.exists(raw_geojson):
        os.remove(raw_geojson)

    # 3. ESRI Shapefile (.shp + .shx + .dbf + .prj)
    shp_dir = os.path.join(output_base_dir, "shapefile")
    os.makedirs(shp_dir, exist_ok=True)
    shp_path = os.path.join(shp_dir, "contours.shp")
    
    # Use ogr2ogr or OGR API to write shapefile from native GeoJSON
    cmd_shp = [
        "ogr2ogr",
        "-f", "ESRI Shapefile",
        shp_path,
        geojson_path,
        "-overwrite"
    ]
    subprocess.run(cmd_shp, capture_output=True, text=True)

    # Zip Shapefile components
    zip_shp_path = os.path.join(output_base_dir, "contours_shapefile.zip")
    with zipfile.ZipFile(zip_shp_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(shp_dir):
            for file in files:
                full_p = os.path.join(root, file)
                z.write(full_p, os.path.basename(full_p))

    # 4. AutoCAD DXF Generation
    if progress_callback:
        progress_callback(96.0, "Exporting AutoCAD DXF 3D contour polylines...")
    dxf_path = os.path.join(output_base_dir, "contours.dxf")
    _export_contours_to_dxf(native_features, dxf_path)

    min_elev = min(elevations) if elevations else 0.0
    max_elev = max(elevations) if elevations else 0.0

    return {
        "geojson_path": geojson_path,
        "wgs84_geojson_path": wgs84_geojson_path,
        "shapefile_zip_path": zip_shp_path,
        "dxf_path": dxf_path,
        "total_contours": len(native_features),
        "index_contours": index_count,
        "intermediate_contours": intermediate_count,
        "contour_interval": contour_interval,
        "index_interval": index_interval,
        "total_length_native": round(total_length_native, 2),
        "min_elevation": round(min_elev, 2),
        "max_elevation": round(max_elev, 2)
    }


def _export_contours_to_dxf(features: List[Dict[str, Any]], dxf_path: str):
    """
    Generates standard AutoCAD R12 DXF format with 3D elevation contours
    separated into CONTOUR_INDEX and CONTOUR_INTERMEDIATE layers.
    """
    lines = []
    
    # DXF Header
    lines.extend([
        "0", "SECTION",
        "2", "HEADER",
        "9", "$ACADVER",
        "1", "AC1009",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "TABLES",
        "0", "TABLE",
        "2", "LAYER",
        "70", "2",
        "0", "LAYER",
        "2", "CONTOUR_INDEX",
        "70", "0",
        "62", "1", # Red/Index color
        "6", "CONTINUOUS",
        "0", "LAYER",
        "2", "CONTOUR_INTERMEDIATE",
        "70", "0",
        "62", "3", # Green/Intermediate color
        "6", "CONTINUOUS",
        "0", "ENDTAB",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "ENTITIES"
    ])

    for feat in features:
        elev = feat["properties"]["elevation"]
        is_index = feat["properties"]["is_index"]
        layer_name = "CONTOUR_INDEX" if is_index else "CONTOUR_INTERMEDIATE"
        geom = feat["geometry"]
        gtype = geom["type"]
        coords_list = []
        
        if gtype == "LineString":
            coords_list = [geom["coordinates"]]
        elif gtype == "MultiLineString":
            coords_list = geom["coordinates"]

        for coords in coords_list:
            if len(coords) < 2:
                continue
            
            # Write POLYLINE
            lines.extend([
                "0", "POLYLINE",
                "8", layer_name,
                "66", "1",
                "70", "8", # 3D Polyline flag
            ])

            for pt in coords:
                x, y = pt[0], pt[1]
                z = elev if len(pt) < 3 else pt[2]
                lines.extend([
                    "0", "VERTEX",
                    "8", layer_name,
                    "10", f"{x:.4f}",
                    "20", f"{y:.4f}",
                    "30", f"{z:.4f}",
                    "70", "32" # 3D Vertex flag
                ])

            lines.extend(["0", "SEQEND"])

    lines.extend([
        "0", "ENDSEC",
        "0", "EOF"
    ])

    with open(dxf_path, "w") as f:
        f.write("\n".join(lines) + "\n")
