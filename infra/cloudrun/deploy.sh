#!/usr/bin/env bash
# Build and deploy the webhook receiver to Cloud Run (V2.1).
#
# Prereqs (run once, see docs/deploy-gcp.md):
#   - gcloud auth login && gcloud auth application-default login
#   - billing enabled on the project
#   - Artifact Registry repo `rosh` created in $REGION
#   - service account + secrets provisioned (Terraform in infra/terraform)
#
# Usage:
#   PROJECT_ID=my-proj REGION=us-central1 ./infra/cloudrun/deploy.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/rosh/webhook-receiver:${IMAGE_TAG}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> Building ${IMAGE}"
gcloud builds submit "${REPO_ROOT}" \
  --tag "${IMAGE}" \
  --gcs-source-staging-dir="gs://${PROJECT_ID}_cloudbuild/source" \
  --project "${PROJECT_ID}"

echo "==> Rendering service.yaml"
RENDERED="$(mktemp)"
sed -e "s/PROJECT_ID/${PROJECT_ID}/g" \
    -e "s/REGION/${REGION}/g" \
    -e "s/IMAGE_TAG/${IMAGE_TAG}/g" \
    "${REPO_ROOT}/infra/cloudrun/service.yaml" > "${RENDERED}"

echo "==> Deploying to Cloud Run"
gcloud run services replace "${RENDERED}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}"

# Webhooks are authenticated by HMAC at the app layer, so the endpoint is public.
gcloud run services add-iam-policy-binding webhook-receiver \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --member="allUsers" \
  --role="roles/run.invoker"

URL="$(gcloud run services describe webhook-receiver \
  --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)')"
echo "==> Deployed: ${URL}"
echo "    Register ${URL}/webhooks/mercadolibre in the ML sandbox app."
