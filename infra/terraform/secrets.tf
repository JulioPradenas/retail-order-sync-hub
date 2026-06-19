# Secret Manager secrets for the HMAC webhook keys. Terraform creates the secret
# containers; the actual values are added out-of-band so they never touch state:
#   echo -n "$VALUE" | gcloud secrets versions add PARIS_API_SECRET --data-file=-
#
# Secret ids match SECRET_MANAGER_SECRETS in the Cloud Run service (UPPER_SNAKE).

resource "google_secret_manager_secret" "paris_api_secret" {
  secret_id = "PARIS_API_SECRET"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "ml_webhook_secret" {
  secret_id = "ML_WEBHOOK_SECRET"

  replication {
    auto {}
  }
}
