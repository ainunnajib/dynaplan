# Dynaplan

Open-source enterprise planning platform. A full-featured replacement for Anaplan.

## Tech Stack

- **Frontend**: Next.js 16, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Python, FastAPI, SQLAlchemy, NumPy/Pandas
- **Database**: PostgreSQL, Redis

## Features

- Multidimensional modeling with formula engine
- Modules, line items, and dimensions (Anaplan-compatible paradigm)
- High-performance grid UI with pivot/filter
- Dashboard builder with charts
- Scenario planning & what-if analysis
- Real-time collaboration
- CSV/Excel import/export
- Role-based access control
- REST API for integrations

## Getting Started

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload
```

PostgreSQL read replicas and pool behavior can be configured with:

- `DYNAPLAN_DATABASE_READ_REPLICA_URLS` (comma-separated URLs)
- `DYNAPLAN_DATABASE_POOL_SIZE`
- `DYNAPLAN_DATABASE_MAX_OVERFLOW`
- `DYNAPLAN_DATABASE_POOL_TIMEOUT`
- `DYNAPLAN_DATABASE_POOL_RECYCLE`

### Frontend
```bash
cd frontend
bun install
bun dev
```

## Deploy to Google Cloud (Artifact Registry)

This repo includes a deployment script that builds images in **Artifact Registry** and deploys backend/frontend to **Cloud Run**.

### Prerequisites

- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated
- Permissions to manage Cloud Run, Cloud Build, Artifact Registry, Cloud SQL, and Secret Manager

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud config set run/region us-central1
```

### Quick Deploy

```bash
./scripts/deploy_gcp.sh
```

By default, the script will:

1. Enable required APIs
2. Create Artifact Registry repo `dynaplan` (if missing)
3. Provision Cloud SQL PostgreSQL + database/user (if missing)
4. Create/update Secret Manager secrets for DB URL and app secret
5. Build backend/frontend images with Cloud Build and push to Artifact Registry
6. Deploy `dynaplan-backend` and `dynaplan-frontend` to Cloud Run

### Important Environment Overrides

- `PROJECT_ID` (default: current `gcloud` project)
- `REGION` (default: `us-central1`)
- `REPOSITORY` (default: `dynaplan`)
- `BACKEND_SERVICE` / `FRONTEND_SERVICE`
- `USE_CLOUD_SQL` (default: `true`)
- `CLOUD_SQL_INSTANCE`, `CLOUD_SQL_DB_NAME`, `CLOUD_SQL_DB_USER`, `CLOUD_SQL_TIER`
- `DB_PASSWORD_SECRET_NAME`, `DB_URL_SECRET_NAME`, `APP_SECRET_KEY_SECRET_NAME`
- `FORCE_ROTATE_SECRETS` (default: `false`)
- `FRONTEND_URL` (optional fixed CORS origin; otherwise uses deployed frontend URL)

### Example: Custom Cloud SQL Names

```bash
PROJECT_ID=my-prod-project \
REGION=us-central1 \
CLOUD_SQL_INSTANCE=dynaplan-prod-pg \
CLOUD_SQL_DB_NAME=dynaplan \
CLOUD_SQL_DB_USER=dynaplan_app \
./scripts/deploy_gcp.sh
```

### Example: No Cloud SQL (ephemeral SQLite)

```bash
USE_CLOUD_SQL=false \
BACKEND_DB_URL='sqlite+aiosqlite:////tmp/dynaplan.db' \
BACKEND_AUTO_CREATE_SCHEMA=true \
./scripts/deploy_gcp.sh
```

### Manual Deploy (Without Script)

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1
REPOSITORY=dynaplan
BACKEND_SERVICE=dynaplan-backend
FRONTEND_SERVICE=dynaplan-frontend
TAG=$(git rev-parse --short HEAD)

BACKEND_IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/backend:${TAG}
FRONTEND_IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/frontend:${TAG}

# Build and push backend image to Artifact Registry
gcloud builds submit --config cloudbuild.backend.yaml \
  --substitutions _IMAGE=${BACKEND_IMAGE} .

# Deploy backend
gcloud run deploy ${BACKEND_SERVICE} \
  --region ${REGION} \
  --image ${BACKEND_IMAGE} \
  --allow-unauthenticated

BACKEND_URL=$(gcloud run services describe ${BACKEND_SERVICE} \
  --region ${REGION} --format='value(status.url)')

# Build and push frontend image to Artifact Registry
gcloud builds submit --config cloudbuild.frontend.yaml \
  --substitutions _IMAGE=${FRONTEND_IMAGE},_NEXT_PUBLIC_API_URL=${BACKEND_URL} .

# Deploy frontend
gcloud run deploy ${FRONTEND_SERVICE} \
  --region ${REGION} \
  --image ${FRONTEND_IMAGE} \
  --allow-unauthenticated \
  --set-env-vars NEXT_PUBLIC_API_URL=${BACKEND_URL}
```

### Verify Deployment

```bash
gcloud run services describe dynaplan-backend --region us-central1 --format='value(status.url)'
gcloud run services describe dynaplan-frontend --region us-central1 --format='value(status.url)'
```

## Development

This project uses Claude Code autonomous workflow patterns. See `CLAUDE.md` for development conventions and `features.json` for the full feature roadmap.

## License

MIT
