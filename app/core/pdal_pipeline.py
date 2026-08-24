"""
PDAL Pipeline Generator and Executor
Generates standard PDAL JSON pipelines for cropping, range filtering, ground classification (SMRF),
outlier removal, and GDAL DEM/TIN creation.
"""

import json
import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional


class PDALPipelineBuilder:
    def __init__(self, input_path: str, output_dem_path: Optional[str] = None):
        self.input_path = input_path
        self.output_dem_path = output_dem_path
        self.stages: List[Dict[str, Any]] = []
        
        # Add reader
        self.stages.append({
            "type": "readers.las",
            "filename": self.input_path
        })

    def add_crop_box(self, min_x: float, min_y: float, max_x: float, max_y: float, min_z: Optional[float] = None, max_z: Optional[float] = None):
        """Adds a 2D or 3D bounding box crop filter."""
        z_part = ""
        if min_z is not None and max_z is not None:
            z_part = f",[{min_z},{max_z}]"
            
        bounds_str = f"([{min_x},{max_x}],[{min_y},{max_y}]{z_part})"
        self.stages.append({
            "type": "filters.crop",
            "bounds": bounds_str
        })
        return self

    def add_elevation_filter(self, min_z: Optional[float] = None, max_z: Optional[float] = None):
        """Filters points by elevation range (Z cutoff)."""
        if min_z is not None and max_z is not None:
            range_str = f"Z[{min_z}:{max_z}]"
        elif min_z is not None:
            range_str = f"Z[{min_z}:]"
        elif max_z is not None:
            range_str = f"Z[:{max_z}]"
        else:
            return self

        self.stages.append({
            "type": "filters.range",
            "limits": range_str
        })
        return self

    def add_classification_filter(self, classes: List[int]):
        """Filters points by ASPRS classification codes (e.g. [2] for ground)."""
        if not classes:
            return self
            
        range_terms = [f"Classification[{c}:{c}]" for c in classes]
        self.stages.append({
            "type": "filters.range",
            "limits": ",".join(range_terms)
        })
        return self

    def add_outlier_removal(self, method: str = "statistical", mean_k: int = 8, multiplier: float = 2.0):
        """Adds statistical outlier removal (SOR) filter."""
        self.stages.append({
            "type": "filters.outlier",
            "method": method,
            "mean_k": mean_k,
            "multiplier": multiplier
        })
        return self

    def add_smrf_ground_filter(self, cell_size: float = 1.0, slope: float = 0.15, threshold: float = 0.5, window: float = 18.0):
        """Simple Morphological Filter (SMRF) to classify unclassified point clouds into ground."""
        self.stages.append({
            "type": "filters.smrf",
            "cell": cell_size,
            "slope": slope,
            "threshold": threshold,
            "window": window,
            "returns": "last,only"
        })
        return self

    def add_voxel_grid_downsample(self, cell_size: float = 1.0):
        """Downsamples points using a 3D voxel grid centroid filter."""
        self.stages.append({
            "type": "filters.voxelgrid",
            "cell": cell_size
        })
        return self

    def add_gdal_dem_writer(self, output_path: str, resolution: float = 1.0, radius: float = 2.0, output_type: str = "idw", data_type: str = "float32"):
        """Adds GDAL writer stage to create a DEM raster GeoTIFF."""
        self.output_dem_path = output_path
        self.stages.append({
            "type": "writers.gdal",
            "filename": output_path,
            "resolution": resolution,
            "radius": radius,
            "output_type": output_type,
            "data_type": data_type,
            "nodata": -9999.0
        })
        return self

    def build_json(self) -> str:
        """Returns JSON pipeline representation."""
        return json.dumps(self.stages, indent=2)

    def save_pipeline(self, output_json_path: str) -> str:
        """Saves pipeline JSON to file."""
        with open(output_json_path, "w") as f:
            f.write(self.build_json())
        return output_json_path

    @staticmethod
    def is_pdal_cli_available() -> bool:
        """Checks if pdal CLI binary is available on the system PATH."""
        return shutil.which("pdal") is not None

    def execute_cli(self, pipeline_json_path: Optional[str] = None) -> bool:
        """Executes the pipeline using pdal CLI if available."""
        if not self.is_pdal_cli_available():
            raise RuntimeError("PDAL CLI is not installed on system PATH.")
            
        if not pipeline_json_path:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
                tf.write(self.build_json())
                pipeline_json_path = tf.name

        cmd = ["pdal", "pipeline", pipeline_json_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"PDAL pipeline execution failed: {result.stderr}")
        return True
