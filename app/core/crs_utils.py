"""
LiDAR Coordinate Reference System (CRS) and Georeferencing Utilities
Supports EPSG lookups, WKT parsing, unit conversions, and WGS84 Lat/Lon bounding transformations.
"""

from typing import Dict, Any, Tuple, Optional, List
import math
import pyproj
from pyproj import CRS, Transformer


UNIT_CONVERSIONS = {
    "meters": 1.0,
    "m": 1.0,
    "us_survey_feet": 0.3048006096012192,
    "ftus": 0.3048006096012192,
    "ft_us": 0.3048006096012192,
    "international_feet": 0.3048,
    "ft": 0.3048,
    "feet": 0.3048,
}


def parse_crs_from_header(header) -> Tuple[Optional[CRS], str, str]:
    """
    Extracts pyproj CRS from a laspy header.
    Returns: (crs_obj, crs_name, epsg_code_or_wkt)
    """
    crs_obj = None
    crs_name = "Unknown CRS"
    crs_repr = "UNKNOWN"

    try:
        raw_crs = header.parse_crs()
        if raw_crs:
            crs_obj = raw_crs
            crs_name = crs_obj.name or "Projected Coordinate System"
            epsg = crs_obj.to_epsg()
            if epsg:
                crs_repr = f"EPSG:{epsg}"
            else:
                crs_repr = crs_obj.to_wkt()
    except Exception:
        # Fallback to VLR search if parse_crs fails
        try:
            for vlr in getattr(header, "vlrs", []):
                desc = getattr(vlr, "description", "").lower()
                rec_id = getattr(vlr, "record_id", 0)
                if "wkt" in desc or rec_id in (2112, 34735):
                    raw_wkt = getattr(vlr, "string", None) or getattr(vlr, "record_data", b"").decode('latin-1', errors='ignore')
                    if "PROJCS" in raw_wkt or "GEOGCS" in raw_wkt or "COMPD_CS" in raw_wkt:
                        crs_obj = CRS.from_wkt(raw_wkt)
                        crs_name = crs_obj.name or "Custom Coordinate System"
                        epsg = crs_obj.to_epsg()
                        crs_repr = f"EPSG:{epsg}" if epsg else raw_wkt[:100]
                        break
        except Exception:
            pass

    return crs_obj, crs_name, crs_repr


def detect_linear_units(crs: Optional[CRS]) -> str:
    """
    Determines linear units from CRS definition.
    Returns 'ftUS', 'ft', or 'm'.
    """
    if not crs:
        return "m"
    
    crs_str = str(crs).lower() + " " + (crs.to_wkt().lower() if hasattr(crs, "to_wkt") else "")
    if "us survey foot" in crs_str or "survey_foot" in crs_str or "ftus" in crs_str or "us survey feet" in crs_str:
        return "ftUS"
    elif "foot" in crs_str or "feet" in crs_str or "ft" in crs_str:
        return "ft"
    return "m"


def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    """Converts a scalar or dimension between linear units."""
    f = from_unit.lower()
    t = to_unit.lower()
    
    f_factor = UNIT_CONVERSIONS.get(f, 1.0)
    t_factor = UNIT_CONVERSIONS.get(t, 1.0)
    
    meters = value * f_factor
    return meters / t_factor


def get_wgs84_bounds(
    min_x: float, min_y: float, max_x: float, max_y: float, crs: Optional[CRS]
) -> Dict[str, float]:
    """
    Transforms native projected coordinates (X, Y) to WGS84 GPS (Lat, Lon).
    Returns dict with min_lat, max_lat, min_lon, max_lon.
    """
    if not crs:
        return {
            "min_lat": 0.0,
            "max_lat": 0.0,
            "min_lon": 0.0,
            "max_lon": 0.0,
            "valid": False
        }
    
    try:
        # Create transformer from CRS to WGS84 (EPSG:4326)
        transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        
        corners = [
            (min_x, min_y),
            (min_x, max_y),
            (max_x, min_y),
            (max_x, max_y)
        ]
        
        lons = []
        lats = []
        for x, y in corners:
            lon, lat = transformer.transform(x, y)
            if not math.isnan(lon) and not math.isnan(lat) and not math.isinf(lon) and not math.isinf(lat):
                lons.append(lon)
                lats.append(lat)
        
        if not lons or not lats:
            return {"min_lat": 0.0, "max_lat": 0.0, "min_lon": 0.0, "max_lon": 0.0, "valid": False}
        
        return {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
            "center_lat": (min(lats) + max(lats)) / 2.0,
            "center_lon": (min(lons) + max(lons)) / 2.0,
            "valid": True
        }
    except Exception as e:
        return {"min_lat": 0.0, "max_lat": 0.0, "min_lon": 0.0, "max_lon": 0.0, "valid": False, "error": str(e)}


def transform_latlon_bbox_to_native(
    min_lat: float, min_lon: float, max_lat: float, max_lon: float, crs: Optional[CRS]
) -> Tuple[float, float, float, float]:
    """
    Transforms WGS84 Lat/Lon bounding box into the native projected CRS coordinates.
    Returns (min_x, min_y, max_x, max_y).
    """
    if not crs:
        return min_lon, min_lat, max_lon, max_lat
    
    try:
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        
        corners = [
            (min_lon, min_lat),
            (min_lon, max_lat),
            (max_lon, min_lat),
            (max_lon, max_lat)
        ]
        
        xs = []
        ys = []
        for lon, lat in corners:
            x, y = transformer.transform(lon, lat)
            xs.append(x)
            ys.append(y)
            
        return min(xs), min(ys), max(xs), max(ys)
    except Exception as e:
        raise ValueError(f"Failed to project Lat/Lon bounds to native CRS: {e}")
