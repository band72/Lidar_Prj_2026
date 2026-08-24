"""
High-Performance Native LiDAR Processing Engine
Provides streaming chunked processing of LAS/LAZ files, spatial bounding box clipping,
elevation cutoff, classification filtering, outlier removal, and DEM GeoTIFF generation using GDAL and NumPy/SciPy.
"""

import os
import math
import time
from typing import Dict, Any, List, Optional, Tuple, Callable
import numpy as np
from scipy import ndimage
import laspy
from osgeo import gdal, osr

from app.core.crs_utils import (
    parse_crs_from_header,
    detect_linear_units,
    get_wgs84_bounds,
    transform_latlon_bbox_to_native,
    convert_units
)

# Standard ASPRS LAS Classification Codes
ASPRS_CLASSIFICATIONS = {
    0: "Created, never classified",
    1: "Unclassified",
    2: "Ground",
    3: "Low Vegetation",
    4: "Medium Vegetation",
    5: "High Vegetation",
    6: "Building",
    7: "Low Point (Noise)",
    8: "Model Key-point",
    9: "Water",
    10: "Rail",
    11: "Road Surface",
    12: "Overlap / Reserved",
    13: "Wire - Guard",
    14: "Wire - Conductor",
    15: "Transmission Tower",
    16: "Wire-structure Connector",
    17: "Bridge Deck",
    18: "High Noise",
}


def inspect_lidar_file(file_path: str, sample_size: int = 100000) -> Dict[str, Any]:
    """
    Inspects a LAS/LAZ point cloud file and returns comprehensive metadata,
    CRS, true physical WGS84 GPS bounds, and classification distribution.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"LiDAR file not found: {file_path}")

    # If user selected a directory, attempt to find LAS/LAZ files inside
    if os.path.isdir(file_path):
        candidates = [
            os.path.join(file_path, f)
            for f in os.listdir(file_path)
            if f.lower().endswith((".las", ".laz"))
        ]
        if candidates:
            # Sort by size descending to pick primary point cloud
            candidates.sort(key=lambda p: os.path.getsize(p), reverse=True)
            file_path = candidates[0]
        else:
            raise ValueError(f"Selected path is a directory with no .las or .laz point cloud files: {file_path}")

    with laspy.open(file_path) as reader:
        header = reader.header
        total_points = header.point_count
        
        # Bounding box in native coordinates
        min_x = header.x_min
        max_x = header.x_max
        min_y = header.y_min
        max_y = header.y_max
        min_z = header.z_min
        max_z = header.z_max
        
        # CRS parsing
        crs_obj, crs_name, crs_repr = parse_crs_from_header(header)
        units = detect_linear_units(crs_obj)
        
        # WGS84 bounds
        wgs84_bounds = get_wgs84_bounds(min_x, min_y, max_x, max_y, crs_obj)
        
        # Sample points to inspect classifications and elevation distribution
        points_to_read = min(total_points, sample_size)
        sample_chunk = reader.read_points(points_to_read)
        
        classes = {}
        sample_z = sample_chunk.z
        
        if hasattr(sample_chunk, "classification"):
            unique_cls, counts = np.unique(sample_chunk.classification, return_counts=True)
            for cls_code, cnt in zip(unique_cls, counts):
                cls_int = int(cls_code)
                cls_name = ASPRS_CLASSIFICATIONS.get(cls_int, f"Class {cls_int}")
                classes[cls_int] = {
                    "name": cls_name,
                    "sample_count": int(cnt),
                    "percentage": round(float(cnt) / len(sample_chunk) * 100, 2)
                }

        z_stats = {
            "min": float(np.min(sample_z)),
            "max": float(np.max(sample_z)),
            "mean": float(np.mean(sample_z)),
            "p5": float(np.percentile(sample_z, 5)),
            "p50": float(np.percentile(sample_z, 50)),
            "p95": float(np.percentile(sample_z, 95)),
        }

        # Estimate area and point density
        width_native = max_x - min_x
        height_native = max_y - min_y
        area_native = max(width_native * height_native, 1.0)
        
        # Density calculations
        if units in ("ftUS", "ft"):
            density_native = total_points / area_native # pts / sq ft
            area_m2 = area_native * (0.3048 ** 2)
            density_m2 = total_points / max(area_m2, 1.0) # pts / m²
        else:
            density_m2 = total_points / area_native
            density_native = density_m2

        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

        return {
            "file_path": file_path,
            "filename": os.path.basename(file_path),
            "file_size_mb": file_size_mb,
            "total_points": total_points,
            "version": f"{header.version.major}.{header.version.minor}",
            "point_format": header.point_format.id,
            "units": units,
            "crs_name": crs_name,
            "crs_repr": crs_repr,
            "native_bounds": {
                "min_x": round(min_x, 3),
                "max_x": round(max_x, 3),
                "min_y": round(min_y, 3),
                "max_y": round(max_y, 3),
                "min_z": round(min_z, 3),
                "max_z": round(max_z, 3),
                "width": round(width_native, 3),
                "height": round(height_native, 3)
            },
            "wgs84_bounds": wgs84_bounds,
            "classes": classes,
            "z_stats": z_stats,
            "density_m2": round(density_m2, 2),
            "density_sqft": round(density_native if units in ("ftUS", "ft") else density_m2 * (0.3048 ** 2), 2)
        }


def process_point_cloud_to_dem(
    input_path: str,
    output_dem_path: str,
    bounding_box_latlon: Optional[Dict[str, float]] = None,
    bounding_box_native: Optional[Tuple[float, float, float, float]] = None,
    elevation_min: Optional[float] = None,
    elevation_max: Optional[float] = None,
    selected_classes: Optional[List[int]] = None,
    cell_size: float = 2.0,
    outlier_removal: bool = True,
    auto_ground_filter: bool = False,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Reads LAS/LAZ point cloud, clips to bounding area, applies elevation cutoffs
    and classification filters, interpolates ground elevation grid, and exports GeoTIFF DEM.
    """
    start_time = time.time()
    if os.path.isdir(input_path):
        candidates = [
            os.path.join(input_path, f)
            for f in os.listdir(input_path)
            if f.lower().endswith((".las", ".laz"))
        ]
        if candidates:
            candidates.sort(key=lambda p: os.path.getsize(p), reverse=True)
            input_path = candidates[0]
        else:
            raise ValueError(f"Directory contains no .las or .laz files: {input_path}")

    if progress_callback:
        progress_callback(5.0, "Opening point cloud file and parsing coordinate reference system...")

    with laspy.open(input_path) as reader:
        header = reader.header
        crs_obj, crs_name, crs_repr = parse_crs_from_header(header)
        units = detect_linear_units(crs_obj)
        total_points = header.point_count

        # Determine target bounding box in native coordinates
        if bounding_box_latlon and bounding_box_latlon.get("min_lat") is not None:
            min_x, min_y, max_x, max_y = transform_latlon_bbox_to_native(
                bounding_box_latlon["min_lat"],
                bounding_box_latlon["min_lon"],
                bounding_box_latlon["max_lat"],
                bounding_box_latlon["max_lon"],
                crs_obj
            )
        elif bounding_box_native:
            min_x, min_y, max_x, max_y = bounding_box_native
        else:
            min_x, min_y, max_x, max_y = header.x_min, header.y_min, header.x_max, header.y_max

        # Restrict within actual dataset bounds
        min_x = max(min_x, header.x_min)
        min_y = max(min_y, header.y_min)
        max_x = min(max_x, header.x_max)
        max_y = min(max_y, header.y_max)

        if min_x >= max_x or min_y >= max_y:
            raise ValueError(f"Invalid bounding area: empty intersection with point cloud data bounds.")

        # Ensure cell size is positive and reasonable
        cell_size = max(0.2, float(cell_size))
        cols = int(math.ceil((max_x - min_x) / cell_size))
        rows = int(math.ceil((max_y - min_y) / cell_size))

        # Memory safety: limit maximum single-tile DEM dimensions to 8000x8000
        max_dim = 8000
        if cols > max_dim or rows > max_dim:
            scale_factor = max(cols / max_dim, rows / max_dim)
            cell_size = cell_size * scale_factor
            cols = int(math.ceil((max_x - min_x) / cell_size))
            rows = int(math.ceil((max_y - min_y) / cell_size))

        if progress_callback:
            progress_callback(10.0, f"Streaming {total_points:,} points. Target raster grid: {cols}x{rows} cells @ {cell_size:.2f} {units} resolution...")

        # Setup Accumulation Grids for Raster DEM
        # We accumulate minimum elevation for ground models or mean elevation
        grid_min_z = np.full((rows, cols), np.inf, dtype=np.float32)
        grid_count = np.zeros((rows, cols), dtype=np.int32)
        
        chunk_size = 2_000_000
        points_read = 0
        points_accepted = 0
        
        class_filter_set = set(selected_classes) if selected_classes else None

        # Stream chunks to keep memory footprint low (< 300MB RAM)
        for chunk in reader.chunk_iterator(chunk_size):
            points_read += len(chunk)
            
            x = np.asarray(chunk.x, dtype=np.float64)
            y = np.asarray(chunk.y, dtype=np.float64)
            z = np.asarray(chunk.z, dtype=np.float32)

            # Spatial Bounding Box Filter
            mask = (x >= min_x) & (x <= max_x) & (y >= min_y) & (y <= max_y)

            # Elevation Cutoff Filter
            if elevation_min is not None:
                mask &= (z >= elevation_min)
            if elevation_max is not None:
                mask &= (z <= elevation_max)

            # Classification Filter
            if class_filter_set is not None and hasattr(chunk, "classification"):
                cls = np.asarray(chunk.classification)
                cls_mask = np.isin(cls, list(class_filter_set))
                mask &= cls_mask

            if not np.any(mask):
                pct = min(75.0, 10.0 + (points_read / total_points) * 65.0)
                if progress_callback:
                    progress_callback(pct, f"Processed {points_read:,} / {total_points:,} points ({points_accepted:,} in ROI)...")
                continue

            # Extract accepted points
            x_acc = x[mask]
            y_acc = y[mask]
            z_acc = z[mask]
            points_accepted += len(x_acc)

            # Map coordinates to grid cell indices
            # Raster Y origin is at top (max_y)
            col_idx = np.clip(np.floor((x_acc - min_x) / cell_size).astype(np.int32), 0, cols - 1)
            row_idx = np.clip(np.floor((max_y - y_acc) / cell_size).astype(np.int32), 0, rows - 1)

            # Accumulate into grid using np.minimum.at
            np.minimum.at(grid_min_z, (row_idx, col_idx), z_acc)
            np.add.at(grid_count, (row_idx, col_idx), 1)

            pct = min(75.0, 10.0 + (points_read / total_points) * 65.0)
            if progress_callback:
                progress_callback(pct, f"Processed {points_read:,} / {total_points:,} points ({points_accepted:,} accepted)...")

    if points_accepted == 0:
        raise ValueError("No points found matching the specified bounding box, elevation cutoff, and classification criteria.")

    if progress_callback:
        progress_callback(78.0, "Interpolating DEM surface and filling voids...")

    # Post-process grid
    valid_mask = grid_count > 0
    nodata_value = -9999.0

    dem_array = np.where(valid_mask, grid_min_z, nodata_value)

    # Outlier filter on grid (eliminate isolated single-pixel spikes or pits)
    if outlier_removal and np.sum(valid_mask) > 100:
        filtered_grid = ndimage.median_filter(np.where(valid_mask, grid_min_z, np.nan), size=3)
        valid_filtered = ~np.isnan(filtered_grid)
        diff = np.abs(grid_min_z - filtered_grid)
        spike_mask = valid_mask & valid_filtered & (diff > (cell_size * 5.0))
        dem_array[spike_mask] = filtered_grid[spike_mask]

    # Inpaint / Fill small data voids (e.g. gaps under trees or between scan lines) using distance transform
    invalid_mask = dem_array == nodata_value
    if np.any(invalid_mask) and np.any(~invalid_mask):
        # Calculate nearest distance to valid data
        indices = ndimage.distance_transform_edt(invalid_mask, return_distances=False, return_indices=True)
        filled_dem = dem_array[tuple(indices)]
        
        # Only fill gaps within 5 cells of valid data to avoid extrapolation outside bounding bounds
        dist = ndimage.distance_transform_edt(invalid_mask)
        close_gap_mask = invalid_mask & (dist <= 5.0)
        dem_array[close_gap_mask] = filled_dem[close_gap_mask]

    # Calculate DEM Statistics
    valid_elevations = dem_array[dem_array != nodata_value]
    if len(valid_elevations) == 0:
        raise ValueError("DEM generation produced an empty raster.")

    z_min_final = float(np.min(valid_elevations))
    z_max_final = float(np.max(valid_elevations))
    z_mean_final = float(np.mean(valid_elevations))
    z_std_final = float(np.std(valid_elevations))

    if progress_callback:
        progress_callback(85.0, f"Writing georeferenced GeoTIFF DEM ({cols}x{rows})...")

    # Write GeoTIFF with GDAL
    os.makedirs(os.path.dirname(output_dem_path), exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(
        output_dem_path,
        cols,
        rows,
        1,
        gdal.GDT_Float32,
        options=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"]
    )

    # Affine geotransform: [top_left_x, pixel_width, 0, top_left_y, 0, -pixel_height]
    geotransform = (min_x, cell_size, 0.0, max_y, 0.0, -cell_size)
    ds.SetGeoTransform(geotransform)

    # Set CRS Projection
    if crs_obj:
        srs = osr.SpatialReference()
        srs.ImportFromWkt(crs_obj.to_wkt())
        ds.SetProjection(srs.ExportToWkt())

    band = ds.GetRasterBand(1)
    band.WriteRaster(0, 0, cols, rows, dem_array.astype(np.float32).tobytes())
    band.SetNoDataValue(nodata_value)
    band.FlushCache()
    ds = None # Close and flush dataset

    elapsed = round(time.time() - start_time, 2)

    return {
        "dem_path": output_dem_path,
        "crs_repr": crs_repr,
        "crs_name": crs_name,
        "units": units,
        "cell_size": cell_size,
        "cols": cols,
        "rows": rows,
        "bounds_native": {
            "min_x": round(min_x, 3),
            "max_x": round(max_x, 3),
            "min_y": round(min_y, 3),
            "max_y": round(max_y, 3)
        },
        "points_total": total_points,
        "points_accepted": points_accepted,
        "z_stats": {
            "min": round(z_min_final, 2),
            "max": round(z_max_final, 2),
            "mean": round(z_mean_final, 2),
            "std": round(z_std_final, 2)
        },
        "elapsed_seconds": elapsed
    }
