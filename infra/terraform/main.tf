terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- Topics ------------------------------------------------------------------

resource "google_pubsub_topic" "events" {
  name = var.topic_events
}

# Dead-letter sink for poison events that exceed max_delivery_attempts.
resource "google_pubsub_topic" "dlq" {
  name = var.topic_dlq
}

# Outbox worker publishes here when a marketplace push fails after all retries.
resource "google_pubsub_topic" "sync_dlq" {
  name = var.topic_sync_dlq
}

# --- Subscriptions -----------------------------------------------------------

resource "google_pubsub_subscription" "events" {
  name  = var.sub_events
  topic = google_pubsub_topic.events.id

  ack_deadline_seconds = 30

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "300s"
  }

  # GCP-managed dead-lettering: after N failed deliveries, forward to the DLQ topic.
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = var.max_delivery_attempts
  }
}

resource "google_pubsub_subscription" "dlq" {
  name  = var.sub_dlq
  topic = google_pubsub_topic.dlq.id

  ack_deadline_seconds = 60
}

resource "google_pubsub_subscription" "sync_dlq" {
  name  = var.sub_sync_dlq
  topic = google_pubsub_topic.sync_dlq.id

  ack_deadline_seconds = 60
}

# Pub/Sub needs permission to publish into the dead-letter topic and to ack the
# source subscription on its own behalf. Grant it to the GCP-managed agent SA.
data "google_project" "current" {}

locals {
  pubsub_agent = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.dlq.id
  role   = "roles/pubsub.publisher"
  member = local.pubsub_agent
}

resource "google_pubsub_subscription_iam_member" "events_subscriber_for_dl" {
  subscription = google_pubsub_subscription.events.id
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_agent
}
