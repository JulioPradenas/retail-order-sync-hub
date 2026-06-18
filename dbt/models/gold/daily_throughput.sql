-- Gold: daily event and order throughput.
{{
    config(
        materialized='table',
        dataset='gold',
        contract={'enforced': true}
    )
}}

WITH events AS (
    SELECT
        DATE(received_at) AS event_date,
        source,
        COUNT(*)          AS event_count
    FROM {{ ref('events_normalized') }}
    GROUP BY event_date, source
),

orders AS (
    SELECT
        DATE(created_at) AS order_date,
        marketplace,
        COUNT(*)         AS order_count
    FROM {{ ref('orders_normalized') }}
    GROUP BY order_date, marketplace
)

SELECT
    COALESCE(e.event_date, o.order_date)   AS date,
    COALESCE(e.source, o.marketplace)      AS marketplace,
    COALESCE(e.event_count, 0)             AS webhooks_received,
    COALESCE(o.order_count, 0)             AS orders_created
FROM events e
FULL OUTER JOIN orders o
    ON e.event_date = o.order_date AND e.source = o.marketplace
ORDER BY date DESC, marketplace
