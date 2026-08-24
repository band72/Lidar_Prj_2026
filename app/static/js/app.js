/**
 * LiDAR Contour Studio - Linux Explorer, Uploader & Processing Engine
 * Features:
 * - Full Linux Filesystem Explorer with Directories, Files, Search, and Uploader
 * - Automatic system-wide LiDAR point cloud discovery (Project, Downloads, Documents, Home)
 * - Direct point cloud inspection & true WGS84 GPS coordinate resolution
 * - Leaflet map interactive bounding box & real-time contour display
 * - SSE live processing stream & multi-format export center
 */

let map = null;
let baseLayers = {};
let currentBaseLayer = 'satellite';
let fileBoundsLayer = null;
let drawRoiLayer = null;
let contourLayer = null;
let currentMetadata = null;
let currentJobId = null;
let eventSource = null;

// File Browser Modal State
let browserTargetInputId = 'inputFilePathManual';
let browserMode = 'file'; // 'file' or 'folder'
let browserCurrentPath = '';
let browserParentPath = null;
let browserShowHidden = false;
let browserSearchTerm = '';
let browserSearchTimeout = null;
let activeModalTab = 'explorer';

document.addEventListener('DOMContentLoaded', () => {
    initLeafletMap();
    fetchAvailableFiles();
});

/**
 * Initializes the Leaflet map with satellite, OSM, and topo layers.
 */
function initLeafletMap() {
    map = L.map('leafletMap', {
        zoomControl: false,
        attributionControl: false
    }).setView([27.95, -82.45], 11);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    baseLayers.satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19
    });

    baseLayers.osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19
    });

    baseLayers.topo = L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 16
    });

    baseLayers.satellite.addTo(map);

    drawRoiLayer = new L.FeatureGroup();
    map.addLayer(drawRoiLayer);

    map.on(L.Draw.Event.CREATED, function (event) {
        const layer = event.layer;
        drawRoiLayer.clearLayers();
        drawRoiLayer.addLayer(layer);

        const bounds = layer.getBounds();
        document.getElementById('bboxMinLat').value = bounds.getSouth().toFixed(6);
        document.getElementById('bboxMaxLat').value = bounds.getNorth().toFixed(6);
        document.getElementById('bboxMinLon').value = bounds.getWest().toFixed(6);
        document.getElementById('bboxMaxLon').value = bounds.getEast().toFixed(6);

        updateRoiPill(bounds);
    });
}

function setBaseLayer(layerKey) {
    if (baseLayers[currentBaseLayer]) {
        map.removeLayer(baseLayers[currentBaseLayer]);
    }
    if (baseLayers[layerKey]) {
        baseLayers[layerKey].addTo(map);
        currentBaseLayer = layerKey;
    }

    document.getElementById('btnLayerSat').className = layerKey === 'satellite' 
        ? 'px-2.5 py-1 rounded bg-cyan-600 text-white font-medium' 
        : 'px-2.5 py-1 rounded text-slate-300 font-medium';
    document.getElementById('btnLayerOsm').className = layerKey === 'osm' 
        ? 'px-2.5 py-1 rounded bg-cyan-600 text-white font-medium' 
        : 'px-2.5 py-1 rounded text-slate-300 font-medium';
    document.getElementById('btnLayerTopo').className = layerKey === 'topo' 
        ? 'px-2.5 py-1 rounded bg-cyan-600 text-white font-medium' 
        : 'px-2.5 py-1 rounded text-slate-300 font-medium';
}

function startMapDrawBox() {
    switchMobileTab('map');
    const rectDrawer = new L.Draw.Rectangle(map, {
        shapeOptions: {
            color: '#f59e0b',
            weight: 2,
            fillColor: '#f59e0b',
            fillOpacity: 0.15
        }
    });
    rectDrawer.enable();
}

/**
 * Fetches LAS/LAZ files discovered across workspace, Downloads, and Home.
 */
async function fetchAvailableFiles() {
    try {
        const res = await fetch('/api/files');
        const data = await res.json();
        const select = document.getElementById('inputFileSelect');
        select.innerHTML = '';

        const badge = document.getElementById('discoveredCountBadge');
        if (badge) {
            badge.textContent = `${data.files.length} Found`;
        }

        if (!data.files || data.files.length === 0) {
            select.innerHTML = '<option value="">No LAS/LAZ files found on system</option>';
            return;
        }

        const defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = `-- Discovered Point Clouds (${data.files.length} found) --`;
        select.appendChild(defaultOpt);

        data.files.forEach((f) => {
            const opt = document.createElement('option');
            opt.value = f.absolute_path;
            const dirShort = f.directory ? f.directory.split(/[/\\]/).slice(-2).join('/') : '';
            opt.textContent = `${f.name} (${f.size_mb} MB) [${dirShort}]`;
            select.appendChild(opt);
        });

        if (data.files.length > 0) {
            select.selectedIndex = 1;
            onFileSelected(data.files[0].absolute_path);
        }
    } catch (err) {
        console.error("Failed to fetch files:", err);
    }
}

async function onFileSelected(filePath) {
    if (!filePath) return;
    document.getElementById('inputFilePathManual').value = filePath;
    await inspectLidarFile(filePath);
}

async function inspectManualPath() {
    const p = document.getElementById('inputFilePathManual').value.trim();
    if (p) await inspectLidarFile(p);
}

async function inspectLidarFile(filePath) {
    document.getElementById('topFileName').textContent = 'Inspecting ' + filePath.split(/[/\\]/).pop() + '...';
    try {
        const res = await fetch('/api/inspect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filePath })
        });

        if (!res.ok) {
            const err = await res.json();
            alert('Inspection failed: ' + (err.detail || 'Unknown error'));
            return;
        }

        currentMetadata = await res.json();
        renderMetadata(currentMetadata);
    } catch (e) {
        console.error('Inspection error:', e);
        alert('Inspection request failed: ' + e.message);
    }
}

function renderMetadata(meta) {
    document.getElementById('topFileName').textContent = meta.filename;
    document.getElementById('inputFilePathManual').value = meta.file_path;
    document.getElementById('fileMetaBox').classList.remove('hidden');

    document.getElementById('metaTotalPoints').textContent = meta.total_points.toLocaleString() + ' pts';
    document.getElementById('metaCrsName').textContent = meta.crs_name;
    document.getElementById('metaCrsName').title = meta.crs_repr;

    const zMin = meta.z_stats.min.toFixed(1);
    const zMax = meta.z_stats.max.toFixed(1);
    document.getElementById('metaZRange').textContent = `${zMin} to ${zMax} ${meta.units}`;

    document.getElementById('metaDensity').textContent = `${meta.density_m2} pts/m² (${meta.density_sqft} pts/ft²)`;

    const unitsSelect = document.getElementById('unitsSelect');
    if (meta.units === 'm') {
        unitsSelect.value = 'm';
        document.getElementById('contourIntervalUnitLabel').textContent = 'm';
        document.getElementById('cellUnitLabel').textContent = 'm';
        document.getElementById('contourIntervalInput').value = '1.0';
        document.getElementById('cellSizeInput').value = '1.0';
    } else {
        unitsSelect.value = meta.units === 'ft' ? 'ft' : 'ftUS';
        document.getElementById('contourIntervalUnitLabel').textContent = 'ft';
        document.getElementById('cellUnitLabel').textContent = 'ft';
        document.getElementById('contourIntervalInput').value = '2.0';
        document.getElementById('cellSizeInput').value = '2.0';
    }

    if (meta.wgs84_bounds && meta.wgs84_bounds.valid) {
        const w = meta.wgs84_bounds;
        document.getElementById('bboxMinLat').value = w.min_lat.toFixed(6);
        document.getElementById('bboxMaxLat').value = w.max_lat.toFixed(6);
        document.getElementById('bboxMinLon').value = w.min_lon.toFixed(6);
        document.getElementById('bboxMaxLon').value = w.max_lon.toFixed(6);

        if (fileBoundsLayer) map.removeLayer(fileBoundsLayer);

        const latLngBounds = L.latLngBounds(
            [w.min_lat, w.min_lon],
            [w.max_lat, w.max_lon]
        );

        fileBoundsLayer = L.rectangle(latLngBounds, {
            color: '#06b6d4',
            weight: 2,
            dashArray: '5, 5',
            fillColor: '#06b6d4',
            fillOpacity: 0.05
        }).addTo(map);

        map.fitBounds(latLngBounds, { padding: [40, 40] });
        updateRoiPill(latLngBounds);
    }
}

function resetBoundingBoxToFull() {
    if (!currentMetadata || !currentMetadata.wgs84_bounds) return;
    const w = currentMetadata.wgs84_bounds;
    document.getElementById('bboxMinLat').value = w.min_lat.toFixed(6);
    document.getElementById('bboxMaxLat').value = w.max_lat.toFixed(6);
    document.getElementById('bboxMinLon').value = w.min_lon.toFixed(6);
    document.getElementById('bboxMaxLon').value = w.max_lon.toFixed(6);

    drawRoiLayer.clearLayers();
    const latLngBounds = L.latLngBounds(
        [w.min_lat, w.min_lon],
        [w.max_lat, w.max_lon]
    );
    map.fitBounds(latLngBounds, { padding: [40, 40] });
    updateRoiPill(latLngBounds);
}

function updateRoiPill(bounds) {
    const pill = document.getElementById('mapRoiPill');
    pill.classList.remove('hidden');
    const south = bounds.getSouth().toFixed(4);
    const north = bounds.getNorth().toFixed(4);
    const west = bounds.getWest().toFixed(4);
    const east = bounds.getEast().toFixed(4);
    document.getElementById('mapRoiText').textContent = `ROI: [${south}°, ${west}°] to [${north}°, ${east}°]`;
}

function setTimestampOutputFolder() {
    const now = new Date();
    const ts = now.toISOString().replace(/[-:T]/g, '_').slice(0, 15);
    document.getElementById('outputDirPathInput').value = `outputs/run_${ts}`;
}

/**
 * ----------------------------------------------------
 * Complete Linux Explorer, Search & Modal Uploader
 * ----------------------------------------------------
 */
function openFileBrowserModal(targetInputId, mode) {
    browserTargetInputId = targetInputId;
    browserMode = mode; // 'file' or 'folder'
    browserSearchTerm = '';
    document.getElementById('browserSearchInput').value = '';

    const title = mode === 'file' ? 'Linux Filesystem Explorer & Uploader' : 'Select Output Destination Folder';
    const subtitle = mode === 'file' ? 'Browse Linux directories, search files, or upload a point cloud' : 'Navigate or search directories to choose export folder';
    document.getElementById('fileBrowserModalTitle').textContent = title;
    document.getElementById('fileBrowserModalSubtitle').textContent = subtitle;

    const btnSelectFolder = document.getElementById('btnSelectCurrentFolder');
    if (mode === 'folder') {
        btnSelectFolder.classList.remove('hidden');
    } else {
        btnSelectFolder.classList.add('hidden');
    }

    switchBrowserModalTab('explorer');

    const currentVal = document.getElementById(targetInputId).value.trim();
    loadBrowserDirectory(currentVal || '');

    document.getElementById('fileBrowserModal').classList.remove('hidden');
}

function closeFileBrowserModal() {
    document.getElementById('fileBrowserModal').classList.add('hidden');
}

function switchBrowserModalTab(tab) {
    activeModalTab = tab;
    const btnExplorer = document.getElementById('btnTabExplorer');
    const btnDiscovered = document.getElementById('btnTabDiscovered');
    const viewExplorer = document.getElementById('viewExplorerTab');
    const viewDiscovered = document.getElementById('viewDiscoveredTab');
    const pathAndSearchBar = document.getElementById('browserPathAndSearchBar');
    const breadcrumbsBar = document.getElementById('browserBreadcrumbsContainer');

    if (tab === 'explorer') {
        btnExplorer.className = 'px-3 py-1 rounded-md bg-cyan-600 text-white font-semibold flex items-center gap-1.5';
        btnDiscovered.className = 'px-3 py-1 rounded-md text-slate-400 hover:text-white font-semibold flex items-center gap-1.5';
        viewExplorer.classList.remove('hidden');
        viewDiscovered.classList.add('hidden');
        pathAndSearchBar.classList.remove('hidden');
        breadcrumbsBar.classList.remove('hidden');
    } else {
        btnExplorer.className = 'px-3 py-1 rounded-md text-slate-400 hover:text-white font-semibold flex items-center gap-1.5';
        btnDiscovered.className = 'px-3 py-1 rounded-md bg-cyan-600 text-white font-semibold flex items-center gap-1.5';
        viewExplorer.classList.add('hidden');
        viewDiscovered.classList.remove('hidden');
        pathAndSearchBar.classList.add('hidden');
        breadcrumbsBar.classList.add('hidden');
        loadDiscoveredDatasets();
    }
}

async function loadDiscoveredDatasets() {
    const container = document.getElementById('discoveredDatasetsList');
    container.innerHTML = '<div class="text-slate-400 py-8 text-center flex items-center justify-center gap-2"><svg class="w-4 h-4 animate-spin text-cyan-400" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>Scanning system for LAS/LAZ point clouds...</div>';

    try {
        const res = await fetch('/api/files');
        const data = await res.json();
        container.innerHTML = '';

        if (!data.files || data.files.length === 0) {
            container.innerHTML = '<div class="text-slate-500 py-12 text-center font-mono">No LAS or LAZ point cloud files discovered in standard paths.</div>';
            return;
        }

        data.files.forEach(f => {
            const card = document.createElement('div');
            card.className = 'p-3.5 bg-slate-950/80 border border-slate-800 hover:border-cyan-500/70 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all group shadow-sm';
            
            card.innerHTML = `
                <div class="flex items-start gap-3 min-w-0 flex-1">
                    <div class="w-9 h-9 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-0.5">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    </div>
                    <div class="min-w-0">
                        <div class="font-bold font-mono text-slate-100 text-xs sm:text-sm group-hover:text-cyan-300 truncate">${f.name}</div>
                        <div class="text-[11px] text-slate-400 font-mono truncate mt-0.5 flex items-center gap-1.5">
                            <span class="text-amber-400">📁</span>
                            <span class="truncate">${f.directory}</span>
                        </div>
                        <div class="text-[10px] text-slate-500 mt-0.5">Last modified: ${f.modified || 'Unknown'}</div>
                    </div>
                </div>
                <div class="flex items-center gap-3 shrink-0 self-end sm:self-center">
                    <span class="text-xs font-mono px-3 py-1 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold">
                        ${f.size_mb} MB
                    </span>
                    <button class="px-4 py-2 bg-gradient-to-r from-cyan-600 to-emerald-500 hover:from-cyan-500 hover:to-emerald-400 text-white rounded-lg text-xs font-bold shadow-lg shadow-cyan-600/30 transition-all flex items-center gap-1.5">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                        <span>Select & Load</span>
                    </button>
                </div>
            `;

            card.querySelector('button').onclick = () => selectFileInBrowser(f.absolute_path);
            container.appendChild(card);
        });

    } catch (e) {
        container.innerHTML = `<div class="text-red-400 py-6 text-center">Error scanning files: ${e.message}</div>`;
    }
}

async function loadBrowserDirectory(path) {
    const listEl = document.getElementById('browserItemList');
    listEl.innerHTML = '<div class="text-slate-400 py-12 text-center flex items-center justify-center gap-2"><svg class="w-4 h-4 animate-spin text-cyan-400" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>Loading filesystem contents...</div>';

    try {
        const queryParams = new URLSearchParams({
            mode: browserMode === 'folder' ? 'folder' : 'all',
            path: path || '',
            show_hidden: browserShowHidden,
            search: browserSearchTerm
        });

        const res = await fetch(`/api/browse?` + queryParams.toString());
        if (!res.ok) throw new Error('Failed to load directory');
        
        const data = await res.json();
        browserCurrentPath = data.current_path;
        browserParentPath = data.parent_path;

        document.getElementById('browserPathBarInput').value = data.current_path;
        document.getElementById('btnBrowserUp').disabled = !data.parent_path;

        renderBreadcrumbs(data.breadcrumbs);
        renderQuickLocations(data.quick_locations);
        renderBrowserList(data);

        const dirCount = data.directories.length;
        const fileCount = data.files.length;
        document.getElementById('browserStatusBar').textContent = `${dirCount} folders, ${fileCount} files in ${data.current_path}`;

    } catch (e) {
        listEl.innerHTML = `<div class="text-red-400 py-6 text-center">Error reading directory: ${e.message}</div>`;
    }
}

function renderBreadcrumbs(breadcrumbs) {
    const container = document.getElementById('browserBreadcrumbsContainer');
    container.innerHTML = '';

    if (!breadcrumbs || breadcrumbs.length === 0) return;

    breadcrumbs.forEach((b, idx) => {
        const chip = document.createElement('button');
        chip.className = 'px-1.5 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-cyan-400 transition-colors shrink-0 truncate max-w-[130px] font-medium';
        chip.textContent = b.name;
        chip.title = b.path;
        chip.onclick = () => loadBrowserDirectory(b.path);
        container.appendChild(chip);

        if (idx < breadcrumbs.length - 1) {
            const sep = document.createElement('span');
            sep.className = 'text-slate-600';
            sep.textContent = '/';
            container.appendChild(sep);
        }
    });

    container.scrollLeft = container.scrollWidth;
}

function renderQuickLocations(locations) {
    const container = document.getElementById('browserQuickLocationsList');
    container.innerHTML = '';

    if (!locations) return;

    locations.forEach(loc => {
        const btn = document.createElement('button');
        const isActive = loc.path === browserCurrentPath;
        btn.className = `w-full text-left px-2.5 py-2 rounded-lg flex items-center gap-2 transition-all ${
            isActive ? 'bg-cyan-600/30 text-cyan-300 font-semibold border border-cyan-500/40' : 'text-slate-400 hover:bg-slate-800/80 hover:text-slate-200'
        }`;
        btn.onclick = () => loadBrowserDirectory(loc.path);

        btn.innerHTML = `
            <svg class="w-4 h-4 text-cyan-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg>
            <span class="truncate">${loc.name}</span>
        `;
        container.appendChild(btn);
    });
}

function renderBrowserList(data) {
    const listEl = document.getElementById('browserItemList');
    listEl.innerHTML = '';

    if (data.directories.length === 0 && data.files.length === 0) {
        listEl.innerHTML = `
            <div class="text-center py-12 space-y-3">
                <div class="text-slate-500 font-mono">No matching files or folders found in this directory.</div>
                <button onclick="switchBrowserModalTab('discovered')" class="px-3.5 py-1.5 bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 border border-cyan-500/40 rounded-lg text-xs font-semibold">
                    View Discovered LiDAR Files on System &rarr;
                </button>
            </div>
        `;
        return;
    }

    // 1. DIRECTORIES SECTION
    if (data.directories.length > 0) {
        const dirHeader = document.createElement('div');
        dirHeader.className = 'text-[11px] font-bold text-slate-400 uppercase tracking-wider px-1 pt-1 pb-0.5 flex items-center gap-1.5';
        dirHeader.innerHTML = `
            <svg class="w-3.5 h-3.5 text-amber-400" fill="currentColor" viewBox="0 0 20 20"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"></path></svg>
            <span>Directories (${data.directories.length})</span>
        `;
        listEl.appendChild(dirHeader);

        data.directories.forEach(d => {
            const row = document.createElement('div');
            row.className = 'flex items-center justify-between p-2.5 hover:bg-slate-800 rounded-xl cursor-pointer transition-all border border-slate-800/80 hover:border-slate-700 group';

            const leftDiv = document.createElement('div');
            leftDiv.className = 'flex items-center gap-3 min-w-0 flex-1';
            leftDiv.onclick = () => loadBrowserDirectory(d.path);
            leftDiv.innerHTML = `
                <div class="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"></path></svg>
                </div>
                <div class="min-w-0">
                    <div class="font-medium text-slate-200 group-hover:text-cyan-300 truncate">${d.name}</div>
                    <div class="text-[10px] text-slate-500">${d.child_count} items • Modified: ${d.modified}</div>
                </div>
            `;
            row.appendChild(leftDiv);

            const rightDiv = document.createElement('div');
            rightDiv.className = 'flex items-center gap-2 shrink-0';

            if (browserMode === 'folder') {
                const selectBtn = document.createElement('button');
                selectBtn.className = 'px-3 py-1 bg-cyan-600/30 hover:bg-cyan-600 text-cyan-300 hover:text-white rounded-md text-xs font-semibold border border-cyan-500/40 transition-colors';
                selectBtn.textContent = 'Select Folder';
                selectBtn.onclick = (e) => {
                    e.stopPropagation();
                    selectFolderInBrowser(d.path);
                };
                rightDiv.appendChild(selectBtn);
            }

            const openBtn = document.createElement('button');
            openBtn.className = 'px-2 py-1 text-slate-400 group-hover:text-cyan-300 text-xs font-mono';
            openBtn.textContent = 'Open →';
            openBtn.onclick = () => loadBrowserDirectory(d.path);
            rightDiv.appendChild(openBtn);

            row.appendChild(rightDiv);
            listEl.appendChild(row);
        });
    }

    // 2. FILES SECTION
    if (browserMode !== 'folder' && data.files.length > 0) {
        const fileHeader = document.createElement('div');
        fileHeader.className = 'text-[11px] font-bold text-slate-400 uppercase tracking-wider px-1 pt-3 pb-0.5 flex items-center gap-1.5';
        fileHeader.innerHTML = `
            <svg class="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
            <span>Point Cloud Datasets & Files (${data.files.length})</span>
        `;
        listEl.appendChild(fileHeader);

        data.files.forEach(f => {
            const isLidar = f.is_lidar;
            const row = document.createElement('div');
            row.className = `flex items-center justify-between p-2.5 rounded-xl cursor-pointer transition-all border ${
                isLidar 
                    ? 'bg-slate-950/70 hover:bg-cyan-950/40 border-cyan-800/40 hover:border-cyan-500/70 shadow-sm' 
                    : 'bg-slate-950/40 hover:bg-slate-800/50 border-slate-800/60'
            } group`;

            if (isLidar) {
                row.onclick = () => selectFileInBrowser(f.path);
            }

            row.innerHTML = `
                <div class="flex items-center gap-3 min-w-0 flex-1">
                    <div class="w-8 h-8 rounded-lg ${isLidar ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' : 'bg-slate-800 text-slate-400'} flex items-center justify-center shrink-0">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    </div>
                    <div class="min-w-0">
                        <div class="font-mono ${isLidar ? 'text-slate-100 font-semibold group-hover:text-cyan-300' : 'text-slate-400'} truncate">${f.name}</div>
                        <div class="text-[10px] text-slate-500">Modified: ${f.modified}</div>
                    </div>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                    <span class="text-[10px] font-mono px-2.5 py-1 rounded-md ${isLidar ? 'bg-cyan-900/50 text-cyan-300 border border-cyan-700/60' : 'bg-slate-800 text-slate-400'} font-bold">
                        ${f.size_mb} MB
                    </span>
                    ${isLidar ? `
                        <button class="px-3.5 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded-md text-xs font-bold shadow-md shadow-cyan-600/30 transition-all">
                            Select File
                        </button>
                    ` : ''}
                </div>
            `;
            listEl.appendChild(row);
        });
    }
}

function onBrowserSearchInput(val) {
    browserSearchTerm = val.trim();
    if (browserSearchTimeout) clearTimeout(browserSearchTimeout);
    browserSearchTimeout = setTimeout(() => {
        loadBrowserDirectory(browserCurrentPath);
    }, 200);
}

function toggleBrowserHiddenFiles(show) {
    browserShowHidden = show;
    loadBrowserDirectory(browserCurrentPath);
}

function navigateBrowserUp() {
    if (browserParentPath) {
        loadBrowserDirectory(browserParentPath);
    }
}

function selectFileInBrowser(filePath) {
    document.getElementById(browserTargetInputId).value = filePath;
    closeFileBrowserModal();
    if (browserTargetInputId === 'inputFilePathManual') {
        inspectLidarFile(filePath);
    }
}

function selectFolderInBrowser(folderPath) {
    document.getElementById(browserTargetInputId).value = folderPath;
    closeFileBrowserModal();
}

function confirmFolderSelection() {
    if (browserCurrentPath) {
        document.getElementById(browserTargetInputId).value = browserCurrentPath;
    }
    closeFileBrowserModal();
}

/**
 * ----------------------------------------------------
 * Modal Integrated File Uploader
 * ----------------------------------------------------
 */
function handleModalFileUpload(files) {
    if (!files || files.length === 0) return;
    const file = files[0];

    const banner = document.getElementById('modalUploadProgressBanner');
    const textEl = document.getElementById('modalUploadProgressText');
    const barEl = document.getElementById('modalUploadProgressBar');

    banner.classList.remove('hidden');
    textEl.textContent = `Uploading ${file.name} (0%)...`;
    barEl.style.width = '0%';

    const formData = new FormData();
    formData.append('file', file);

    const targetDirParam = encodeURIComponent(browserCurrentPath || '');
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/upload?target_dir=${targetDirParam}`, true);

    xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            textEl.textContent = `Uploading ${file.name} (${pct}%)...`;
            barEl.style.width = `${pct}%`;
        }
    };

    xhr.onload = async function () {
        banner.classList.add('hidden');
        if (xhr.status >= 200 && xhr.status < 300) {
            try {
                const data = JSON.parse(xhr.responseText);
                await loadBrowserDirectory(browserCurrentPath);
                selectFileInBrowser(data.path);
                await fetchAvailableFiles();
            } catch (err) {
                alert('Upload successful but parsing failed: ' + err.message);
            }
        } else {
            try {
                const err = JSON.parse(xhr.responseText);
                alert('Upload failed: ' + (err.detail || 'Server error'));
            } catch {
                alert('Upload failed with status code: ' + xhr.status);
            }
        }
    };

    xhr.onerror = function () {
        banner.classList.add('hidden');
        alert('Network error during upload.');
    };

    xhr.send(formData);
}

function handleDeviceFileUpload(files) {
    handleModalFileUpload(files);
}

async function promptCreateNewFolder() {
    const name = prompt("Enter new folder name:");
    if (!name || !name.trim()) return;

    try {
        const res = await fetch('/api/create-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parent_path: browserCurrentPath, folder_name: name.trim() })
        });
        if (!res.ok) {
            const err = await res.json();
            alert("Failed to create folder: " + (err.detail || "Error"));
            return;
        }
        loadBrowserDirectory(browserCurrentPath);
    } catch (e) {
        alert("Error creating folder: " + e.message);
    }
}

async function openSystemFolderInExplorer() {
    const outPath = document.getElementById('outputDirPathInput').value.trim() || 'outputs';
    try {
        const res = await fetch('/api/open-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: outPath })
        });
        if (res.ok) {
            console.log("Opened folder in system file manager.");
        }
    } catch (e) {
        console.error("Could not open system file manager:", e);
    }
}

/**
 * ----------------------------------------------------
 * Processing Pipeline Execution
 * ----------------------------------------------------
 */
async function startLiDARProcessing() {
    const filePath = document.getElementById('inputFilePathManual').value.trim();
    if (!filePath) {
        alert('Please select or specify a valid LAS/LAZ point cloud file.');
        return;
    }

    const outputDir = document.getElementById('outputDirPathInput').value.trim();
    const units = document.getElementById('unitsSelect').value;
    const contourInterval = parseFloat(document.getElementById('contourIntervalInput').value) || 2.0;
    const indexMultiplier = parseInt(document.getElementById('indexMultiplierSelect').value) || 5;
    const cellSize = parseFloat(document.getElementById('cellSizeInput').value) || 2.0;
    const outlierRemoval = document.getElementById('chkOutlierRemoval').checked;

    const selectedClasses = [];
    if (document.getElementById('clsGround').checked) selectedClasses.push(2);
    if (document.getElementById('clsKeypoint').checked) selectedClasses.push(8);
    if (document.getElementById('clsUnclassified').checked) selectedClasses.push(1);
    if (document.getElementById('clsWater').checked) selectedClasses.push(9);

    let bbox = null;
    const minLat = parseFloat(document.getElementById('bboxMinLat').value);
    const maxLat = parseFloat(document.getElementById('bboxMaxLat').value);
    const minLon = parseFloat(document.getElementById('bboxMinLon').value);
    const maxLon = parseFloat(document.getElementById('bboxMaxLon').value);

    if (!isNaN(minLat) && !isNaN(maxLat) && !isNaN(minLon) && !isNaN(maxLon)) {
        bbox = { min_lat: minLat, max_lat: maxLat, min_lon: minLon, max_lon: maxLon };
    }

    const elevMinVal = document.getElementById('elevMinInput').value.trim();
    const elevMaxVal = document.getElementById('elevMaxInput').value.trim();
    const elevMin = elevMinVal !== '' ? parseFloat(elevMinVal) : null;
    const elevMax = elevMaxVal !== '' ? parseFloat(elevMaxVal) : null;

    const payload = {
        file_path: filePath,
        output_dir: outputDir || null,
        units: units,
        contour_interval: contourInterval,
        index_multiplier: indexMultiplier,
        bounding_box_latlon: bbox,
        elevation_min: elevMin,
        elevation_max: elevMax,
        selected_classes: selectedClasses.length > 0 ? selectedClasses : null,
        cell_size: cellSize,
        outlier_removal: outlierRemoval
    };

    document.getElementById('progressContainer').classList.remove('hidden');
    document.getElementById('progressBarFill').style.width = '5%';
    document.getElementById('progressPercentage').textContent = '5%';
    document.getElementById('progressStatusText').innerHTML = `
        <svg class="w-3.5 h-3.5 animate-spin text-cyan-400" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
        Launching LiDAR pipeline...
    `;
    const consoleBox = document.getElementById('progressLogConsole');
    consoleBox.innerHTML = '<div>[0%] Pipeline initialized.</div>';

    const btn = document.getElementById('btnStartProcess');
    btn.disabled = true;
    btn.classList.add('opacity-75', 'processing-active');

    try {
        const res = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Processing request failed');
        }

        const data = await res.json();
        currentJobId = data.job_id;
        listenToProgress(currentJobId);

    } catch (e) {
        alert('Error: ' + e.message);
        btn.disabled = false;
        btn.classList.remove('opacity-75', 'processing-active');
    }
}

function listenToProgress(jobId) {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(`/api/progress/${jobId}`);

    eventSource.onmessage = function (e) {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'progress') {
                const pct = Math.round(data.progress);
                document.getElementById('progressBarFill').style.width = `${pct}%`;
                document.getElementById('progressPercentage').textContent = `${pct}%`;
                document.getElementById('progressStatusText').textContent = data.message;
                
                const consoleBox = document.getElementById('progressLogConsole');
                const logLine = document.createElement('div');
                logLine.textContent = `[${pct}%] ${data.message}`;
                consoleBox.appendChild(logLine);
                consoleBox.scrollTop = consoleBox.scrollHeight;
            } else if (data.type === 'log') {
                const consoleBox = document.getElementById('progressLogConsole');
                const logLine = document.createElement('div');
                logLine.textContent = data.message;
                consoleBox.appendChild(logLine);
                consoleBox.scrollTop = consoleBox.scrollHeight;
            } else if (data.type === 'completed') {
                eventSource.close();
                onProcessingComplete(data.results);
            } else if (data.type === 'error') {
                eventSource.close();
                alert('Processing Error: ' + data.error);
                const btn = document.getElementById('btnStartProcess');
                btn.disabled = false;
                btn.classList.remove('opacity-75', 'processing-active');
            }
        } catch (err) {
            console.error('SSE parse error:', err);
        }
    };

    eventSource.onerror = function () {
        console.warn('SSE stream closed or interrupted.');
    };
}

async function onProcessingComplete(results) {
    const btn = document.getElementById('btnStartProcess');
    btn.disabled = false;
    btn.classList.remove('opacity-75', 'processing-active');

    document.getElementById('progressBarFill').style.width = '100%';
    document.getElementById('progressPercentage').textContent = '100%';
    document.getElementById('progressStatusText').innerHTML = `
        <span class="text-emerald-400 font-bold flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
            Contours Generated (${results.contour_meta.total_contours.toLocaleString()} lines)
        </span>
    `;

    await loadContourGeoJson(results.job_id);
    setupDownloadLinks(results.job_id);

    document.getElementById('mapLegendCard').classList.remove('hidden');
    document.getElementById('legendUnitLabel').textContent = results.dem_meta.units;

    if (window.innerWidth < 768) {
        switchMobileTab('map');
    }
}

async function loadContourGeoJson(jobId) {
    if (contourLayer) map.removeLayer(contourLayer);

    try {
        const res = await fetch(`/api/contours-geojson/${jobId}`);
        const geojson = await res.json();

        contourLayer = L.geoJSON(geojson, {
            style: function (feature) {
                const isIndex = feature.properties.is_index;
                return {
                    color: isIndex ? '#f59e0b' : '#38bdf8',
                    weight: isIndex ? 2.5 : 1.2,
                    opacity: isIndex ? 0.95 : 0.75
                };
            },
            onEachFeature: function (feature, layer) {
                const elev = feature.properties.elevation;
                const type = feature.properties.type;
                const isIndex = feature.properties.is_index;
                const units = document.getElementById('unitsSelect').value;

                layer.bindTooltip(`${elev} ${units} (${type})`, {
                    sticky: true,
                    className: isIndex ? 'contour-tooltip index-contour-tooltip' : 'contour-tooltip'
                });

                layer.bindPopup(`
                    <div class="font-sans text-xs space-y-1 p-1">
                        <div class="font-bold text-cyan-400 text-sm">${elev} ${units}</div>
                        <div class="text-slate-300">Contour Type: <span class="capitalize font-semibold">${type}</span></div>
                    </div>
                `);
            }
        }).addTo(map);

        if (contourLayer.getBounds().isValid()) {
            map.fitBounds(contourLayer.getBounds(), { padding: [30, 30] });
        }
    } catch (err) {
        console.error('Failed to load contour GeoJSON:', err);
    }
}

function toggleContourLayer(visible) {
    if (!contourLayer) return;
    if (visible) {
        map.addLayer(contourLayer);
    } else {
        map.removeLayer(contourLayer);
    }
}

function setupDownloadLinks(jobId) {
    document.getElementById('btnDlShp').href = `/api/download/${jobId}/shapefile`;
    document.getElementById('btnDlDxf').href = `/api/download/${jobId}/dxf`;
    document.getElementById('btnDlGeojson').href = `/api/download/${jobId}/geojson`;
    document.getElementById('btnDlDem').href = `/api/download/${jobId}/dem`;
    document.getElementById('btnDlReport').href = `/api/download/${jobId}/report_html`;

    document.getElementById('reportIframe').src = `/api/download/${jobId}/report_html`;
}

function openDownloadsModal() {
    if (!currentJobId) {
        alert('Please run contour processing first to generate deliverables.');
        return;
    }
    document.getElementById('downloadsModal').classList.remove('hidden');
}

function closeDownloadsModal() {
    document.getElementById('downloadsModal').classList.add('hidden');
}

function openReportModal() {
    if (!currentJobId) {
        alert('Please run contour processing first to generate the engineering report.');
        return;
    }
    document.getElementById('reportModal').classList.remove('hidden');
}

function closeReportModal() {
    document.getElementById('reportModal').classList.add('hidden');
}

function printReportIframe() {
    const iframe = document.getElementById('reportIframe');
    if (iframe && iframe.contentWindow) {
        iframe.contentWindow.print();
    }
}

function switchMobileTab(tab) {
    const sidebar = document.getElementById('sidebarPanel');
    const mapEl = document.getElementById('mapContainer');
    const btnSettings = document.getElementById('tabBtnSettings');
    const btnMap = document.getElementById('tabBtnMap');
    const btnReport = document.getElementById('tabBtnReport');

    btnSettings.className = 'px-3 py-1 rounded-md text-slate-300 font-medium';
    btnMap.className = 'px-3 py-1 rounded-md text-slate-300 font-medium';
    btnReport.className = 'px-3 py-1 rounded-md text-slate-300 font-medium';

    if (tab === 'settings') {
        sidebar.classList.remove('hidden');
        mapEl.classList.add('hidden');
        btnSettings.className = 'px-3 py-1 rounded-md bg-cyan-600 text-white font-medium';
    } else if (tab === 'map') {
        sidebar.classList.add('hidden');
        mapEl.classList.remove('hidden');
        btnMap.className = 'px-3 py-1 rounded-md bg-cyan-600 text-white font-medium';
        setTimeout(() => { if (map) map.invalidateSize(); }, 200);
    } else if (tab === 'report') {
        btnReport.className = 'px-3 py-1 rounded-md bg-cyan-600 text-white font-medium';
        openReportModal();
    }
}
