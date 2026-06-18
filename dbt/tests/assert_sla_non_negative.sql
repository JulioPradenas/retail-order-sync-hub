-- Fails if any marketplace has a negative p50 sync time (data integrity check).
SELECT marketplace, p50_sync_seconds
FROM {{ ref('sla_by_marketplace') }}
WHERE p50_sync_seconds IS NOT NULL
  AND p50_sync_seconds < 0
