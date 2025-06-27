#!/bin/bash

# Simple deployment script for Flask apps to Google Cloud Run
# Assumes project, service account, and all files already exist

set -e  # Exit on any error

# ============================================================================
# CONFIGURATION - Update these for each project
# ============================================================================
PROJECT_ID="ingwane-ikhadi"
SERVICE_NAME="ikhadi" 
REGION="us-east1"

SERVICE_ACCOUNT_KEY="${HOME}/.gcp-keys/${PROJECT_ID}-key.json"

# ============================================================================
# DEPLOYMENT SCRIPT - No changes needed below
# ============================================================================

# Colours
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${YELLOW}📋 $1 ${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1 ${NC}"
}

print_error() {
    echo -e "${RED}❌ $1 ${NC}"
}

# Validate prerequisites
print_status "Validating prerequisites..."

# SECRET KEY
filename="$HOME/.flask_secret_key"
if [ ! -f ${filename} ]; then
    print_error "Required file '$filename' not found!"
    exit 1
fi
SECRET_KEY=$(head -n 1 $filename)

# Check required files exist
required_files=("app.py" "requirements.txt")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        print_error "Required file '$file' not found in current directory!"
        exit 1
    fi
done

print_success "All required files found"

# Check service account key exists
if [ ! -f "$SERVICE_ACCOUNT_KEY" ]; then
    print_error "Service account key not found: $SERVICE_ACCOUNT_KEY"
    print_error "Please ensure the service account key exists"
    exit 1
fi

# Authenticate with Google Cloud
print_status "Authenticating with Google Cloud..."
gcloud auth activate-service-account --key-file="$SERVICE_ACCOUNT_KEY"
gcloud config set project "$PROJECT_ID"

# Verify project exists and is accessible
if ! gcloud projects describe "$PROJECT_ID" &>/dev/null; then
    print_error "Project '$PROJECT_ID' not found or not accessible"
    print_error "Please verify the project exists and service account has access"
    exit 1
fi

print_success "Authentication successful, project verified"

# Check if required APIs are enabled
print_status "Checking required APIs..."

required_apis=("cloudbuild.googleapis.com" "run.googleapis.com" "artifactregistry.googleapis.com")

for api in "${required_apis[@]}"; do
    if gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "${api}"; then
        print_success "${api} is enabled"
    else
        print_error "${api} is not enabled"
        print_error "Enable it with: gcloud services enable $api --project=${PROJECT_ID}"
        exit 1
    fi
done

print_success "Required API's are enabled"

# Deploy to Cloud Run
print_status "Deploying '$SERVICE_NAME' to Cloud Run..."

if gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --max-instances 1 \
    --memory 256Mi \
    --timeout 300 \
    --set-env-vars SECRET_KEY="$SECRET_KEY" \
    --quiet; then
    
    print_success "Deployment completed successfully!"
    
    # Get and display service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --format="value(status.url)")
    
    print_success "Service available at: $SERVICE_URL"
    
    
    # Save URL for reference
    echo "$SERVICE_URL" > last_deployment_url.txt
    print_status "Service URL saved to: last_deployment_url.txt"
    
else
    print_error "Deployment failed!"
    exit 1
fi

# Get version number
if [ ! -f "version.py" ]; then
    version=""
else
    version=$(cat version.py | grep "__version__" | cut -d" " -f3 | tr -d '"')
fi

print_success "${version} Deployment complete!"

#EOF