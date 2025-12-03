# Play Store Review Analyzer - Frontend & API

This document explains the new frontend dashboard and API features added to the review analyzer.

## New Features

### 1. Generic Play Store App Support
The analyzer now works with **any Google Play Store app**, not just Groww!

Configure in `.env`:
```bash
APP_PACKAGE_NAME=com.yourapp.packagename
APP_NAME=YourAppName
REVIEW_LANG=en
REVIEW_COUNTRY=in
```

### 2. Review Type Classification
Reviews are now classified into 10 types:
- Bug Report
- Feature Request
- Positive Feedback
- Negative Feedback
- Pricing/Value Concern
- Customer Support Issue
- Transaction/Payment Issue
- Security/Trust Concern
- Performance Issue
- UI/UX Issue

### 3. React-less Frontend Dashboard
A beautiful, responsive Bento-style dashboard built with pure HTML/CSS/JS.

**Features:**
- Real-time statistics
- Interactive charts (Chart.js)
- Latest reviews table
- AI insights panel
- One-click data refresh

### 4. REST API Server
Flask-based API with CORS support.

**Endpoints:**
- `GET /api/reviews` - Get latest reviews
- `GET /api/summary` - Get weekly summary
- `GET /api/themes` - Get theme distribution
- `GET /api/review-types` - Get review type distribution
- `GET /api/statistics` - Get overall statistics
- `POST /api/refresh` - Trigger pipeline refresh
- `GET /api/health` - Health check

### 5. CLI Utility
Command-line interface for manual operations.

**Commands:**
```bash
python src/cli.py fetch --weeks 2
python src/cli.py classify
python src/cli.py summary
python src/cli.py email --send
python src/cli.py full-run
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

### 3. Start API Server
```bash
python src/api_server.py
```
Server runs on `http://localhost:5001`

### 4. Open Frontend
Open `frontend/index.html` in your browser, or access via API server:
```
http://localhost:5001/
```

### 5. Run Pipeline
Click "Refresh Data" button in the dashboard, or run manually:
```bash
python main.py
```

## Architecture

```
┌─────────────┐
│  Frontend   │  (HTML/CSS/JS)
│  Dashboard  │
└──────┬──────┘
       │ REST API
┌──────▼──────┐
│ Flask API   │  (Port 5001)
│   Server    │
└──────┬──────┘
       │
┌──────▼────────────────┐
│  Pipeline Components  │
│  ├── Import Reviews   │
│  ├── Classify Themes  │
│  ├── Classify Types   │ (NEW)
│  ├── Generate Note    │
│  ├── Draft Email      │
│  └── Send Email       │
└───────────────────────┘
```

## Frontend Design

The dashboard uses a **Bento Grid** layout with:
- **Soft blue theme** (#4A6CF7)
- **Rounded cards** (20px radius)
- **Clean Inter font**
- **Responsive** (mobile & desktop)
- **Smooth animations**

### Color Palette
- Primary: `#4A6CF7`
- Background: `#F5F8FF`
- Card: `#FFFFFF`
- Border: `#E3E9F7`
- Success: `#10B981`
- Danger: `#EF4444`

## Testing

Run unit tests:
```bash
pytest tests/
```

Run with integration tests (requires API key):
```bash
pytest tests/ --run-integration
```

## Deployment

### Option 1: Local Server
```bash
python src/api_server.py
```

### Option 2: Production WSGI
Use gunicorn or uwsgi:
```bash
gunicorn -w 4 -b 0.0.0.0:5001 src.api_server:app
```

### Option 3: Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["python", "src/api_server.py"]
```

## API Usage Examples

### Get Reviews
```bash
curl http://localhost:5001/api/reviews?limit=10
```

### Get Statistics
```bash
curl http://localhost:5001/api/statistics
```

### Trigger Refresh
```bash
curl -X POST http://localhost:5001/api/refresh
```

## Troubleshooting

**Q: Frontend shows no data**
- Ensure API server is running on port 5001
- Run pipeline at least once to generate data
- Check browser console for errors

**Q: Charts not displaying**
- Verify Chart.js CDN is loading
- Check that data endpoints return valid JSON
- Inspect network tab for failed requests

**Q: CORS errors**
- flask-cors is installed and configured
- API server allows all origins by default
- Check browser security settings

## Support

For issues or questions:
1. Check existing GitHub issues
2. Review logs in `logs/` directory
3. Run with `LOG_LEVEL=DEBUG` for verbose output

## License

Same as parent project.
