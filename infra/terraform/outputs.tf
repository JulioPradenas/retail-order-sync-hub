output "events_topic" {
  value       = google_pubsub_topic.events.id
  description = "Full resource id of the events topic."
}

output "dlq_topic" {
  value       = google_pubsub_topic.dlq.id
  description = "Dead-letter topic for poison events."
}

output "webhook_receiver_sa" {
  value       = google_service_account.webhook_receiver.email
  description = "Service account email to set on the Cloud Run service."
}

output "subscriber_worker_sa" {
  value       = google_service_account.subscriber_worker.email
  description = "Service account email for the subscriber/outbox workers."
}
