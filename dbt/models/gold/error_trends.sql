-- Gold: daily error and cancellation trends per marketplace.
{{
    config(
        materialized='table',
        dataset='gold',
        contract={'enforced': true}
    )
}}

SELECT
    DATE(created_at)        AS order_date,
    marketplace,
    COUNT(*)                AS total_orders,
    COUNTIF(status = 'cancelled')   AS cancelled,
    ROUND(
        SAFE_DIVIDE(COUNTIF(status = 'cancelled'), COUNT(*)) * 100, 2
    )                               AS cancellation_rate_pct
FROM {{ ref('orders_normalized') }}
GROUP BY order_date, marketplace
ORDER BY order_date DESC, marketplace
