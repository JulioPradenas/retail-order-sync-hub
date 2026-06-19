variable "project_id" {
  type        = string
  description = "GCP project that owns the Pub/Sub topics, service accounts and secrets."
}

variable "region" {
  type        = string
  description = "Default region for regional resources."
  default     = "us-central1"
}

# Topic / subscription names mirror src/common/config.py defaults so the app
# needs no code change between emulator (V1) and real Pub/Sub (V2).
variable "topic_events" {
  type    = string
  default = "marketplace.events"
}

variable "sub_events" {
  type    = string
  default = "marketplace.events.sub"
}

variable "topic_dlq" {
  type    = string
  default = "marketplace.dlq"
}

variable "sub_dlq" {
  type    = string
  default = "marketplace.dlq.sub"
}

variable "topic_sync_dlq" {
  type    = string
  default = "marketplace.sync.dlq"
}

variable "sub_sync_dlq" {
  type    = string
  default = "marketplace.sync.dlq.sub"
}

# How many delivery attempts before a message is forwarded to the dead-letter topic.
variable "max_delivery_attempts" {
  type    = number
  default = 5
}
