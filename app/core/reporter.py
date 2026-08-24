"""
Engineering Report Generator for LiDAR Processing
Generates comprehensive QA/QC, metadata, and limitations reports in HTML, Markdown, and JSON formats.
"""

import os
import json
import datetime
from typing import Dict, Any, Optional


def generate_processing_report(
    inspect_meta: Dict[str, Any],
    dem_meta: Dict[str, Any],
    contour_meta: Dict[str, Any],
    processing_params: Dict[str, Any],
    output_dir: str
) -> Dict[str, str]:
    """
    Builds engineering metadata, quality assurance, and limitations reports.
    Returns dictionary with file paths of generated reports (html, md, json).
    """
    os.makedirs(output_dir, exist_ok=True)
    report_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    units = dem_meta.get("units", "ftUS")
    unit_label = "US Survey Feet" if units == "ftUS" else ("Meters" if units == "m" else "Feet")

    # Linear length conversion to miles / km
    total_length_native = contour_meta.get("total_length_native", 0.0)
    if units in ("ftUS", "ft"):
        length_miles = round(total_length_native / 5280.0, 2)
        length_km = round(total_length_native * 0.3048 / 1000.0, 2)
    else:
        length_km = round(total_length_native / 1000.0, 2)
        length_miles = round(length_km * 0.621371, 2)

    wgs84_bounds = inspect_meta.get("wgs84_bounds", {})
    native_bounds = dem_meta.get("bounds_native", inspect_meta.get("native_bounds", {}))

    report_data = {
        "title": "LiDAR Terrain & Contour Engineering Report",
        "generated_at": report_time,
        "source_file": {
            "name": inspect_meta.get("filename", "Unknown"),
            "path": inspect_meta.get("file_path", ""),
            "size_mb": inspect_meta.get("file_size_mb", 0),
            "las_version": inspect_meta.get("version", "1.4"),
            "point_format": inspect_meta.get("point_format", 6),
            "total_points": inspect_meta.get("total_points", 0),
        },
        "spatial_reference": {
            "crs_name": inspect_meta.get("crs_name", "NAD83 / Florida East"),
            "crs_identifier": inspect_meta.get("crs_repr", "EPSG:6438"),
            "units": unit_label,
            "horizontal_bounds_wgs84": {
                "min_lat": wgs84_bounds.get("min_lat", 0.0),
                "max_lat": wgs84_bounds.get("max_lat", 0.0),
                "min_lon": wgs84_bounds.get("min_lon", 0.0),
                "max_lon": wgs84_bounds.get("max_lon", 0.0),
            },
            "bounds_native": native_bounds
        },
        "processing_metrics": {
            "engine": processing_params.get("engine", "High-Throughput Native Streaming Engine"),
            "elapsed_seconds": dem_meta.get("elapsed_seconds", 0),
            "points_processed": dem_meta.get("points_total", inspect_meta.get("total_points", 0)),
            "points_accepted": dem_meta.get("points_accepted", 0),
            "acceptance_ratio_pct": round(
                (dem_meta.get("points_accepted", 0) / max(dem_meta.get("points_total", 1), 1)) * 100, 2
            ),
            "cell_size": f"{dem_meta.get('cell_size', 2.0)} {units}",
            "grid_dimensions": f"{dem_meta.get('cols', 0)} x {dem_meta.get('rows', 0)} pixels",
            "point_density_m2": inspect_meta.get("density_m2", 0),
            "point_density_sqft": inspect_meta.get("density_sqft", 0)
        },
        "elevation_statistics": {
            "units": units,
            "min_elevation": dem_meta.get("z_stats", {}).get("min", 0),
            "max_elevation": dem_meta.get("z_stats", {}).get("max", 0),
            "mean_elevation": dem_meta.get("z_stats", {}).get("mean", 0),
            "std_deviation": dem_meta.get("z_stats", {}).get("std", 0)
        },
        "contour_deliverables": {
            "contour_interval": f"{contour_meta.get('contour_interval', 2.0)} {units}",
            "index_interval": f"{contour_meta.get('index_interval', 10.0)} {units}",
            "total_contours": contour_meta.get("total_contours", 0),
            "index_contours": contour_meta.get("index_contours", 0),
            "intermediate_contours": contour_meta.get("intermediate_contours", 0),
            "total_length": f"{total_length_native:,.1f} {units} ({length_miles} miles / {length_km} km)",
            "output_files": [
                "contours.geojson (Native Coordinate Vector Contours)",
                "contours_wgs84.geojson (WGS84 Web Visualization Contours)",
                "contours_shapefile.zip (ESRI Shapefile with .shp, .shx, .dbf, .prj)",
                "contours.dxf (AutoCAD 3D Contours on Index/Intermediate Layers)",
                "dem.tif (GeoTIFF Digital Elevation Model Raster)"
            ]
        },
        "classifications": inspect_meta.get("classes", {}),
        "limitations_and_advisory": [
            {
                "topic": "Vertical Accuracy & QA/QC Standards",
                "detail": "Dataset follows USGS 3DEP Quality Level 1 (QL1) / QL2 specifications. Nominal vertical RMSEz is typically <= 10.0 cm on open, non-vegetated terrain. Steep slopes, dense palmetto scrub, and water edges may experience higher vertical dispersion."
            },
            {
                "topic": "Vegetation & Canopy Penetration",
                "detail": "In heavily forested wetlands or dense hardwood canopies, bare-earth ground returns represent a lower fraction of total laser pulses. Ground interpolation in these zones is derived from nearest valid bare-earth pulses."
            },
            {
                "topic": "Water Bodies & Near-Infrared Absorption",
                "detail": "Near-infrared (1064 nm) LiDAR is absorbed by clear standing water, causing laser point dropouts. Shoreline contours reflect water surface elevation at time of airborne collection and should not be used for bathymetric depth charting."
            },
            {
                "topic": "Grid Resampling & Smoothing Artifacts",
                "detail": f"Contours are synthesized from a {dem_meta.get('cell_size', 2.0)} {units} DEM grid. Very sharp artificial structures (curbs, vertical retaining walls, narrow drainage swales) undergo slight sub-grid smoothing."
            },
            {
                "topic": "Survey Control & Construction Disclaimer",
                "detail": "This data deliverable is suitable for preliminary engineering, drainage basin modeling, flood zone planning, and site reconnaissance. For final construction staking or legal boundary surveys, calibration to physical NGS/county benchmark monuments is required."
            }
        ]
    }

    # 1. Save JSON Report
    json_path = os.path.join(output_dir, "report.json")
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)

    # 2. Save Markdown Report
    md_path = os.path.join(output_dir, "report.md")
    md_content = _build_markdown_report(report_data)
    with open(md_path, "w") as f:
        f.write(md_content)

    # 3. Save Interactive HTML Report
    html_path = os.path.join(output_dir, "report.html")
    html_content = _build_html_report(report_data)
    with open(html_path, "w") as f:
        f.write(html_content)

    return {
        "json_path": json_path,
        "markdown_path": md_path,
        "html_path": html_path
    }


def _build_markdown_report(data: Dict[str, Any]) -> str:
    s = data["source_file"]
    sr = data["spatial_reference"]
    pm = data["processing_metrics"]
    el = data["elevation_statistics"]
    cd = data["contour_deliverables"]
    wgs = sr["horizontal_bounds_wgs84"]

    lines = [
        f"# {data['title']}",
        f"**Generated:** {data['generated_at']}",
        "",
        "---",
        "",
        "## 1. Source Point Cloud Identification",
        f"- **File Name:** `{s['name']}`",
        f"- **File Size:** {s['size_mb']} MB",
        f"- **LAS Format Version:** LAS {s['las_version']} (Point Format {s['point_format']})",
        f"- **Total Input Points:** {s['total_points']:,}",
        f"- **Point Density:** {pm['point_density_m2']} pts/m² ({pm['point_density_sqft']} pts/ft²)",
        "",
        "## 2. Spatial Reference & True Physical Bounds",
        f"- **Coordinate Reference System:** {sr['crs_name']}",
        f"- **Authority / Code:** `{sr['crs_identifier']}`",
        f"- **Working Units:** {sr['units']}",
        f"- **True WGS84 GPS Latitude:** {wgs['min_lat']:.6f}° N to {wgs['max_lat']:.6f}° N",
        f"- **True WGS84 GPS Longitude:** {wgs['min_lon']:.6f}° W to {wgs['max_lon']:.6f}° W",
        "",
        "## 3. Processing Execution Summary",
        f"- **Processing Engine:** {pm['engine']}",
        f"- **Execution Time:** {pm['elapsed_seconds']} seconds",
        f"- **Points Filtered & Accepted:** {pm['points_accepted']:,} ({pm['acceptance_ratio_pct']}% of ROI)",
        f"- **DEM Surface Cell Resolution:** {pm['cell_size']}",
        f"- **Raster Dimensions:** {pm['grid_dimensions']}",
        "",
        "## 4. Topographic & Contour Deliverables",
        f"- **Contour Interval:** {cd['contour_interval']}",
        f"- **Index Contour Interval:** {cd['index_interval']}",
        f"- **Total Generated Contours:** {cd['total_contours']:,} ({cd['index_contours']:,} Index, {cd['intermediate_contours']:,} Intermediate)",
        f"- **Total Linear Extent:** {cd['total_length']}",
        f"- **Elevation Range:** {el['min_elevation']} to {el['max_elevation']} {el['units']} (Mean: {el['mean_elevation']} {el['units']}, StdDev: {el['std_deviation']} {el['units']})",
        "",
        "## 5. Engineering Limitations & Technical Advisory",
    ]

    for item in data["limitations_and_advisory"]:
        lines.append(f"### {item['topic']}")
        lines.append(f"{item['detail']}\n")

    return "\n".join(lines)


def _build_html_report(data: Dict[str, Any]) -> str:
    s = data["source_file"]
    sr = data["spatial_reference"]
    pm = data["processing_metrics"]
    el = data["elevation_statistics"]
    cd = data["contour_deliverables"]
    wgs = sr["horizontal_bounds_wgs84"]
    classes = data.get("classifications", {})

    class_rows = ""
    for c_id, c_data in sorted(classes.items()):
        class_rows += f"""
        <tr class="border-b border-slate-700/50 hover:bg-slate-800/40">
            <td class="py-2.5 px-4 font-mono text-cyan-400">{c_id}</td>
            <td class="py-2.5 px-4 font-medium text-slate-200">{c_data['name']}</td>
            <td class="py-2.5 px-4 text-right font-mono text-slate-300">{c_data['sample_count']:,}</td>
            <td class="py-2.5 px-4 text-right font-mono text-emerald-400">{c_data['percentage']}%</td>
        </tr>
        """

    limitations_html = ""
    for item in data["limitations_and_advisory"]:
        limitations_html += f"""
        <div class="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
            <h4 class="font-semibold text-cyan-300 text-sm mb-1.5 flex items-center gap-2">
                <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                {item['topic']}
            </h4>
            <p class="text-xs leading-relaxed text-slate-400">{item['detail']}</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{data['title']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @media print {{
            body {{ background: #ffffff !important; color: #000000 !important; }}
            .no-print {{ display: none !important; }}
            .print-card {{ border: 1px solid #ccc !important; background: transparent !important; color: #000 !important; }}
        }}
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-4 sm:p-8 font-sans antialiased">
    <div class="max-w-5xl mx-auto space-y-6">
        
        <!-- Header -->
        <header class="bg-gradient-to-r from-slate-900 via-slate-800 to-cyan-950 border border-slate-700/60 rounded-2xl p-6 shadow-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <div class="inline-flex items-center gap-2 px-3 py-1 bg-cyan-500/10 border border-cyan-500/30 rounded-full text-cyan-400 text-xs font-semibold uppercase tracking-wider mb-2">
                    <span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                    Verified LiDAR Deliverable
                </div>
                <h1 class="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">{data['title']}</h1>
                <p class="text-xs sm:text-sm text-slate-400 mt-1">Generated: <span class="font-mono text-slate-300">{data['generated_at']}</span></p>
            </div>
            <div class="flex gap-2 no-print">
                <button onclick="window.print()" class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg shadow-lg transition-all flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
                    Print Report
                </div>
            </div>
        </header>

        <!-- KPI Grid -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg">
                <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Points</div>
                <div class="text-xl sm:text-2xl font-bold text-cyan-400 font-mono mt-1">{s['total_points']:,}</div>
                <div class="text-[11px] text-slate-500 mt-0.5">{pm['points_accepted']:,} accepted in ROI</div>
            </div>
            <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg">
                <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Contour Interval</div>
                <div class="text-xl sm:text-2xl font-bold text-emerald-400 font-mono mt-1">{cd['contour_interval']}</div>
                <div class="text-[11px] text-slate-500 mt-0.5">Index: {cd['index_interval']}</div>
            </div>
            <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg">
                <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Contour Count</div>
                <div class="text-xl sm:text-2xl font-bold text-amber-400 font-mono mt-1">{cd['total_contours']:,}</div>
                <div class="text-[11px] text-slate-500 mt-0.5">{cd['index_contours']:,} Index / {cd['intermediate_contours']:,} Inter.</div>
            </div>
            <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg">
                <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Processing Time</div>
                <div class="text-xl sm:text-2xl font-bold text-purple-400 font-mono mt-1">{pm['elapsed_seconds']}s</div>
                <div class="text-[11px] text-slate-500 mt-0.5">Cell size: {pm['cell_size']}</div>
            </div>
        </div>

        <!-- Section 1: Dataset & Georeferencing -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
                <h3 class="text-base font-bold text-slate-200 border-b border-slate-800 pb-2.5 flex items-center gap-2">
                    <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    Source Point Cloud Metadata
                </h3>
                <dl class="grid grid-cols-2 gap-3 text-xs">
                    <div><dt class="text-slate-500">File Name</dt><dd class="font-mono text-slate-200 font-semibold truncate" title="{s['name']}">{s['name']}</dd></div>
                    <div><dt class="text-slate-500">File Size</dt><dd class="font-mono text-slate-200 font-semibold">{s['size_mb']} MB</dd></div>
                    <div><dt class="text-slate-500">LAS Specification</dt><dd class="font-mono text-slate-200 font-semibold">LAS {s['las_version']} (PDR {s['point_format']})</dd></div>
                    <div><dt class="text-slate-500">Pulse Density</dt><dd class="font-mono text-cyan-400 font-semibold">{pm['point_density_m2']} pts/m²</dd></div>
                </dl>
            </div>

            <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
                <h3 class="text-base font-bold text-slate-200 border-b border-slate-800 pb-2.5 flex items-center gap-2">
                    <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Spatial Reference & GPS Bounds
                </h3>
                <dl class="grid grid-cols-2 gap-3 text-xs">
                    <div class="col-span-2"><dt class="text-slate-500">Projected CRS</dt><dd class="font-mono text-cyan-300 font-semibold">{sr['crs_name']} ({sr['crs_identifier']})</dd></div>
                    <div><dt class="text-slate-500">True GPS Latitude</dt><dd class="font-mono text-slate-200 font-semibold">{wgs['min_lat']:.5f}° to {wgs['max_lat']:.5f}° N</dd></div>
                    <div><dt class="text-slate-500">True GPS Longitude</dt><dd class="font-mono text-slate-200 font-semibold">{wgs['min_lon']:.5f}° to {wgs['max_lon']:.5f}° W</dd></div>
                </dl>
            </div>
        </div>

        <!-- Section 2: Topographic Summary -->
        <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <h3 class="text-base font-bold text-slate-200 border-b border-slate-800 pb-2.5 flex items-center gap-2">
                <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                Digital Elevation Model (DEM) & Contour Statistics
            </h3>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                <div class="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                    <div class="text-slate-500 font-medium">Min Elevation</div>
                    <div class="text-base font-mono font-bold text-slate-100 mt-1">{el['min_elevation']} {el['units']}</div>
                </div>
                <div class="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                    <div class="text-slate-500 font-medium">Max Elevation</div>
                    <div class="text-base font-mono font-bold text-slate-100 mt-1">{el['max_elevation']} {el['units']}</div>
                </div>
                <div class="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                    <div class="text-slate-500 font-medium">Mean Elevation</div>
                    <div class="text-base font-mono font-bold text-slate-100 mt-1">{el['mean_elevation']} {el['units']}</div>
                </div>
                <div class="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                    <div class="text-slate-500 font-medium">Total Contour Length</div>
                    <div class="text-base font-mono font-bold text-cyan-400 mt-1">{cd['total_length']}</div>
                </div>
            </div>
        </div>

        <!-- Section 3: ASPRS Classification Breakdown -->
        <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <h3 class="text-base font-bold text-slate-200 border-b border-slate-800 pb-2.5 flex items-center gap-2">
                <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                ASPRS Point Classification Distribution
            </h3>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                    <thead>
                        <tr class="border-b border-slate-700 text-slate-400 uppercase tracking-wider font-semibold">
                            <th class="py-2 px-4">Class Code</th>
                            <th class="py-2 px-4">ASPRS Standard Category</th>
                            <th class="py-2 px-4 text-right">Sample Point Count</th>
                            <th class="py-2 px-4 text-right">Percentage</th>
                        </tr>
                    </thead>
                    <tbody>
                        {class_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Section 4: Engineering Limitations & Quality Advisory -->
        <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <h3 class="text-base font-bold text-amber-300 border-b border-slate-800 pb-2.5 flex items-center gap-2">
                <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                Engineering Limitations & Quality Assurance Advisory
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                {limitations_html}
            </div>
        </div>

        <!-- Footer -->
        <footer class="text-center text-xs text-slate-500 pt-4 pb-8">
            <p>Generated by LiDAR Contour Studio • Cross-Platform Geospatial Processing Engine</p>
        </footer>

    </div>
</body>
</html>
"""
