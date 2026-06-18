-- Silver: deduplicated webhook events (one row per event_id+source).
{{
    config(
        materialized='table',
        dataset='silver',
        contract={'enforced': true}
    )
}}

WITH ranked AS (
    SELECT
        id,
        event_id,
        source,
        received_at,
        ingested_at,
        ROW_NUMBER() OVER (
            PARTITION BY source, event_id
            ORDER BY received_at DESC, ingested_at DESC
        ) AS rn
    FROM {{ source('bronze', 'raw_webhooks') }}
)

SELECT
    id,
    event_id,
    source,
    received_at,
    ingested_at
FROM ranked
WHERE rn = 1
