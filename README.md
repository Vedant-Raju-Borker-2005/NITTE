# 🔥 IGNISIA — Satellite Methane Detection Platform

<p align="center">
  <strong>AI-powered methane leak detection using real satellite imagery, physics-informed quantification, and graph-based attribution.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-0.111-green?style=flat-square&logo=fastapi" />
  <img src="https://img.shields.io/badge/React-18.3-61DAFB?style=flat-square&logo=react" />
  <img src="https://img.shields.io/badge/Three.js-0.168-black?style=flat-square&logo=three.js" />
  <img src="https://img.shields.io/badge/Sentinel--2-L2A-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/EMIT-Hyperspectral-purple?style=flat-square" />
</p>

---

## 📖 Table of Contents

1. [What is IGNISIA?](#-what-is-ignisia)
2. [Key Features](#-key-features)
3. [Project Architecture](#-project-architecture)
4. [Directory Structure](#-directory-structure)
5. [How It Works — The AI Pipeline](#-how-it-works--the-ai-pipeline)
6. [Scientific Methods](#-scientific-methods)
7. [Prerequisites](#-prerequisites)
8. [Quick Start — Backend](#-quick-start--backend)
9. [Quick Start — Frontend (Live UI)](#-quick-start--frontend-live-ui)
10. [Quick Start — React Frontend (Advanced)](#-quick-start--react-frontend-advanced)
11. [Running with Docker](#-running-with-docker)
12. [API Reference](#-api-reference)
13. [Severity Classification](#-severity-classification)
14. [Configuration](#%EF%B8%8F-configuration)
15. [Troubleshooting](#-troubleshooting)

---

## 🌍 What is IGNISIA?

**IGNISIA** is a full-stack, AI-powered platform for detecting, quantifying, and attributing **methane (CH₄) emissions** from industrial facilities worldwide — using real satellite imagery from the **Sentinel-2 L2A** and **NASA EMIT** missions.

Methane is responsible for ~30% of current global warming. Industrial super-emitters (oil refineries, gas plants, landfills, coal mines, petrochemical hubs) leak enormous quantities of methane continuously. Traditional detection requires expensive ground teams or aircraft surveys. **IGNISIA automates this with satellites + AI**, enabling:

- ✅ Real-time detection of methane plumes from space
- ✅ Physics-based quantification of emission rate (kg/hr)
- ✅ Graph-based attribution to the most likely source facility
- ✅ Financial impact calculation (USD cost per hour)
- ✅ CO₂-equivalent climate impact reporting
- ✅ Time-series trend analysis per facility

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🛰 **Live Satellite Imagery** | Pulls real Sentinel-2 L2A multispectral data via Sentinel Hub; falls back to NASA EMIT hyperspectral when available |
| 🧠 **UNet Neural Network** | Deep learning segmentation model trained on methane plume signatures |
| 🌈 **SWIR Spectral Analysis** | Uses Short-Wave Infrared bands (B11/B12) — methane's unique spectral fingerprint |
| 📐 **Physics Quantification** | Pasquill-Gifford Gaussian dispersion model + IME (Integrated Mass Enhancement) |
| 🕸 **Graph Attribution** | Wind-aware graph scoring identifies the most likely emission source facility |
| 🚨 **Severity Alerts** | CRITICAL / HIGH / MODERATE / LOW classification with recommended actions |
| 💰 **Financial Impact** | Real-time cost calculation based on market gas prices |
| 🏭 **Facility Database** | Pre-loaded database of Indian industrial facilities with emission history |
| 🌐 **3D Globe & Map** | Interactive rotating globe and 2D detection map (React frontend) |
| 🐳 **Docker Ready** | Full Docker Compose orchestration for one-command deployment |

---

## 🏗 Project Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    User / Browser                            │
│         live.html  ──OR──  React SPA (port 3000)            │
└────────────────────────┬─────────────────────────────────────┘
                         │  HTTP REST API
                         ▼
┌──────────────────────────────────────────────────────────────┐
│            FastAPI Backend  (server/)  :8000                 │
│   /predict/live  /geocode  /satellite  /plants  /health ...  │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                 AI Engine  (ai/)                             │
│                                                              │
│   Pipeline Manager v2                                        │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│   │  Data    │→│ Spectral │→│Detection │→│Post-Proc │      │
│   │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │      │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│   │Attrib.   │→│ Insight  │→│Temporal  │                    │
│   │(Graph)   │ │(Physics) │ │  Agent   │                    │
│   └──────────┘ └──────────┘ └──────────┘                    │
│                                                              │
│  ┌─────────────────────┐  ┌──────────────────────────────┐  │
│  │  Satellite Sources   │  │         Models               │  │
│  │  • Sentinel-2 L2A   │  │  • UNet (methane_model.pth) │  │
│  │  • NASA EMIT L2A    │  │  • Physics module (P-G)     │  │
│  │  • AVIRIS           │  │  • Graph attribution         │  │
│  │  • Synthetic stub   │  │  • False-positive filter    │  │
│  └─────────────────────┘  └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
Quantum-Coders/
│
├── server/                         # FastAPI backend
│   ├── app/
│   │   ├── main.py                 # ← API server entrypoint (580 lines)
│   │   └── final.py
│   └── requirements.txt            # Python dependencies
│
├── ai/                             # AI/ML engine
│   ├── config.py                   # Global constants (thresholds, GWP, pixel area)
│   ├── pipelines/
│   │   ├── pipeline_manager_v2.py  # ← Main AI orchestrator (1255 lines)
│   │   └── en02_pipeline.ipynb     # Research notebook
│   ├── models/
│   │   ├── inference_model.py      # UNet wrapper
│   │   ├── physics_module.py       # Pasquill-Gifford dispersion
│   │   ├── graph_attribution.py    # Wind-aware graph source attribution
│   │   ├── false_positive_filter.py
│   │   ├── inversion_pipeline.py   # IME quantification method
│   │   ├── satellite_adapter.py    # SWIR ratio, hybrid detection
│   │   ├── train_model.py          # Model training script
│   │   └── methane_model.pth       # Trained model weights
│   ├── data/
│   │   ├── sentinel2_fetcher.py    # Sentinel-2 L2A API client
│   │   ├── emit_fetcher.py         # NASA EMIT hyperspectral client
│   │   ├── aviris_loader.py        # AVIRIS airborne data loader
│   │   └── generate_dataset_v3.py  # Synthetic training data generator
│   └── utils/
│       ├── logger.py               # Structured logging
│       └── temporal_analysis.py    # Time-series trend analysis
│
├── client/                         # React + Vite frontend (Advanced SPA)
│   ├── public/
│   │   └── live.html               # ← Lightweight standalone UI (served by backend)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── GlobePage.jsx       # 3D rotating globe (Three.js)
│   │   │   ├── DetectionPage.jsx   # 2D world map + bounding box detection
│   │   │   ├── AlertsPage.jsx      # Real-time alert stream
│   │   │   ├── FacilitiesPage.jsx  # Searchable facility database
│   │   │   └── SimulationPage.jsx  # 3D factory simulation
│   │   ├── components/
│   │   │   ├── Globe/              # Three.js globe components
│   │   │   ├── Map/                # MapLibre + Deck.gl map
│   │   │   ├── Alerts/             # Alert panels
│   │   │   ├── Charts/             # Recharts emission graphs
│   │   │   ├── Dashboard/          # Dashboard widgets
│   │   │   └── Simulation/         # 3D factory scene
│   │   ├── api/                    # Axios API client
│   │   ├── store/                  # Zustand state management
│   │   └── styles/                 # CSS modules
│   ├── package.json
│   └── vite.config.js              # Vite config (proxy → backend :8000)
│
├── outputs/                        # Runtime image outputs
│   ├── latest_satellite.png        # Latest RGB satellite capture
│   ├── swir_false.png              # SWIR false-color overlay
│   └── plume_mask.png              # Detected plume mask
│
├── dataset/                        # Training dataset
├── data/                           # Data files
├── docker/                         # Dockerfile configs
├── docker-compose.yml              # One-command full-stack deployment
├── detect_methane.py               # Standalone CLI detection script
└── visualize_results.py            # Result visualization utility
```

---

## 🤖 How It Works — The AI Pipeline

Every scan triggers a chain of 8 specialized agents in sequence:

### Step 1 — DataAgent: Satellite Data Acquisition
Tries data sources in priority order:
```
[1] NASA EMIT Hyperspectral (L2A) — if available for location
[2] Sentinel-2 L2A (Sentinel Hub API) — retries with 1×, 2×, 3× radius
[3] Synthetic fallback — deterministic procedural bands (always works)
```
Extracts bands: **B04** (Red), **B08** (NIR), **B11** (SWIR-1 @ 1.6μm), **B12** (SWIR-2 @ 2.3μm), **RGB**

### Step 2 — PreprocessingAgent
- OpenCV `fastNlMeansDenoisingColored` for noise reduction
- Band normalization and resizing to standard `IMG_SIZE`

### Step 3 — SpectralAgent: SWIR Analysis
```
SWIR Ratio = (B12 − B11) / (B12 + B11)   ← methane spectral fingerprint
CH4 Band   = NIR − (SWIR_ratio × 65)      ← concentration proxy
```
Methane absorbs differently at 1.6μm vs 2.3μm. This ratio isolates CH₄-rich pixels.

### Step 4 — DetectionAgent: Neural Network Inference
- Feeds SWIR/NIR composite into trained **UNet** → probability map
- Fuses with SWIR concentration mask:
  ```
  Plume Mask = model_prob_map ∩ swir_concentration_mask
  ```
- Adaptive threshold fallback if model is too conservative
- Guardrail: mask capped at **12% of frame** to prevent false positives

### Step 5 — PostProcessingAgent: False Positive Filtering
Removes detections in regions that correlate with clouds, bright urban surfaces, and water reflections (not methane).

### Step 6 — AttributionAgent (Graph-Based)
For each detected plume centroid, scores all plants in the database:
```
Score(plant) = f(distance_to_plume, wind_alignment, plume_intensity)
wind_alignment = dot(wind_vector, plant→plume_vector)
```
Returns **top-3 candidate source facilities** with confidence scores.

### Step 7 — InsightAgent (Physics-Based Quantification)
Runs two independent emission models and blends them:

**Model A — IME (Integrated Mass Enhancement):**
```
Q (kg/s) = (U_eff / L) × Σ(ΔΩ × pixel_area × k_column)
```

**Model B — Pasquill-Gifford Gaussian Dispersion:**
```
Q (kg/s) = (M × U × A_align × S_spread) / A_plume
```

Final emission rate = calibrated blend of both.
Also computes: CO₂ equivalent, financial loss (USD/hr), uncertainty band, atmospheric stability class.

### Step 8 — TemporalAgent
Appends emission reading to plant's history → runs time-series trend analysis (rising/falling/stable).

---

## 🔬 Scientific Methods

| Method | Purpose | Formula |
|---|---|---|
| **SWIR Ratio** | Spectral methane detection | `(B12−B11)/(B12+B11)` |
| **Hybrid Detection** | Reduce false positives | `model_mask ∩ swir_mask` |
| **IME** | Emission quantification from column data | `Q = (U/L) × IME` |
| **Pasquill-Gifford** | Atmospheric dispersion physics | Gaussian plume (stability class A–F) |
| **Graph Attribution** | Wind-aware source identification | Distance + wind alignment scoring |
| **GWP-28** | Climate impact | `CO₂_eq = CH₄_kg × 28` |

---

## ✅ Prerequisites

### Backend
| Requirement | Version |
|---|---|
| Python | 3.11 or higher |
| pip | Latest |
| (Optional) CUDA GPU | For faster inference |

### Frontend (React)
| Requirement | Version |
|---|---|
| Node.js | 18+ (20 recommended) |
| npm | 9+ |

### Optional API Keys (for live satellite data)
| Service | What it unlocks |
|---|---|
| [Sentinel Hub](https://www.sentinel-hub.com/) | Real Sentinel-2 L2A imagery |
| NASA LPDAAC | NASA EMIT hyperspectral data |

> **Without API keys**, the system runs in **synthetic fallback mode** — all features work, images are procedurally generated.

---

## 🚀 Quick Start — Backend

```bash
# 1. Navigate to the project root
cd d:\NITTE\Quantum-Coders

# 2. (Recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r server/requirements.txt

# 4. Start the FastAPI server
python -m uvicorn server.app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be live at: **http://localhost:8000**

Verify it's running:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "device": "cpu",
  "model_loaded": false,
  "demo_mode": true,
  "uptime_seconds": 2.1
}
```

---

## 🖥 Quick Start — Frontend (Live UI)

> This is the **simplest way** to use IGNISIA. No Node.js required.

Once the backend is running, simply open in your browser:

```
http://localhost:8000/live
```

The backend serves `client/public/live.html` directly. This is a fully featured UI:

### What you can do in the Live UI:

1. **Type a company name/address** → Click **"Locate Address"** → auto-fills lat/lon via geocoding
2. **Or manually enter Latitude/Longitude** coordinates
3. **Configure scan options:**
   - Wind Speed (m/s) — leave blank for default
   - Radius (km) — area to scan around the coordinates
   - Mask Mode — `Auto` (recommended) or `Strict`
   - Prefer EMIT — try NASA hyperspectral first (Yes/No)
   - Live Satellite Mode — `Strict` (real satellite only) or `Allow fallback`
4. **Click "Run Live Scan"** — starts the full AI pipeline
5. **View results:**
   - 📊 Stats panel: Plume detected, Leak rate (kg/hr), Cost (USD/hr), Confidence, Source facility, Image source
   - 🗺 **Left image** — Normal RGB satellite view
   - 🔬 **Right image** — SWIR false-color overlay (**red = methane detected**)
   - 🏭 Company/facility crops with risk badges
   - 📋 Full raw JSON response from the pipeline

### Example: Scanning a refinery
```
Company Name: Reliance Industries
Company Address: Jamnagar, Gujarat, India
→ Click Locate Address
→ Click Run Live Scan
```

---

## ⚛️ Quick Start — React Frontend (Advanced)

The React SPA provides the full 3D globe, animated factory simulation, and facility database.

```bash
# 1. Navigate to client directory
cd d:\NITTE\Quantum-Coders\client

# 2. Install all dependencies (first time only — ~500MB)
npm install

# 3. Start the development server
npm run dev
```

Open in browser: **http://localhost:3000**

> The Vite dev server automatically proxies `/api/*` and `/ws/*` requests to the backend at `http://localhost:8000`. Make sure the backend is running first.

### Available npm scripts

| Command | Description |
|---|---|
| `npm run dev` | Start development server with hot reload (port 3000) |
| `npm run build` | Build production bundle → `client/dist/` |
| `npm run preview` | Preview production build locally |
| `npm run lint` | Run ESLint on source files |

### React Frontend Pages

| Page | Route | Description |
|---|---|---|
| **Globe** | `/` | Interactive 3D rotating globe (Three.js) with global emission hotspots |
| **Detection** | `/detection` | 2D world map with bounding box selector and real-time detection overlay |
| **Alerts** | `/alerts` | Live alert stream — CRITICAL / HIGH / MODERATE severity events |
| **Facilities** | `/facilities` | Searchable facility database with 30-day emission history charts |
| **Simulation** | `/simulation` | 3D industrial facility model with animated workers and vehicles |

---

## 🐳 Running with Docker

> One command to run everything — no manual setup needed.

```bash
# From the project root
cd d:\NITTE\Quantum-Coders
docker-compose up --build
```

| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Live UI | http://localhost:8000/live |
| React Frontend | http://localhost:3000 |

To stop:
```bash
docker-compose down
```

---

## 📡 API Reference

### Core Detection Endpoints

#### `POST /predict/live` — Live Satellite Scan ⭐
The main endpoint. Fetches real satellite data and runs the full AI pipeline.

**Request body:**
```json
{
  "lat": 19.0760,
  "lon": 72.8777,
  "wind_speed_ms": 5.0,
  "radius_km": 5.0,
  "prefer_emit": false,
  "mask_mode": "auto",
  "require_live_satellite": false
}
```

**Response:**
```json
{
  "plume_detected": true,
  "emission_kghr": 342.5,
  "cost_loss_usd_per_hour": 1.37,
  "source": "Gas Plant Beta",
  "confidence": 0.82,
  "image_source": "Sentinel-2 L2A",
  "quantification": {
    "method": "fused_model_swir_calibrated",
    "emission_kghr": 342.5,
    "raw_estimates": {
      "ime_emission_kghr": 310.2,
      "physics_emission_kghr": 374.8
    }
  },
  "processing_time_ms": 1240.3
}
```

#### `POST /predict` — Upload Image Scan
Upload your own satellite image for analysis.

```bash
curl -X POST http://localhost:8000/predict \
  -F "file=@satellite_image.png"
```

#### `POST /predict/geo` — Coordinate Scan (Standard Pipeline)
```bash
curl -X POST "http://localhost:8000/predict/geo?lat=19.076&lon=72.877"
```

#### `POST /predict_bbox` — Bounding Box Area Scan
```bash
curl -X POST "http://localhost:8000/predict_bbox?lat_min=18.0&lat_max=20.0&lon_min=72.0&lon_max=74.0"
```

### Utility Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Server health, model status, uptime, request count |
| `/plants` | GET | List all facilities in the plant database |
| `/history/{plant_id}` | GET | Emission history for a specific plant |
| `/scan/scheduled` | GET | Run a full scan across all known plants |
| `/geocode?address=...` | GET | Geocode an address to lat/lon |
| `/satellite/latest` | GET | Latest RGB satellite image (PNG) |
| `/satellite/swir` | GET | SWIR false-color overlay (PNG) |
| `/emit/availability?lat=&lon=` | GET | Check NASA EMIT data availability |
| `/preflight/sentinel` | GET | Sentinel Hub connectivity check |
| `/subscription?tier=pro` | GET | SaaS subscription tier info |

---

## 🚨 Severity Classification

| Level | Emission Rate | Action |
|---|---|---|
| 🔴 **CRITICAL** | > 1000 kg/hr | Immediate shutdown + regulatory report + emergency response |
| 🟠 **HIGH** | 500–1000 kg/hr | Urgent inspection + temporary shutdown |
| 🟡 **MODERATE** | 100–500 kg/hr | Maintenance alert + scheduled repair |
| 🟢 **LOW** | < 100 kg/hr | Increased monitoring frequency |

---

## ⚙️ Configuration

### Backend Environment Variables

Create a `.env` file in the project root or set these environment variables:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | API server bind host |
| `PORT` | `8000` | API server port |
| `RELOAD` | `0` | Set to `1` for hot reload in development |
| `EN02_ALERT_THRESHOLD` | `300` | Minimum emission (kg/hr) to raise alert |
| `ENABLE_EMIT` | `0` | Set to `1` to prefer NASA EMIT data |
| `GEOCODE_USER_AGENT` | (default) | User-Agent for Nominatim geocoding |
| `GEOCODE_INSECURE_SSL` | `0` | Set to `1` to skip TLS verification (dev only!) |

### Sentinel Hub Configuration

To enable real Sentinel-2 imagery, set up Sentinel Hub credentials:
```bash
# See ai/data/sentinel2_fetcher.py for configuration details
# Register at https://www.sentinel-hub.com/
```

### Frontend Environment Variables

Create `client/.env`:
```
VITE_API_URL=http://localhost:8000
```

---

## 🛠 Troubleshooting

### Backend won't start

```bash
# Check Python version (need 3.11+)
python --version

# Check if port 8000 is already in use
netstat -ano | findstr :8000

# Install dependencies if missing
pip install -r server/requirements.txt
```

### React frontend can't connect to backend

```bash
# Confirm backend health
curl http://localhost:8000/health

# Check the proxy config in client/vite.config.js
# It should proxy /api → http://localhost:8000
```

### "Torch unavailable; running in demo mode"

This is **normal** — the AI pipeline has a demo mode that works without PyTorch.  
To enable full neural network inference:
```bash
pip install torch torchvision
```

### Satellite images not loading

1. Backend must be running at `http://localhost:8000`
2. Without Sentinel Hub credentials, images use synthetic fallback (still functional)
3. Check browser console for CORS errors
4. Verify: `curl http://localhost:8000/satellite/latest`

### `npm install` takes too long / fails

```bash
# Clear npm cache and retry
npm cache clean --force
npm install

# If behind a proxy:
npm config set proxy http://your-proxy:port
```

### Port 3000 already in use

```bash
# Kill the process using port 3000
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Or change port in client/vite.config.js
```

---

## 🏭 Built-In Facility Database

The system includes 6 pre-loaded Indian industrial facilities:

| ID | Name | Location | Type |
|---|---|---|---|
| P-01 | Refinery Alpha | Delhi (28.61°N, 77.21°E) | Oil Refinery |
| P-02 | Gas Plant Beta | Mumbai (19.08°N, 72.88°E) | Natural Gas |
| P-03 | Compressor Station C | Bengaluru (12.97°N, 77.59°E) | Pipeline |
| P-04 | Landfill Site D | Kolkata (22.57°N, 88.36°E) | Landfill |
| P-05 | Coal Mine E | Jharkhand (23.61°N, 85.28°E) | Mining |
| P-06 | Petrochemical Hub F | Surat (21.17°N, 72.83°E) | Petrochemical |

---

## 🏆 SaaS Subscription Tiers

| Tier | Price | Scans/month | Alerts | API Access |
|---|---|---|---|---|
| Basic | $50/mo | 10 | ✗ | ✗ |
| Pro | $200/mo | 100 | ✓ | ✓ |
| Enterprise | $500/mo | Unlimited | ✓ | ✓ |

Check tier info: `GET /subscription?tier=pro`

---

## 🧰 Full Tech Stack

### Backend
| Technology | Version | Role |
|---|---|---|
| Python | 3.11+ | Core language |
| FastAPI | 0.111 | REST API framework |
| Uvicorn | 0.30 | ASGI server |
| NumPy | 1.26 | Numerical computing |
| OpenCV | 4.9 | Image processing |
| PyTorch | 2.9+ | Neural network inference |
| sentinelhub | 3.11+ | Sentinel-2 satellite data |

### AI / ML
| Component | Method |
|---|---|
| Plume detection | UNet segmentation (CNN) |
| Spectral analysis | SWIR ratio (B11/B12) |
| Emission quantification | IME + Pasquill-Gifford physics |
| Source attribution | Graph scoring with wind alignment |
| False positive filtering | Texture + brightness correlation |
| Trend analysis | Time-series statistics |

### Frontend (React)
| Technology | Version | Role |
|---|---|---|
| React | 18.3 | UI framework |
| Vite | 5.4 | Build tool + dev server |
| Three.js | 0.168 | 3D globe and factory |
| react-three-fiber | 8.17 | React bindings for Three.js |
| Deck.gl | 9.0 | Geospatial data visualization |
| MapLibre GL | 4.7 | 2D map rendering |
| Recharts | 2.13 | Emission history charts |
| Zustand | 5.0 | Global state management |
| Framer Motion | 11.9 | UI animations |
| GSAP | 3.14 | Advanced animations |
| Axios | 1.7 | HTTP client |

---

## 📄 License

Copyright © 2026 IGNISIA / Quantum-Coders. All rights reserved.

---

## 🙋 Support

- **Backend not starting?** Check the terminal for red error lines from Uvicorn.
- **Frontend issues?** Open browser DevTools → Console + Network tabs.
- **API errors?** Check `http://localhost:8000/health` and backend terminal logs.
