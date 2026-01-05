#!/bin/bash
# Deploy to Google Cloud Run
# Usage: ./scripts/deploy-cloud-run.sh [SERVICE_NAME] [REGION] [PROJECT_ID]
# 
# Environment variables:
#   USE_SECRETS: Set to "true" to use Secret Manager (default: false, uses env vars from .env)
#   MIN_INSTANCES, MAX_INSTANCES, CPU, MEMORY, TIMEOUT, CONCURRENCY: Cloud Run configuration

set -e

# Configuration
SERVICE_NAME="${1:-autopilot-api}"
REGION="${2:-us-central1}"
PROJECT_ID="${3:-$(gcloud config get-value project)}"
REPOSITORY="${REPOSITORY:-docker-repo}"
# Use Artifact Registry format: LOCATION-docker.pkg.dev/PROJECT_ID/REPOSITORY/IMAGE
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
MAX_INSTANCES="${MAX_INSTANCES:-10}"
CPU="${CPU:-1}"
MEMORY="${MEMORY:-512Mi}"
TIMEOUT="${TIMEOUT:-300}"
CONCURRENCY="${CONCURRENCY:-80}"
USE_SECRETS="${USE_SECRETS:-false}"

echo "🚀 Deploying to Cloud Run..."
echo "   Service: ${SERVICE_NAME}"
echo "   Region: ${REGION}"
echo "   Project: ${PROJECT_ID}"
echo "   Repository: ${REPOSITORY}"
echo "   Image: ${IMAGE_NAME}"

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# Ensure Artifact Registry repository exists
echo "📦 Checking Artifact Registry repository..."
if ! gcloud artifacts repositories describe "${REPOSITORY}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "   Creating Artifact Registry repository: ${REPOSITORY}"
  gcloud artifacts repositories create "${REPOSITORY}" \
    --repository-format=docker \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --description="Docker repository for ${SERVICE_NAME}"
fi

# Build and push the container image using Cloud Build
echo "📦 Building container image..."
gcloud builds submit --tag "${IMAGE_NAME}" --project "${PROJECT_ID}" --region="${REGION}"

# Prepare deployment command
DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --allow-unauthenticated \
  --min-instances ${MIN_INSTANCES} \
  --max-instances ${MAX_INSTANCES} \
  --cpu ${CPU} \
  --memory ${MEMORY} \
  --timeout ${TIMEOUT} \
  --concurrency ${CONCURRENCY} \
  --port 8080 \
  --set-env-vars APP_ENV=production,DEBUG=false,HOST=0.0.0.0"

# Add secrets or environment variables
if [ "${USE_SECRETS}" = "true" ]; then
  echo "🔐 Using Secret Manager for sensitive values..."
  DEPLOY_CMD="${DEPLOY_CMD} --update-secrets=SUPABASE_URL=supabase-url:latest,SUPABASE_SECRET_KEY=supabase-secret-key:latest,SUPABASE_SIGNING_KEY_JWK=supabase-signing-key-jwk:latest,OPENAI_API_KEY=openai-api-key:latest,PINECONE_API_KEY=pinecone-api-key:latest,PINECONE_ENVIRONMENT=pinecone-environment:latest"
else
  echo "📝 Using environment variables from .env file..."
  if [ -f .env ]; then
    # Read values from .env and add to deployment
    ENV_VARS="APP_ENV=production,DEBUG=false,HOST=0.0.0.0"
    
    while IFS='=' read -r key value; do
      # Skip comments and empty lines
      [[ "$key" =~ ^#.*$ ]] && continue
      [[ -z "$key" ]] && continue
      
      # Remove quotes from value
      value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
      
      # Add to env vars if it's one of our required variables
      case "$key" in
        SUPABASE_URL|SUPABASE_SECRET_KEY|SUPABASE_SIGNING_KEY_JWK|OPENAI_API_KEY|PINECONE_API_KEY|PINECONE_ENVIRONMENT|OPENAI_MODEL|PINECONE_INDEX_NAME|EMBEDDING_MODEL|MAX_CONTEXT_MESSAGES|CORS_ORIGINS)
          ENV_VARS="${ENV_VARS},${key}=${value}"
          ;;
      esac
    done < .env
    
    DEPLOY_CMD="${DEPLOY_CMD} --set-env-vars ${ENV_VARS}"
  else
    echo "⚠️  Warning: .env file not found. You'll need to set environment variables manually."
    echo "   Required variables: SUPABASE_URL, SUPABASE_SECRET_KEY, SUPABASE_SIGNING_KEY_JWK,"
    echo "   OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENVIRONMENT"
  fi
fi

# Deploy to Cloud Run
echo "🚢 Deploying to Cloud Run..."
eval "${DEPLOY_CMD}"

echo ""
echo "✅ Deployment complete!"
echo ""
if [ "${USE_SECRETS}" = "true" ]; then
  echo "📝 Note: Make sure secrets are set in Secret Manager and the Cloud Run service account"
  echo "   has access. Run ./scripts/setup-secrets.sh to set them up."
else
  echo "📝 Note: Environment variables were set from .env file."
  echo "   For production, consider using Secret Manager (set USE_SECRETS=true)."
fi
echo ""
echo "🌐 Service URL:"
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --format="value(status.url)"

