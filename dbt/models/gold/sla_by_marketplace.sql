-- Gold: SLA metrics per marketplace — median and p95 time from created to synced.
{{
    config(
        materialized='table',
        dataset='gold',
        contract={'enforced': true}
    )
}}

WITH synced AS (
    SELECT
        marketplace,
        TIMESTAMP_DIFF(last_sync_at, created_at, SECOND) AS sync_seconds
    FROM {{ ref('orders_normalized') }}
    WHERE last_sync_at IS NOT NULL
      AND status IN ('confirmed', 'shipped', 'delivered')
)

SELECT
    marketplace,
    COUNT(*)                                            AS total_synced,
    ROUND(AVG(sync_seconds), 1)                         AS avg_sync_seconds,
    ROUND(APPROX_QUANTILES(sync_seconds, 100)[OFFSET(50)], 1)  AS p50_sync_seconds,
    ROUND(APPROX_QUANTILES(sync_seconds, 100)[OFFSET(95)], 1)  AS p95_sync_seconds,
    ROUND(MAX(sync_seconds), 1)                         AS max_sync_seconds
FROM synced
GROUP BY marketplace
