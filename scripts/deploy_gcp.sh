#!/usr/bin/env bash
set -euo pipefail

# Deploy Dynaplan backend + frontend to Cloud Run using Artifact Registry.
#
# Required:
#   gcloud auth/application context with deploy permissions
#
# Optional environment overrides:
#   PROJECT_ID
#   REGION (default: us-central1)
#   REPOSITORY (default: dynaplan)
#   BACKEND_SERVICE (default: dynaplan-backend)
#   FRONTEND_SERVICE (default: dynaplan-frontend)
#   USE_CLOUD_SQL (default: true)
#   CLOUD_SQL_INSTANCE (default: dynaplan-pg)
#   CLOUD_SQL_DB_NAME (default: dynaplan)
#   CLOUD_SQL_DB_USER (default: dynaplan_app)
#   CLOUD_SQL_TIER (default: db-custom-1-3840)
#   DB_PASSWORD_SECRET_NAME (default: dynaplan-db-password)
#   DB_URL_SECRET_NAME (default: dynaplan-db-url)
#   APP_SECRET_KEY_SECRET_NAME (default: dynaplan-secret-key)
#   BACKEND_RUNTIME_SERVICE_ACCOUNT (default: <project-number>-compute@developer.gserviceaccount.com)
#   FORCE_ROTATE_SECRETS (default: false)
#   CLOUD_SQL_DB_PASSWORD (optional explicit DB password seed)
#   BACKEND_DB_URL (default: sqlite+aiosqlite:////tmp/dynaplan.db)
#   BACKEND_REDIS_URL (default: redis://localhost:6379/0)
#   BACKEND_SECRET_KEY (default: random value generated per deploy)
#   BACKEND_AUTO_CREATE_SCHEMA (default: true when using sqlite, else false)
#   FRONTEND_URL (if set, used for backend CORS; otherwise inferred from frontend URL after deploy)

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-us-central1}"
REPOSITORY="${REPOSITORY:-dynaplan}"
BACKEND_SERVICE="${BACKEND_SERVICE:-dynaplan-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-dynaplan-frontend}"
USE_CLOUD_SQL="${USE_CLOUD_SQL:-true}"

CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-dynaplan-pg}"
CLOUD_SQL_DB_NAME="${CLOUD_SQL_DB_NAME:-dynaplan}"
CLOUD_SQL_DB_USER="${CLOUD_SQL_DB_USER:-dynaplan_app}"
CLOUD_SQL_TIER="${CLOUD_SQL_TIER:-db-custom-1-3840}"

DB_PASSWORD_SECRET_NAME="${DB_PASSWORD_SECRET_NAME:-dynaplan-db-password}"
DB_URL_SECRET_NAME="${DB_URL_SECRET_NAME:-dynaplan-db-url}"
APP_SECRET_KEY_SECRET_NAME="${APP_SECRET_KEY_SECRET_NAME:-dynaplan-secret-key}"
FORCE_ROTATE_SECRETS="${FORCE_ROTATE_SECRETS:-false}"

BACKEND_DB_URL="${BACKEND_DB_URL:-sqlite+aiosqlite:////tmp/dynaplan.db}"
BACKEND_REDIS_URL="${BACKEND_REDIS_URL:-redis://localhost:6379/0}"
BACKEND_SECRET_KEY="${BACKEND_SECRET_KEY:-}"

is_true() {
  local value
  value="$(printf "%s" "$1" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

secret_exists() {
  local name="$1"
  gcloud secrets describe "${name}" --project "${PROJECT_ID}" >/dev/null 2>&1
}

ensure_secret_with_value() {
  local name="$1"
  local value="$2"
  if ! secret_exists "${name}"; then
    gcloud secrets create "${name}" \
      --project "${PROJECT_ID}" \
      --replication-policy="automatic" \
      --quiet
  fi

  local latest=""
  if latest="$(gcloud secrets versions access latest \
      --secret "${name}" \
      --project "${PROJECT_ID}" 2>/dev/null)"; then
    :
  else
    latest=""
  fi

  if is_true "${FORCE_ROTATE_SECRETS}" || [[ -z "${latest}" ]] || [[ "${latest}" != "${value}" ]]; then
    printf "%s" "${value}" | gcloud secrets versions add "${name}" \
      --project "${PROJECT_ID}" \
      --data-file=- \
      --quiet >/dev/null
  fi
}

get_secret_latest_or_empty() {
  local name="$1"
  gcloud secrets versions access latest \
    --secret "${name}" \
    --project "${PROJECT_ID}" 2>/dev/null || true
}

deploy_backend() {
  local cors_url="$1"
  if is_true "${USE_CLOUD_SQL}"; then
    gcloud run deploy "${BACKEND_SERVICE}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --platform managed \
      --image "${BACKEND_IMAGE}" \
      --service-account "${BACKEND_RUNTIME_SERVICE_ACCOUNT}" \
      --allow-unauthenticated \
      --add-cloudsql-instances "${INSTANCE_CONNECTION_NAME}" \
      --set-env-vars "DYNAPLAN_REDIS_URL=${BACKEND_REDIS_URL},DYNAPLAN_FRONTEND_URL=${cors_url},DYNAPLAN_AUTO_CREATE_SCHEMA=${BACKEND_AUTO_CREATE_SCHEMA}" \
      --set-secrets "DYNAPLAN_DATABASE_URL=${DB_URL_SECRET_NAME}:latest,DYNAPLAN_SECRET_KEY=${APP_SECRET_KEY_SECRET_NAME}:latest" \
      --quiet
  else
    gcloud run deploy "${BACKEND_SERVICE}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --platform managed \
      --image "${BACKEND_IMAGE}" \
      --service-account "${BACKEND_RUNTIME_SERVICE_ACCOUNT}" \
      --allow-unauthenticated \
      --set-env-vars "DYNAPLAN_DATABASE_URL=${BACKEND_DB_URL},DYNAPLAN_REDIS_URL=${BACKEND_REDIS_URL},DYNAPLAN_SECRET_KEY=${BACKEND_SECRET_KEY},DYNAPLAN_FRONTEND_URL=${cors_url},DYNAPLAN_AUTO_CREATE_SCHEMA=${BACKEND_AUTO_CREATE_SCHEMA}" \
      --quiet
  fi
}

if [[ "${BACKEND_DB_URL}" == sqlite* ]]; then
  DEFAULT_AUTO_CREATE_SCHEMA="true"
else
  DEFAULT_AUTO_CREATE_SCHEMA="false"
fi
if is_true "${USE_CLOUD_SQL}"; then
  DEFAULT_AUTO_CREATE_SCHEMA="true"
fi
BACKEND_AUTO_CREATE_SCHEMA="${BACKEND_AUTO_CREATE_SCHEMA:-${DEFAULT_AUTO_CREATE_SCHEMA}}"
if ! is_true "${USE_CLOUD_SQL}" && [[ -z "${BACKEND_SECRET_KEY}" ]]; then
  BACKEND_SECRET_KEY="$(openssl rand -hex 32)"
fi

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is empty. Set PROJECT_ID or configure gcloud core/project." >&2
  exit 1
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
BACKEND_RUNTIME_SERVICE_ACCOUNT="${BACKEND_RUNTIME_SERVICE_ACCOUNT:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"

GIT_SHA="$(git rev-parse --short HEAD)"
BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/backend:${GIT_SHA}"
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/frontend:${GIT_SHA}"

echo "Using project: ${PROJECT_ID}"
echo "Using region: ${REGION}"
echo "Using Artifact Registry repo: ${REPOSITORY}"
echo "Using Cloud SQL mode: ${USE_CLOUD_SQL}"
echo "Using backend runtime service account: ${BACKEND_RUNTIME_SERVICE_ACCOUNT}"

services=(
  artifactregistry.googleapis.com
  run.googleapis.com
  cloudbuild.googleapis.com
)
if is_true "${USE_CLOUD_SQL}"; then
  services+=(
    sqladmin.googleapis.com
    secretmanager.googleapis.com
  )
fi
gcloud services enable "${services[@]}" --project "${PROJECT_ID}" --quiet

if ! gcloud artifacts repositories describe "${REPOSITORY}" \
  --location "${REGION}" \
  --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${REPOSITORY}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Dynaplan container images" \
    --project "${PROJECT_ID}" \
    --quiet
fi

if is_true "${USE_CLOUD_SQL}"; then
  if ! gcloud sql instances describe "${CLOUD_SQL_INSTANCE}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Creating Cloud SQL instance: ${CLOUD_SQL_INSTANCE}"
    gcloud sql instances create "${CLOUD_SQL_INSTANCE}" \
      --project "${PROJECT_ID}" \
      --database-version "POSTGRES_15" \
      --tier "${CLOUD_SQL_TIER}" \
      --region "${REGION}" \
      --storage-size "20GB" \
      --storage-type "SSD" \
      --availability-type "zonal" \
      --quiet
  fi

  if ! gcloud sql databases describe "${CLOUD_SQL_DB_NAME}" \
    --instance "${CLOUD_SQL_INSTANCE}" \
    --project "${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Creating Cloud SQL database: ${CLOUD_SQL_DB_NAME}"
    gcloud sql databases create "${CLOUD_SQL_DB_NAME}" \
      --instance "${CLOUD_SQL_INSTANCE}" \
      --project "${PROJECT_ID}" \
      --quiet
  fi

  CLOUD_SQL_DB_PASSWORD="${CLOUD_SQL_DB_PASSWORD:-$(get_secret_latest_or_empty "${DB_PASSWORD_SECRET_NAME}")}"
  if [[ -z "${CLOUD_SQL_DB_PASSWORD}" ]]; then
    CLOUD_SQL_DB_PASSWORD="$(openssl rand -hex 24)"
  fi
  if [[ -z "${BACKEND_SECRET_KEY}" ]]; then
    BACKEND_SECRET_KEY="$(get_secret_latest_or_empty "${APP_SECRET_KEY_SECRET_NAME}")"
  fi
  if [[ -z "${BACKEND_SECRET_KEY}" ]]; then
    BACKEND_SECRET_KEY="$(openssl rand -hex 32)"
  fi
  ensure_secret_with_value "${DB_PASSWORD_SECRET_NAME}" "${CLOUD_SQL_DB_PASSWORD}"
  ensure_secret_with_value "${APP_SECRET_KEY_SECRET_NAME}" "${BACKEND_SECRET_KEY}"
  DB_PASSWORD="$(gcloud secrets versions access latest \
    --secret "${DB_PASSWORD_SECRET_NAME}" \
    --project "${PROJECT_ID}")"

  if gcloud sql users list \
    --instance "${CLOUD_SQL_INSTANCE}" \
    --project "${PROJECT_ID}" \
    --format="value(name)" | grep -Fx "${CLOUD_SQL_DB_USER}" >/dev/null; then
    echo "Updating Cloud SQL user password: ${CLOUD_SQL_DB_USER}"
    gcloud sql users set-password "${CLOUD_SQL_DB_USER}" \
      --instance "${CLOUD_SQL_INSTANCE}" \
      --password "${DB_PASSWORD}" \
      --project "${PROJECT_ID}" \
      --quiet
  else
    echo "Creating Cloud SQL user: ${CLOUD_SQL_DB_USER}"
    gcloud sql users create "${CLOUD_SQL_DB_USER}" \
      --instance "${CLOUD_SQL_INSTANCE}" \
      --password "${DB_PASSWORD}" \
      --project "${PROJECT_ID}" \
      --quiet
  fi

  INSTANCE_CONNECTION_NAME="$(gcloud sql instances describe "${CLOUD_SQL_INSTANCE}" \
    --project "${PROJECT_ID}" \
    --format='value(connectionName)')"
  BACKEND_DB_URL="postgresql+asyncpg://${CLOUD_SQL_DB_USER}:${DB_PASSWORD}@/${CLOUD_SQL_DB_NAME}?host=/cloudsql/${INSTANCE_CONNECTION_NAME}"
  ensure_secret_with_value "${DB_URL_SECRET_NAME}" "${BACKEND_DB_URL}"

  gcloud secrets add-iam-policy-binding "${DB_URL_SECRET_NAME}" \
    --project "${PROJECT_ID}" \
    --member "serviceAccount:${BACKEND_RUNTIME_SERVICE_ACCOUNT}" \
    --role "roles/secretmanager.secretAccessor" \
    --quiet >/dev/null
  gcloud secrets add-iam-policy-binding "${APP_SECRET_KEY_SECRET_NAME}" \
    --project "${PROJECT_ID}" \
    --member "serviceAccount:${BACKEND_RUNTIME_SERVICE_ACCOUNT}" \
    --role "roles/secretmanager.secretAccessor" \
    --quiet >/dev/null
fi

echo "Building backend image: ${BACKEND_IMAGE}"
gcloud builds submit . \
  --project "${PROJECT_ID}" \
  --substitutions "_IMAGE=${BACKEND_IMAGE}" \
  --config cloudbuild.backend.yaml \
  --quiet

BACKEND_FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"

echo "Deploying backend service: ${BACKEND_SERVICE}"
deploy_backend "${BACKEND_FRONTEND_URL}"

BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format='value(status.url)')"

echo "Backend URL: ${BACKEND_URL}"
echo "Building frontend image: ${FRONTEND_IMAGE}"
gcloud builds submit . \
  --project "${PROJECT_ID}" \
  --substitutions "_IMAGE=${FRONTEND_IMAGE},_NEXT_PUBLIC_API_URL=${BACKEND_URL}" \
  --config cloudbuild.frontend.yaml \
  --quiet

echo "Deploying frontend service: ${FRONTEND_SERVICE}"
gcloud run deploy "${FRONTEND_SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --image "${FRONTEND_IMAGE}" \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_API_URL=${BACKEND_URL}" \
  --quiet

FRONTEND_URL_DEPLOYED="$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format='value(status.url)')"

echo "Frontend URL: ${FRONTEND_URL_DEPLOYED}"

if [[ -z "${FRONTEND_URL:-}" ]]; then
  echo "Updating backend CORS to deployed frontend URL."
  deploy_backend "${FRONTEND_URL_DEPLOYED}"
fi

echo "Deployment complete."
echo "Backend:  ${BACKEND_URL}"
echo "Frontend: ${FRONTEND_URL_DEPLOYED}"
