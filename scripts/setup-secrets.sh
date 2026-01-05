#!/bin/bash
# Setup secrets in Google Cloud Secret Manager for Cloud Run
# Usage: ./scripts/setup-secrets.sh [PROJECT_ID]

set -e

PROJECT_ID="${1:-$(gcloud config get-value project)}"

echo "🔐 Setting up secrets in Secret Manager for project: ${PROJECT_ID}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. You'll need to provide values manually."
    echo ""
fi

# Function to create or update a secret
create_secret() {
    local secret_name=$1
    local description=$2
    local env_var=$3
    
    if [ -f .env ] && grep -q "^${env_var}=" .env; then
        local secret_value=$(grep "^${env_var}=" .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
        echo "📝 Creating/updating secret: ${secret_name}"
        echo "${secret_value}" | gcloud secrets create "${secret_name}" \
            --data-file=- \
            --project="${PROJECT_ID}" \
            --replication-policy="automatic" \
            2>/dev/null || \
        echo "${secret_value}" | gcloud secrets versions add "${secret_name}" \
            --data-file=- \
            --project="${PROJECT_ID}"
    else
        echo "⚠️  Secret ${secret_name} not found in .env. Creating empty secret."
        echo "   Please update it manually:"
        echo "   echo -n 'your-value' | gcloud secrets versions add ${secret_name} --data-file=- --project=${PROJECT_ID}"
        echo ""
    fi
}

# Create secrets
create_secret "supabase-url" "Supabase project URL" "SUPABASE_URL"
create_secret "supabase-secret-key" "Supabase secret key" "SUPABASE_SECRET_KEY"
create_secret "supabase-signing-key-jwk" "Supabase signing key JWK" "SUPABASE_SIGNING_KEY_JWK"
create_secret "openai-api-key" "OpenAI API key" "OPENAI_API_KEY"
create_secret "pinecone-api-key" "Pinecone API key" "PINECONE_API_KEY"
create_secret "pinecone-environment" "Pinecone environment" "PINECONE_ENVIRONMENT"
create_secret "stripe-secret-key" "Stripe secret API key" "STRIPE_SECRET_KEY"
create_secret "stripe-webhook-secret" "Stripe webhook signing secret" "STRIPE_WEBHOOK_SECRET"
create_secret "stripe-publishable-key" "Stripe publishable key" "STRIPE_PUBLISHABLE_KEY"

echo ""
echo "✅ Secrets setup complete!"
echo ""
echo "📋 To grant Cloud Run access to these secrets, run:"
echo ""
echo "   gcloud secrets add-iam-policy-binding supabase-url \\"
echo "     --member='serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com' \\"
echo "     --role='roles/secretmanager.secretAccessor' \\"
echo "     --project=${PROJECT_ID}"
echo ""
echo "   (Repeat for each secret, or use the compute service account)"
echo ""
echo "   To find your project number:"
echo "   gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)'"

