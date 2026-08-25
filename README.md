# LiDAR Contour Studio

**LiDAR Contour Studio** is a high-performance, cross-platform geospatial application designed for Windows, Linux desktops, and Android tablets / mobile devices. It processes massive LiDAR point clouds (`.las` / `.laz`), performs ground classification filtering, Lat/Lon bounding box cropping, elevation cutoffs, and generates large-scale vector contours, DEM surfaces, and comprehensive engineering QA/QC metadata reports.

---

## Key Features

1. **PDAL & Native Streaming Engine**:
   - Generates standard PDAL JSON pipelines (`readers.las`, `filters.crop`, `filters.range`, `filters.outlier`, `filters.smrf`, `writers.gdal`).
   - High-throughput chunked native streaming engine (Laspy + GDAL + SciPy + NumPy) processing 70M+ point clouds with minimal memory footprint (< 300MB RAM).
2. **Cross-Platform & Touch-Optimized**:
   - Responsive UI with Progressive Web App (PWA) support for **Android tablets**, **iPads**, **Windows**, and **Linux** desktops.
3. **Interactive Bounding Box (Lat / Lon WGS84)**:
   - Visual interactive bounding box drawing on Leaflet satellite/topographic maps with automatic bidirectional reprojection into native projected CRS (e.g. NAD83 Florida East ftUS).
4. **Classification & Point Filtering**:
   - Extraction by ASPRS standard classes: Ground (2), Model Key-points (8), Low/Med/High Veg (3,4,5), Water (9), Unclassified (1).
   - Statistical Outlier Removal (SOR) to eliminate atmospheric noise, birds, and multipath spikes.
5. **Multi-Format Large-Scale Contours**:
   - Vector Contours: **GeoJSON**, **ESRI Shapefile (.shp + .shx + .dbf + .prj)**, **AutoCAD 3D DXF**, **GeoPackage (.gpkg)**.
   - Customizable contour intervals (e.g. 1 ft, 2 ft, 5 ft, 10 ft, 0.5 m, 1 m) with differentiated index/intermediate line weights and attributes.
6. **Automated Engineering QA/QC Report**:
   - Produces detailed HTML (printable to PDF), Markdown, and JSON reports documenting dataset metadata, point density, vertical datums, classification statistics, and engineering limitations.

---

## Quick Start

### 1. Launch Web Application (Desktop & Android Tablet Access)

```bash
python3 run_server.py
```
- **Desktop (Local)**: Open `http://localhost:8000` in your web browser.
- **Android Tablet / Mobile**: Open `http://<YOUR_LOCAL_IP>:8000` in Chrome on your tablet, and tap "Add to Home Screen" to install as a standalone tablet app.

### 2. Command-Line Processing (CLI)

```bash
# Inspect dataset metadata, CRS, and bounds
python3 -m app.cli -i USGS_LPC_FL_Peninsular_FDEM_2018_D19_DRRA_LID2019_224738_E.laz --inspect-only

# Generate 2-ft contours with 10-ft index lines within Lat/Lon bounds
python3 -m app.cli \
  -i USGS_LPC_FL_Peninsular_FDEM_2018_D19_DRRA_LID2019_224738_E.laz \
  -o outputs/florida_run \
  --interval 2.0 \
  --index-mult 5 \
  --classes 2 8 \
  --units ftUS \
  --bbox-latlon 27.950 -82.465 27.965 -82.450
```

---

## Deliverables Generated

When a processing job completes, the following files are produced in `outputs/<job_id>/`:
- `contours.geojson` - Native coordinate vector contours.
- `contours_wgs84.geojson` - WGS84 contours for web visualization.
- `contours_shapefile.zip` - Complete ESRI Shapefile suite (.shp, .shx, .dbf, .prj).
- `contours.dxf` - AutoCAD 3D polyline contours organized into `CONTOUR_INDEX` and `CONTOUR_INTERMEDIATE` layers.
- `dem.tif` - High-resolution georeferenced GeoTIFF DEM.
- `report.html` - Professional engineering quality assurance report.
- `report.md` & `report.json` - Markdown and JSON metadata logs.
- `pdal_pipeline.json` - Reusable PDAL pipeline specification.

---

## License

This project is licensed under the [MIT License](LICENSE) © 2026 band72.

