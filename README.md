# PrivInspect - Privacy Analysis Tool

PrivInspect is a comprehensive privacy analysis tool that combines machine learning with heuristic analysis to evaluate website privacy practices. It consists of a Chrome extension frontend, FastAPI backend, and an advanced ML model trained on DuckDuckGo's TrackerRadar dataset.

## Features

- **Real-time Privacy Analysis**: Analyzes websites as you browse with detailed privacy scores
- **ML-Powered Domain Scoring**: Uses trained models on 51,198+ domains from TrackerRadar dataset
- **Comprehensive Detection**: Identifies tracking scripts, fingerprinting, cookies, and third-party requests
- **Fair Scoring System**: Balanced penalties with proportion-based calculations
- **Chrome Extension**: Easy-to-use browser extension with detailed breakdowns
- **RESTful API**: Backend API for integration with other tools

## Architecture

```
PrivInspect/
├── client/          # Chrome Extension (React + TypeScript)
├── backend/         # FastAPI Server (Python)
├── notebooks/       # ML Training Pipeline (Jupyter)
├── scripts/         # Standalone Training Scripts
└── README.md        # This file
```

## Prerequisites

- **Python 3.8+** (for backend and ML training)
- **Node.js 16+** (for Chrome extension)
- **Chrome Browser** (for extension testing)
- **2GB free disk space** (for ML data and models)
- **Internet connection** (for downloading TrackerRadar data)

## Quick Start

### 1. Clone Repository

```bash
git clone <your-repository-url>
cd PrivInspect
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env with your configuration (JWT_SECRET, etc.)
```

### 3. Train ML Model (Required)

The backend requires trained ML models. Run the complete training pipeline:

```bash
cd notebooks

# Open Jupyter notebook
jupyter notebook domain_ranking_model.ipynb

# OR use Python directly
python -m jupyter notebook domain_ranking_model.ipynb
```

**Run all 6 steps in the notebook:**

1. Install dependencies automatically
2. Setup project structure and download tools
3. Download TrackerRadar data (~51,198 domains)
4. Define advanced feature extraction
5. Process all domain data
6. Train ML model and save for production

**Expected runtime:** 20-25 minutes for complete training

### 4. Start Backend Server

```bash
cd backend
python3 main.py
```

Server will start at `http://localhost:8000`

### 5. Chrome Extension Setup

```bash
cd client

# Install dependencies
npm install

# Build extension
npm run build

# The built extension will be in client/dist/
```

**Load in Chrome:**

1. Open Chrome → Extensions (`chrome://extensions/`)
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `client/dist/` folder
5. Extension should appear in your browser toolbar

### 6. Test the System

1. **Backend Health Check:**

   ```bash
   curl http://localhost:8000/health
   ```

2. **Extension Test:**
   - Click the PrivInspect extension icon
   - Visit any website
   - Click "Analyze Current Page"
   - View privacy score and detailed breakdown

## Development

### Backend Development

```bash
cd backend
source .venv/bin/activate
python3 main.py

# Run tests
python -m pytest

# API Documentation available at:
# http://localhost:8000/docs
```

### Frontend Development

```bash
cd client

# Development build with hot reload
npm run dev

# Build for production
npm run build
```

### Retraining ML Model

To retrain with latest TrackerRadar data:

```bash
cd notebooks
# Run all cells in domain_ranking_model.ipynb

# OR use the standalone script:
cd scripts
python train_domain_model.py
```

## API Endpoints

### Core Analysis

- `POST /api/v1/analyze` - Analyze webpage privacy
- `GET /health` - Health check

### ML Model

- `GET /api/v1/model/info` - Model information
- `POST /api/v1/model/predict` - Direct domain predictions

### Authentication

- `POST /api/v1/auth/token` - Get JWT token
- `POST /api/v1/auth/refresh` - Refresh token

### Chrome Extension

Built extension loads automatically. For development, manifest.json contains all necessary permissions.

## ML Model Details

**Training Data:** 51,198 domains from DuckDuckGo TrackerRadar
**Algorithm:** LightGBM Gradient Boosting
**Features:** 17 domain-level features including:

- Enhanced fingerprinting scores
- Category-based tracking detection
- Resource type analysis
- Prevalence and cookie data

**Performance:**

- Tracking domains: ~20-30/100 (lower = better detection)
- Legitimate domains: ~85-95/100 (higher = better protection)
- AddThis improvement: 100.0 → 57.4/100

## Privacy Scoring

**ML Base Score (0-100):** Domain-level ML predictions
**Heuristic Penalties:** Proportion-based system

- Third-party domains: Based on ratios
- Persistent cookies: Percentage of total
- Inline scripts: Percentage with reduced impact
- Penalty cap: Maximum -10 points

**Final Score:** ML Score + Heuristic Penalties (capped)

## Project Structure

```
PrivInspect/
├── backend/
│   ├── app/
│   │   ├── routers/       # API endpoints
│   │   ├── models/        # Data models
│   │   ├── ml_scoring.py  # ML integration
│   │   └── auth.py        # Authentication
│   ├── main.py            # FastAPI app
│   └── requirements.txt   # Python dependencies
├── client/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── services/      # API services
│   │   └── types/         # TypeScript types
│   ├── public/            # Extension assets
│   ├── package.json       # Node.js dependencies
│   └── manifest.json      # Extension manifest
├── notebooks/
│   └── domain_ranking_model.ipynb  # Complete ML pipeline
└── scripts/
    └── train_domain_model.py       # Standalone training
```

## Troubleshooting

### Backend Issues

- **Model not found:** Run the ML training notebook first
- **Port 8000 in use:** Change port in main.py or kill existing process
- **Import errors:** Ensure virtual environment is activated

### Extension Issues

- **Extension not loading:** Check Chrome developer mode is enabled
- **API errors:** Verify backend is running on correct port
- **No analysis results:** Check browser console for errors

### ML Training Issues

- **Download failures:** Check internet connection
- **Memory errors:** Ensure 4GB+ RAM available
- **Import errors:** Run Step 1 in notebook to install dependencies

**Note:** The ML model training is required for the system to function properly. The notebook provides a completely self-contained setup that works on any fresh device.
