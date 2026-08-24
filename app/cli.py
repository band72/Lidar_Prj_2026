"""
Command Line Interface for LiDAR Contour Studio
Processes LAS/LAZ files directly from the terminal or automated scripts.
"""

import os
import sys
import argparse
import json
from app.core.native_pipeline import inspect_lidar_file, process_point_cloud_to_dem
from app.core.contour_builder import generate_contours
from app.core.reporter import generate_processing_report
from app.core.pdal_pipeline import PDALPipelineBuilder


def main():
    parser = argparse.ArgumentParser(
        description="LiDAR Contour Studio - High-Performance Point Cloud Processing, DEM Surface and Contour Generator"
    )
    parser.add_argument("-i", "--input", required=True, help="Path to input LAS or LAZ point cloud file")
    parser.add_argument("-o", "--output-dir", default="outputs/cli_run", help="Output directory for deliverables")
    parser.add_argument("--interval", type=float, default=2.0, help="Contour interval (default: 2.0)")
    parser.add_argument("--index-mult", type=int, default=5, help="Index contour multiplier (default: 5)")
    parser.add_argument("--cell-size", type=float, default=2.0, help="DEM cell grid size in native units (default: 2.0)")
    parser.add_argument("--units", choices=["ftUS", "ft", "m"], default="ftUS", help="Working units (default: ftUS)")
    parser.add_argument("--classes", type=int, nargs="+", default=[2, 8], help="ASPRS class codes to extract (default: 2 8)")
    parser.add_argument("--zmin", type=float, default=None, help="Minimum elevation cutoff")
    parser.add_argument("--zmax", type=float, default=None, help="Maximum elevation cutoff")
    parser.add_argument("--bbox-latlon", type=float, nargs=4, metavar=("MIN_LAT", "MIN_LON", "MAX_LAT", "MAX_LON"),
                        help="Bounding box in WGS84 GPS Lat/Lon: min_lat min_lon max_lat max_lon")
    parser.add_argument("--inspect-only", action="store_true", help="Only inspect metadata and print JSON report")
    parser.add_argument("--no-outlier-filter", action="store_true", help="Disable statistical outlier filter")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Inspecting LiDAR dataset: {args.input}")
    meta = inspect_lidar_file(args.input)

    if args.inspect_only:
        print(json.dumps(meta, indent=2))
        sys.exit(0)

    print(f"    - Points: {meta['total_points']:,}")
    print(f"    - CRS: {meta['crs_name']} ({meta['crs_repr']})")
    print(f"    - Elevation (Z): {meta['z_stats']['min']:.1f} to {meta['z_stats']['max']:.1f} {meta['units']}")

    os.makedirs(args.output_dir, exist_ok=True)
    dem_path = os.path.join(args.output_dir, "dem.tif")

    bbox_dict = None
    if args.bbox_latlon:
        bbox_dict = {
            "min_lat": args.bbox_latlon[0],
            "min_lon": args.bbox_latlon[1],
            "max_lat": args.bbox_latlon[2],
            "max_lon": args.bbox_latlon[3]
        }
        print(f"    - ROI Lat/Lon: [{bbox_dict['min_lat']}, {bbox_dict['min_lon']}] to [{bbox_dict['max_lat']}, {bbox_dict['max_lon']}]")

    def progress(pct, msg):
        print(f"[{pct:5.1f}%] {msg}")

    print("\n[*] Processing point cloud to DEM GeoTIFF...")
    dem_meta = process_point_cloud_to_dem(
        input_path=args.input,
        output_dem_path=dem_path,
        bounding_box_latlon=bbox_dict,
        elevation_min=args.zmin,
        elevation_max=args.zmax,
        selected_classes=args.classes,
        cell_size=args.cell_size,
        outlier_removal=not args.no_outlier_filter,
        progress_callback=progress
    )

    print("\n[*] Generating multi-format vector contours...")
    contour_meta = generate_contours(
        dem_raster_path=dem_path,
        output_base_dir=args.output_dir,
        contour_interval=args.interval,
        index_multiplier=args.index_mult,
        progress_callback=progress
    )

    print("\n[*] Compiling QA/QC and limitations engineering report...")
    params = vars(args)
    report_meta = generate_processing_report(
        inspect_meta=meta,
        dem_meta=dem_meta,
        contour_meta=contour_meta,
        processing_params=params,
        output_dir=args.output_dir
    )

    # PDAL JSON pipeline
    pdal = PDALPipelineBuilder(args.input)
    b = dem_meta["bounds_native"]
    pdal.add_crop_box(b["min_x"], b["min_y"], b["max_x"], b["max_y"])
    if args.classes:
        pdal.add_classification_filter(args.classes)
    pdal.save_pipeline(os.path.join(args.output_dir, "pdal_pipeline.json"))

    print("\n" + "="*60)
    print("SUCCESS: Processing Completed!")
    print(f"Total Contours Generated: {contour_meta['total_contours']:,}")
    print(f"Index Contours:           {contour_meta['index_contours']:,}")
    print(f"Intermediate Contours:    {contour_meta['intermediate_contours']:,}")
    print(f"Deliverables Saved To:    {args.output_dir}")
    print(f"  - GeoJSON:              {contour_meta['geojson_path']}")
    print(f"  - ESRI Shapefile ZIP:   {contour_meta['shapefile_zip_path']}")
    print(f"  - AutoCAD DXF:          {contour_meta['dxf_path']}")
    print(f"  - GeoTIFF DEM:          {dem_path}")
    print(f"  - Engineering Report:   {report_meta['html_path']}")
    print("="*60)


if __name__ == "__main__":
    main()
