-- Gold: orders stuck in pending/cancelled without a last_sync_at — DLQ root cause proxy.
-- These are orders that were created but never successfully synced to a marketplace.
{{
    config(
        materialized='table',
        dataset='gold',
        contract={'enforced': true}
    )
}}

SELECT
    marketplace,
    status,
    COUNT(*)                                AS stuck_orders,
    MIN(created_at)                         AS oldest_stuck_at,
    MAX(created_at)                         AS newest_stuck_at,
    TIMESTAMP_DIFF(
        CURRENT_TIMESTAMP(), MIN(created_at), HOUR
    )                                       AS max_age_hours
FROM {{ ref('orders_normalized') }}
WHERE last_sync_at IS NULL
  AND status IN ('pending', 'cancelled')
GROUP BY marketplace, status
ORDER BY stuck_orders DESC
