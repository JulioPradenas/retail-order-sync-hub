-- Fails if webhooks_received or orders_created is negative.
SELECT date, marketplace, webhooks_received, orders_created
FROM {{ ref('daily_throughput') }}
WHERE webhooks_received < 0
   OR orders_created < 0
