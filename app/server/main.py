"""
FastAPI Server Entrypoint for LiDAR Contour Studio
Cross-Platform Desktop, Tablet, and Mobile Application Server.
"""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.server.routes import router

app = FastAPI(
    title="LiDAR Contour Studio",
    description="Cross-Platform LiDAR Point Cloud Processing, DEM Gridding, Contour Extraction, and Engineering Reporting Engine",
    version="1.0.0"
)

# Enable CORS for tablet and mobile cross-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

app.include_router(router)


@app.get("/")
async def root_view(request: Request):
    """Renders the main touch-responsive application interface."""
    return templates.TemplateResponse(request=request, name="index.html")
