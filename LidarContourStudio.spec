# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Collect heavy geospatial data packages (PROJ, GDAL, lazrs)
datas = [
    ('app/templates', 'app/templates'),
    ('app/static', 'app/static'),
]

binaries = []
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'laspy',
    'laspy.compression',
    'lazrs',
    'pyproj',
    'shapely',
    'osgeo',
    'osgeo.gdal',
    'osgeo.osr',
    'osgeo.ogr',
    'scipy',
    'scipy.interpolate',
    'jinja2',
]

# Collect pyproj and osgeo data trees
for pkg in ['pyproj', 'osgeo', 'laspy', 'lazrs']:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception as e:
        print(f"Notice: collect_all({pkg}): {e}")

excludes = [
    'torch',
    'torchvision',
    'torchaudio',
    'tensorflow',
    'tensorboard',
    'matplotlib',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'tkinter',
]

a = Analysis(
    ['packaging/option_1_desktop_app/desktop_launcher.py'],
    pathex=[os.getcwd()],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LidarContourStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LidarContourStudio',
)
