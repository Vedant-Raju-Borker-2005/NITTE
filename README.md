# MethSight - Satellite Methane Detection AI

A comprehensive satellite-based methane emission detection and attribution system combining AI inference, geographic visualization, and real-time alerting.

## Overview

MethSight uses satellite imagery analysis to detect and quantify methane emissions from industrial facilities worldwide. The system employs:

- **AI Pipeline**: Segmentation, quantification, and attribution models for plume detection.
- **Real-time Alerts**: Critical/High/Medium severity notifications for super-emitters.
- **3D Visualization**: Interactive factory simulation and rotating globe view.
- **Global Heatmaps**: 2D/3D world maps showing methane hotspots.
- **Facility Database**: Searchable database with emission history and risk scoring.
- **Detection Analytics**: Bounding box-based detection with confidence metrics.

## Project Structure

```
MethSight2/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # FastAPI app setup
│   │   ├── api/            # API endpoints
│   │   │   ├── alerts.py
│   │   │   ├── detect.py
│   │   │   ├── facilities.py
│   │   │   ├── simulation.py
│   │   │   └── timeseries.py
│   │   ├── models/         # ML models
│   │   ├── pipeline/       # Processing pipeline
│   │   ├── utils/          # Utilities
│   │   └── data/           # Data files
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile
│   └── venv/              # Virtual environment
│
├── frontend/               # React + Vite frontend
│   ├── src/
│   │   ├── pages/         # Page components
│   │   │   ├── AlertsPage.jsx
│   │   │   ├── DetectionPage.jsx
│   │   │   ├── FacilitiesPage.jsx
│   │   │   ├── SimulationPage.jsx
│   │   │   └── GlobePage.jsx
│   │   ├── components/    # Reusable components
│   │   ├── api/          # API client
│   │   ├── store/        # State management
│   │   └── styles/       # CSS
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
│
└── docker-compose.yml      # Docker orchestration
```

## Prerequisites

### Backend
- Python 3.11+
- pip or conda

### Frontend  
- Node.js 20+
- npm

## Quick Start

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`

**Available API Endpoints:**
- GET `/api/health` - Health check
- GET `/api/alerts` - Retrieve methane alerts
- POST `/api/detect` - Run detection pipeline
- GET `/api/facilities` - Get facility database
- GET `/api/facilities/ranking/top` - Top polluting facilities
- GET `/api/simulation/hotspots` - Global emission hotspots
- GET `/api/timeseries` - Emission time series for a facility
- GET `/api/stats` - Global statistics

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

**Scripts:**
- `npm run dev` - Development server with hot reload
- `npm run build` - Production build
- `npm run preview` - Preview production build

### 3. Access the Application

Open your browser and navigate to:
```
http://localhost:3000
```

## Features

### Pages

1. **Dashboard/Globe** - Interactive 3D rotating globe showing global emissions
2. **Simulation** - Real-time 3D factory model with animated workers and vehicles
3. **Detection** - Methane detection interface with 2D world map and bounding box selection
4. **Alerts** - Real-time alert stream (CRITICAL/HIGH/MEDIUM only)
5. **Facilities** - Searchable facility database with emission history

### Key Features

- ✅ **3D Factory Visualization** - Detailed industrial facility with workers and vehicles
- ✅ **Global Heatmap** - 8192x4096 Mercator projection globe
- ✅ **2D Detection Map** - 40+ countries with detection visualization
- ✅ **Real-time Alerts** - Live methane detection notifications
- ✅ **Facility Search** - Filter by name, country, or location
- ✅ **Emission History** - 30-day time series per facility
- ✅ **Risk Scoring** - Automated risk assessment

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# From root directory
docker-compose up --build

# Access at http://localhost:3000
```

The docker-compose.yml orchestrates:
- **Backend** service on port 8000
- **Frontend** service on port 3000
- Automatic API proxy configuration

### Individual Docker Builds

**Backend:**
```bash
cd backend
docker build -t methsight-backend .
docker run -p 8000:8000 methsight-backend
```

**Frontend:**
```bash
cd frontend
docker build -t methsight-frontend .
docker run -p 3000:3000 methsight-frontend
```

## Configuration

### Backend Environment Variables

Create `.env` file in backend directory:
```
DATABASE_URL=postgresql://user:pass@localhost:5432/methsight
LOG_LEVEL=INFO
CACHE_TTL=300
```

### Frontend Environment Variables

Create `.env` file in frontend directory:
```
VITE_API_URL=http://localhost:8000
```

## API Usage Examples

### 1. Run Detection

```bash
curl -X POST "http://localhost:8000/api/detect?bbox=31.0,-104.0,33.0,-102.0&simulate=true"
```

Response:
```json
{
  "detected": true,
  "severity": "CRITICAL",
  "emission_rate_kg_hr": 1250.5,
  "is_super_emitter": true,
  "detection_confidence": 0.92,
  "attribution": {
    "facility_name": "Permian Basin Operations",
    "distance_km": 2.5,
    "attribution_confidence": 0.87
  }
}
```

### 2. Get Facilities

```bash
curl "http://localhost:8000/api/facilities?limit=20&sort_by=risk_score"
```

### 3. Get Top Polluters

```bash
curl "http://localhost:8000/api/facilities/ranking/top?n=10"
```

### 4. Get Alerts

```bash
curl "http://localhost:8000/api/alerts?limit=20&severity=CRITICAL"
```

### 5. Get Timeseries Data

```bash
curl "http://localhost:8000/api/timeseries?facility_id=FAC_001&days=30"
```

## Data Structure

### Alert Object
```json
{
  "id": "ALERT_0001",
  "facility_id": "FAC_0001",
  "facility_name": "Permian Basin",
  "emission_rate_kg_hr": 1500.5,
  "severity": "CRITICAL",
  "timestamp": "2024-01-15T10:30:00Z",
  "country": "USA",
  "lat": 31.8,
  "lon": -103.5,
  "is_super_emitter": true
}
```

### Facility Object
```json
{
  "id": "FAC_0001",
  "name": "Permian Basin Operations",
  "type": "oil_well",
  "country": "USA",
  "operator": "Major Operator Inc",
  "lat": 31.8,
  "lon": -103.5,
  "historical_emission_rate": 1250.5,
  "risk_score": 0.92,
  "last_detected": "2024-01-15T10:30:00Z",
  "detection_count": 42
}
```

### Detection Result
```json
{
  "detected": true,
  "severity": "CRITICAL",
  "detect_confidence": 0.92,
  "emission_rate_kg_hr": 1250.5,
  "emission_uncertainty_kg_hr": 150.2,
  "is_super_emitter": true,
  "plume_centroid": {"lat": 31.8, "lon": -103.5},
  "attribution": {...},
  "wind": {"speed_ms": 5.2, "direction_deg": 270}
}
```

## Severity Levels

- **CRITICAL** - Emission rate > 1000 kg/hr (super-emitters)
- **HIGH** - Emission rate 500-1000 kg/hr  
- **MEDIUM** - Emission rate 100-500 kg/hr
- **LOW** - (filtered out from frontend)

## Technologies

### Backend
- **Framework**: FastAPI 0.104.1
- **Server**: Uvicorn 0.24.0
- **Science**: NumPy, SciPy, scikit-image
- **Imaging**: Pillow

### Frontend
- **Framework**: React 18.3.1
- **Build**: Vite 5.4.21
- **3D Graphics**: Three.js, react-three-fiber
- **Visualization**: Recharts, Deck.gl
- **State**: Zustand
- **Animation**: Framer Motion
- **UI**: Custom components with CSS

## Development

### Backend Development

```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest

# Auto-reload on file changes
uvicorn app.main:app --reload --port 8000
```

### Frontend Development

```bash
# Development with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## Troubleshooting

### Backend won't start
```bash
# Ensure Python 3.11+
python --version

# Check if port 8000 is available
netstat -ano | findstr :8000
```

### Frontend won't connect to backend
```bash
# Check API URL in .env
cat frontend/.env

# Verify backend is running
curl http://localhost:8000/api/health
```

### Large bundle warnings
The frontend bundle size is intentionally large due to Three.js and Deck.gl:
- Three.js: ~980 KB
- Deck.gl: ~300 KB
- React ecosystem: ~400 KB

This is normal for a 3D-heavy application.

### Data not loading
1. Ensure backend is running: `http://localhost:8000/api/health`
2. Check browser console for errors
3. Verify network tab for failed requests
4. Check backend logs for errors

## Performance Tips

- Use simulation mode for faster detection results
- Pre-filter alerts by severity to reduce data
- Limit timeseries queries to < 90 days
- Cache facility data in Zustand store

## License

Copyright 2024 MethSight. All rights reserved.

## Support

For issues or questions, check the application logs:

**Backend logs:**
```bash
# Check terminal where uvicorn is running
# Look for error messages in red text
```

**Frontend logs:**
```bash
# Open browser Developer Tools (F12)
# Check Console tab for errors
# Check Network tab for API errors
```

## Next Steps

1. ✅ Run backend: `uvicorn app.main:app --reload`
2. ✅ Run frontend: `npm run dev`
3. ✅ Open http://localhost:3000
4. ✅ Explore the three pages
5. ✅ Try running a detection
6. ✅ View live alerts

Enjoy exploring methane emissions data!
