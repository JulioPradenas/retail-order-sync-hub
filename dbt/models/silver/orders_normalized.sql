-- Silver: deduplicated, latest-snapshot of each order.
-- One row per (marketplace, marketplace_order_id) — last updated_at wins.
{{
    config(
        materialized='table',
        dataset='silver',
        contract={'enforced': true}
    )
}}

WITH ranked AS (
    SELECT
        internal_id,
        odoo_order_id,
        marketplace,
        marketplace_order_id,
        status,
        last_sync_at,
        created_at,
        updated_at,
        ingested_at,
        ROW_NUMBER() OVER (
            PARTITION BY marketplace, COALESCE(marketplace_order_id, CAST(internal_id AS STRING))
            ORDER BY updated_at DESC, ingested_at DESC
        ) AS rn
    FROM {{ source('bronze', 'raw_orders') }}
)

SELECT
    internal_id,
    odoo_order_id,
    marketplace,
    marketplace_order_id,
    status,
    last_sync_at,
    created_at,
    updated_at,
    ingested_at
FROM ranked
WHERE rn = 1
