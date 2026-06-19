# Two service accounts with least privilege:
#   - webhook-receiver: only publishes events + reads its HMAC secrets (Cloud Run).
#   - subscriber-worker: only consumes the events subscription.

resource "google_service_account" "webhook_receiver" {
  account_id   = "webhook-receiver"
  display_name = "ROSH webhook receiver (Cloud Run)"
}

resource "google_service_account" "subscriber_worker" {
  account_id   = "subscriber-worker"
  display_name = "ROSH subscriber/reconciler worker"
}

# Receiver publishes to the events topic only (not DLQ, not sync_dlq).
resource "google_pubsub_topic_iam_member" "receiver_publish_events" {
  topic  = google_pubsub_topic.events.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.webhook_receiver.email}"
}

# Outbox worker also publishes the sync-failure DLQ; it shares the subscriber SA.
resource "google_pubsub_topic_iam_member" "worker_publish_sync_dlq" {
  topic  = google_pubsub_topic.sync_dlq.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.subscriber_worker.email}"
}

# Subscriber consumes events (and the DLQ subscription for replay tooling).
resource "google_pubsub_subscription_iam_member" "worker_consume_events" {
  subscription = google_pubsub_subscription.events.id
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.subscriber_worker.email}"
}

resource "google_pubsub_subscription_iam_member" "worker_consume_dlq" {
  subscription = google_pubsub_subscription.dlq.id
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.subscriber_worker.email}"
}

# Receiver reads its HMAC secrets from Secret Manager.
resource "google_secret_manager_secret_iam_member" "receiver_paris_secret" {
  secret_id = google_secret_manager_secret.paris_api_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.webhook_receiver.email}"
}

resource "google_secret_manager_secret_iam_member" "receiver_ml_secret" {
  secret_id = google_secret_manager_secret.ml_webhook_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.webhook_receiver.email}"
}
