"""
FastAPI Route Handlers for LiDAR Contour Studio
Provides endpoints for file inspection, asynchronous processing, SSE progress streaming,
and multi-format deliverable downloads.
"""

import os
import sys
import uuid
import asyncio
import json
import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.native_pipeline import inspect_lidar_file, process_point_cloud_to_dem
from app.core.contour_builder import generate_contours
from app.core.reporter import generate_processing_report
from app.core.pdal_pipeline import PDALPipelineBuilder

router = APIRouter()

# Global in-memory job registry
JOBS: Dict[str, Dict[str, Any]] = {}
JOB_QUEUES: Dict[str, asyncio.Queue] = {}


class InspectRequest(BaseModel):
    file_path: str = Field(..., description="Absolute or relative path to LAS/LAZ file")


class ProcessRequest(BaseModel):
    file_path: str = Field(..., description="Path to LAS/LAZ file")
    output_dir: Optional[str] = Field(None, description="Custom output destination folder")
    units: str = Field("ftUS", description="Target linear units: ftUS, ft, or m")
    contour_interval: float = Field(2.0, description="Contour interval in target units")
    index_multiplier: int = Field(5, description="Index contour multiplier (e.g. 5 for every 5th contour)")
    bounding_box_latlon: Optional[Dict[str, float]] = Field(None, description="Bounding area {min_lat, max_lat, min_lon, max_lon}")
    elevation_min: Optional[float] = Field(None, description="Minimum elevation cutoff")
    elevation_max: Optional[float] = Field(None, description="Maximum elevation cutoff")
    selected_classes: Optional[List[int]] = Field(None, description="List of ASPRS class codes to include (e.g. [2] for ground)")
    cell_size: float = Field(2.0, description="Raster DEM resolution in native units")
    outlier_removal: bool = Field(True, description="Enable statistical outlier filter")
    engine_preference: str = Field("auto", description="Processing engine: 'auto', 'native', or 'pdal'")


class OpenFolderRequest(BaseModel):
    path: str


class CreateFolderRequest(BaseModel):
    parent_path: str
    folder_name: str


class NativePickRequest(BaseModel):
    mode: str = "file"  # "file" or "folder"
    initial_path: Optional[str] = None


@router.get("/api/browse")
async def browse_filesystem(path: Optional[str] = None, mode: str = "all", show_hidden: bool = False, search: Optional[str] = None):
    """
    Enhanced Linux and cross-platform filesystem browser with breadcrumbs,
    quick system locations, search filtering, and rich file metadata.
    """
    if path and path.strip():
        expanded = os.path.expanduser(path.strip())
        if os.path.exists(expanded):
            target_dir = os.path.abspath(expanded)
            if not os.path.isdir(target_dir):
                target_dir = os.path.dirname(target_dir)
        else:
            parent = os.path.dirname(os.path.abspath(expanded))
            target_dir = parent if os.path.exists(parent) else os.getcwd()
    else:
        target_dir = os.getcwd()

    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        target_dir = os.getcwd()

    # Determine parent directory
    candidate_parent = os.path.dirname(target_dir)
    parent_dir = candidate_parent if target_dir != os.path.abspath(os.sep) and candidate_parent != target_dir else None

    # Build clickable breadcrumb list (Windows + Linux + macOS safe)
    breadcrumbs = []
    drive, path_without_drive = os.path.splitdrive(os.path.normpath(target_dir))
    parts = [p for p in path_without_drive.split(os.sep) if p]

    if drive:
        # Windows drive root (e.g. C:\)
        accum = drive + os.sep
        breadcrumbs.append({"name": f"Drive ({drive})", "path": accum})
    else:
        # Unix/Linux root (/)
        accum = "/"
        breadcrumbs.append({"name": "Root (/)", "path": "/"})

    for part in parts:
        accum = os.path.join(accum, part)
        breadcrumbs.append({"name": part, "path": accum})

    # Standard Cross-Platform Quick Locations (Windows, Linux, macOS)
    home_dir = os.path.expanduser("~")
    quick_locations = [
        {"name": "Project Workspace", "path": os.getcwd(), "icon": "project"},
        {"name": "Outputs Folder", "path": os.path.join(os.getcwd(), "outputs"), "icon": "output"},
        {"name": "Downloads", "path": os.path.join(home_dir, "Downloads"), "icon": "downloads"},
        {"name": "Documents", "path": os.path.join(home_dir, "Documents"), "icon": "documents"},
        {"name": "Desktop", "path": os.path.join(home_dir, "Desktop"), "icon": "desktop"},
        {"name": "Home Directory", "path": home_dir, "icon": "home"},
    ]

    # Windows Drive Letters (C:, D:, E:, F:, etc.)
    if sys.platform.startswith("win"):
        import string
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                quick_locations.append({"name": f"Local Disk ({letter}:)", "path": drive_path, "icon": "drive"})
    else:
        # Linux & macOS roots
        quick_locations.append({"name": "File System (Root)", "path": "/", "icon": "root"})
        if os.path.exists("/media"):
            quick_locations.append({"name": "Media / USB Drives", "path": "/media", "icon": "media"})
        if os.path.exists("/mnt"):
            quick_locations.append({"name": "Mounts (/mnt)", "path": "/mnt", "icon": "mnt"})
        if os.path.exists("/Volumes"):
            quick_locations.append({"name": "Mac Volumes", "path": "/Volumes", "icon": "volumes"})

    quick_locations = [loc for loc in quick_locations if os.path.exists(loc["path"])]

    directories = []
    files = []

    try:
        entries = sorted(os.scandir(target_dir), key=lambda e: (not e.is_dir(), e.name.lower()))
        for entry in entries:
            try:
                # Hidden file filter
                if not show_hidden and entry.name.startswith("."):
                    continue

                # Search filter
                if search and search.strip():
                    if search.strip().lower() not in entry.name.lower():
                        continue

                stat = entry.stat()
                mod_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

                if entry.is_dir():
                    try:
                        child_count = len([x for x in os.listdir(entry.path) if not x.startswith(".")])
                    except Exception:
                        child_count = 0

                    directories.append({
                        "name": entry.name,
                        "path": entry.path,
                        "child_count": child_count,
                        "modified": mod_time
                    })
                elif entry.is_file():
                    is_lidar = entry.name.lower().endswith((".las", ".laz"))
                    if mode == "folder":
                        continue
                    if mode == "file" and not is_lidar:
                        continue

                    sz_mb = round(stat.st_size / (1024 * 1024), 2)
                    files.append({
                        "name": entry.name,
                        "path": entry.path,
                        "size_mb": sz_mb,
                        "size_bytes": stat.st_size,
                        "is_lidar": is_lidar,
                        "modified": mod_time
                    })
            except (PermissionError, OSError):
                continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list directory: {str(e)}")

    return {
        "current_path": target_dir,
        "parent_path": parent_dir,
        "breadcrumbs": breadcrumbs,
        "quick_locations": quick_locations,
        "directories": directories,
        "files": files
    }


@router.post("/api/upload")
async def upload_point_cloud(file: UploadFile = File(...), target_dir: Optional[str] = Query(None)):
    """Uploads a LAS/LAZ file from client device to workspace or target folder."""
    if not file.filename.lower().endswith((".las", ".laz")):
        raise HTTPException(status_code=400, detail="Only .las and .laz point cloud files are allowed")

    if target_dir and os.path.exists(target_dir) and os.path.isdir(target_dir):
        upload_dir = os.path.abspath(target_dir)
    else:
        upload_dir = os.path.join(os.getcwd(), "inputs")
        os.makedirs(upload_dir, exist_ok=True)

    dest_path = os.path.join(upload_dir, file.filename)

    with open(dest_path, "wb") as buffer:
        while content := await file.read(1024 * 1024 * 10): # 10MB chunk
            buffer.write(content)

    file_size_mb = round(os.path.getsize(dest_path) / (1024 * 1024), 2)
    return {
        "status": "uploaded",
        "filename": file.filename,
        "path": dest_path,
        "size_mb": file_size_mb
    }


@router.post("/api/create-folder")
async def create_new_folder(req: CreateFolderRequest):
    """Creates a new subdirectory inside the specified parent folder."""
    if not req.folder_name or not req.folder_name.strip():
        raise HTTPException(status_code=400, detail="Folder name is required")

    parent = os.path.abspath(req.parent_path)
    if not os.path.exists(parent):
        raise HTTPException(status_code=404, detail="Parent directory does not exist")

    new_path = os.path.join(parent, req.folder_name.strip())
    try:
        os.makedirs(new_path, exist_ok=False)
        return {"status": "created", "path": new_path}
    except FileExistsError:
        raise HTTPException(status_code=400, detail="A folder with this name already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {str(e)}")


@router.post("/api/native-pick")
async def native_pick_dialog(req: NativePickRequest):
    """
    Opens the Linux/Desktop native file or folder picker dialog (Zenity, KDialog, or Tkinter).
    Returns the selected absolute path.
    """
    import subprocess
    import shutil
    import sys

    initial = os.path.abspath(req.initial_path) if req.initial_path and os.path.exists(req.initial_path) else os.getcwd()
    if not os.path.isdir(initial):
        initial = os.path.dirname(initial)

    # 1. Try Zenity (Native GNOME / Ubuntu file chooser)
    if shutil.which("zenity") and "DISPLAY" in os.environ:
        try:
            if req.mode == "folder":
                cmd = [
                    "zenity", "--file-selection", "--directory",
                    "--title=Select Output Destination Folder",
                    f"--filename={initial}/"
                ]
            else:
                cmd = [
                    "zenity", "--file-selection",
                    "--title=Select Input LiDAR Point Cloud (.las / .laz)",
                    "--file-filter=LiDAR Point Clouds (*.las *.laz) | *.las *.laz *.LAS *.LAZ",
                    "--file-filter=All Files | *",
                    f"--filename={initial}/"
                ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return {"status": "selected", "path": res.stdout.strip()}
            elif res.returncode == 1:
                return {"status": "cancelled", "path": None}
        except Exception:
            pass

    # 2. Try Tkinter fallback
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        if req.mode == "folder":
            chosen = filedialog.askdirectory(initialdir=initial, title="Select Output Destination Folder")
        else:
            chosen = filedialog.askopenfilename(
                initialdir=initial,
                title="Select Input LiDAR Point Cloud (.las / .laz)",
                filetypes=[("LiDAR Point Clouds", "*.las *.laz *.LAS *.LAZ"), ("All Files", "*.*")]
            )
        root.destroy()

        if chosen:
            return {"status": "selected", "path": chosen}
        return {"status": "cancelled", "path": None}
    except Exception as e:
        return {"status": "error", "error": f"Native dialog unavailable: {str(e)}", "path": None}


@router.post("/api/open-folder")
async def open_system_folder(req: OpenFolderRequest):
    """Opens a folder in the local OS file manager (Linux, Windows, macOS)."""
    target = os.path.abspath(req.path)
    if not os.path.exists(target):
        os.makedirs(target, exist_ok=True)

    import subprocess
    import sys

    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", target])
        elif sys.platform.startswith("win"):
            os.startfile(target)
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", target])
        return {"status": "opened", "path": target}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not open file manager: {str(e)}")


def find_system_lidar_files(search_base: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fast recursive discovery of LAS/LAZ point clouds across standard
    Linux directories (Project, Downloads, Documents, Home, Media).
    """
    home = os.path.expanduser("~")
    if search_base and os.path.exists(search_base):
        roots = [os.path.abspath(search_base)]
    else:
        roots = [
            os.getcwd(),
            os.path.join(home, "Downloads"),
            os.path.join(home, "Documents"),
            home,
        ]
        if os.path.exists("/media"):
            roots.append("/media")

    found = []
    seen = set()

    for base in roots:
        if not os.path.exists(base):
            continue
        try:
            for root, dirs, filenames in os.walk(base, topdown=True):
                # Prune hidden directories, node_modules, and cache trees
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d not in ("node_modules", "__pycache__", "venv", ".cache", "proc", "sys", "dev")
                ]
                # Depth limit relative to base
                depth = root[len(base):].count(os.sep)
                if depth >= 4:
                    dirs[:] = []

                for f in filenames:
                    if f.lower().endswith((".las", ".laz")):
                        full_p = os.path.abspath(os.path.join(root, f))
                        if full_p not in seen:
                            seen.add(full_p)
                            sz_mb = round(os.path.getsize(full_p) / (1024 * 1024), 2)
                            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%Y-%m-%d %H:%M")
                            found.append({
                                "name": f,
                                "directory": os.path.dirname(full_p),
                                "absolute_path": full_p,
                                "size_mb": sz_mb,
                                "modified": mod_time
                            })
        except Exception:
            continue

    found.sort(key=lambda x: x["size_mb"], reverse=True)
    return found


@router.get("/api/files")
async def list_available_files(directory: Optional[str] = None):
    """Lists LAS and LAZ files across workspace, Downloads, and Home."""
    files = find_system_lidar_files(search_base=directory)
    return {"directory": directory or os.getcwd(), "files": files}


@router.get("/api/search-lidar")
async def search_lidar_files(query: Optional[str] = None, directory: Optional[str] = None):
    """Deep recursive search for LAS and LAZ files matching query string."""
    files = find_system_lidar_files(search_base=directory)
    if query and query.strip():
        q = query.strip().lower()
        files = [f for f in files if q in f["name"].lower() or q in f["absolute_path"].lower()]
    return {"query": query, "total_found": len(files), "files": files}


@router.post("/api/inspect")
async def inspect_file(req: InspectRequest):
    """Inspects a LAS/LAZ file and returns metadata, CRS, bounds, and class distribution."""
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

    try:
        meta = inspect_lidar_file(req.file_path)
        return meta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inspection failed: {str(e)}")


def run_pipeline_worker(job_id: str, req: ProcessRequest, loop: asyncio.AbstractEventLoop):
    """Background worker for LiDAR processing."""
    if req.output_dir and req.output_dir.strip():
        output_dir = os.path.abspath(req.output_dir.strip())
    else:
        output_dir = os.path.join(os.getcwd(), "outputs", job_id)
    os.makedirs(output_dir, exist_ok=True)

    def progress_callback(percentage: float, message: str):
        JOBS[job_id]["progress"] = round(percentage, 1)
        JOBS[job_id]["status_message"] = message
        JOBS[job_id]["logs"].append(f"[{round(percentage)}%] {message}")
        if job_id in JOB_QUEUES:
            loop.call_soon_threadsafe(
                JOB_QUEUES[job_id].put_nowait,
                {"type": "progress", "progress": round(percentage, 1), "message": message}
            )

    try:
        progress_callback(2.0, "Initializing LiDAR Contour Studio pipeline...")

        # 1. Inspect file metadata
        inspect_meta = inspect_lidar_file(req.file_path)
        
        # 2. Process Point Cloud to DEM GeoTIFF
        dem_output_path = os.path.join(output_dir, "dem.tif")
        dem_meta = process_point_cloud_to_dem(
            input_path=req.file_path,
            output_dem_path=dem_output_path,
            bounding_box_latlon=req.bounding_box_latlon,
            elevation_min=req.elevation_min,
            elevation_max=req.elevation_max,
            selected_classes=req.selected_classes,
            cell_size=req.cell_size,
            outlier_removal=req.outlier_removal,
            progress_callback=progress_callback
        )

        # 3. Generate Multi-Format Contours
        contour_meta = generate_contours(
            dem_raster_path=dem_output_path,
            output_base_dir=output_dir,
            contour_interval=req.contour_interval,
            index_multiplier=req.index_multiplier,
            progress_callback=progress_callback
        )

        # 4. Generate Engineering QA/QC Report
        progress_callback(98.0, "Compiling Engineering QA/QC & Limitations Report...")
        report_meta = generate_processing_report(
            inspect_meta=inspect_meta,
            dem_meta=dem_meta,
            contour_meta=contour_meta,
            processing_params=req.model_dump(),
            output_dir=output_dir
        )

        # Also generate standard PDAL pipeline JSON for reference
        pdal_builder = PDALPipelineBuilder(req.file_path)
        if req.bounding_box_latlon:
            b = dem_meta["bounds_native"]
            pdal_builder.add_crop_box(b["min_x"], b["min_y"], b["max_x"], b["max_y"])
        if req.elevation_min or req.elevation_max:
            pdal_builder.add_elevation_filter(req.elevation_min, req.elevation_max)
        if req.selected_classes:
            pdal_builder.add_classification_filter(req.selected_classes)
        pdal_builder.save_pipeline(os.path.join(output_dir, "pdal_pipeline.json"))

        progress_callback(100.0, "Processing completed successfully!")

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["results"] = {
            "job_id": job_id,
            "output_dir": output_dir,
            "dem_meta": dem_meta,
            "contour_meta": contour_meta,
            "inspect_meta": inspect_meta,
            "report_paths": report_meta,
            "wgs84_geojson_url": f"/api/contours-geojson/{job_id}",
            "files": {
                "geojson": os.path.join(output_dir, "contours.geojson"),
                "wgs84_geojson": os.path.join(output_dir, "contours_wgs84.geojson"),
                "shapefile_zip": os.path.join(output_dir, "contours_shapefile.zip"),
                "dxf": os.path.join(output_dir, "contours.dxf"),
                "dem_tif": dem_output_path,
                "report_html": report_meta["html_path"],
                "report_md": report_meta["markdown_path"],
                "report_json": report_meta["json_path"],
                "pdal_pipeline": os.path.join(output_dir, "pdal_pipeline.json")
            }
        }

        if job_id in JOB_QUEUES:
            loop.call_soon_threadsafe(
                JOB_QUEUES[job_id].put_nowait,
                {"type": "completed", "results": JOBS[job_id]["results"]}
            )

    except Exception as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)
        progress_callback(100.0, f"Error: {str(e)}")
        if job_id in JOB_QUEUES:
            loop.call_soon_threadsafe(
                JOB_QUEUES[job_id].put_nowait,
                {"type": "error", "error": str(e)}
            )


@router.post("/api/process")
async def start_process(req: ProcessRequest, background_tasks: BackgroundTasks):
    """Starts asynchronous processing for the specified LAS/LAZ dataset."""
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail=f"Input file not found: {req.file_path}")

    job_id = str(uuid.uuid4())[:8]
    loop = asyncio.get_event_loop()

    JOBS[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "progress": 0.0,
        "status_message": "Queued for processing...",
        "logs": [],
        "created_at": asyncio.get_event_loop().time()
    }
    JOB_QUEUES[job_id] = asyncio.Queue()

    background_tasks.add_task(run_pipeline_worker, job_id, req, loop)
    return {"job_id": job_id, "status": "processing"}


@router.get("/api/progress/{job_id}")
async def stream_progress(job_id: str):
    """SSE endpoint to stream real-time progress events."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        # First send existing logs
        job = JOBS.get(job_id, {})
        for log in job.get("logs", []):
            yield f"data: {json.dumps({'type': 'log', 'message': log})}\n\n"

        queue = JOB_QUEUES.get(job_id)
        if not queue:
            yield f"data: {json.dumps({'type': 'status', 'status': job.get('status')})}\n\n"
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("completed", "error"):
                    break
            except asyncio.TimeoutError:
                # Keep alive ping
                yield f": ping\n\n"
                if JOBS.get(job_id, {}).get("status") in ("completed", "failed"):
                    break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/results/{job_id}")
async def get_results(job_id: str):
    """Returns the job status and output deliverables."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]


@router.get("/api/contours-geojson/{job_id}")
async def get_contours_geojson(job_id: str):
    """Streams WGS84 GeoJSON for interactive Leaflet map preview."""
    job = JOBS.get(job_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Contours not ready or job not found")

    wgs84_path = job["results"]["files"]["wgs84_geojson"]
    if not os.path.exists(wgs84_path):
        raise HTTPException(status_code=404, detail="WGS84 GeoJSON file missing")

    return FileResponse(wgs84_path, media_type="application/json")


@router.get("/api/download/{job_id}/{file_type}")
async def download_file(job_id: str, file_type: str):
    """Download deliverables: shapefile, dxf, geojson, dem, report."""
    job = JOBS.get(job_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Job not found or incomplete")

    files = job["results"]["files"]
    mapping = {
        "shapefile": (files["shapefile_zip"], f"contours_{job_id}_shp.zip", "application/zip"),
        "dxf": (files["dxf"], f"contours_{job_id}.dxf", "application/dxf"),
        "geojson": (files["geojson"], f"contours_{job_id}.geojson", "application/geo+json"),
        "wgs84_geojson": (files["wgs84_geojson"], f"contours_{job_id}_wgs84.geojson", "application/geo+json"),
        "dem": (files["dem_tif"], f"dem_{job_id}.tif", "image/tiff"),
        "report_html": (files["report_html"], f"report_{job_id}.html", "text/html"),
        "report_md": (files["report_md"], f"report_{job_id}.md", "text/markdown"),
        "report_json": (files["report_json"], f"report_{job_id}.json", "application/json"),
        "pdal_pipeline": (files["pdal_pipeline"], f"pipeline_{job_id}.json", "application/json"),
    }

    if file_type not in mapping:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")

    file_path, filename, media_type = mapping[file_type]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not generated: {file_type}")

    return FileResponse(file_path, filename=filename, media_type=media_type)
