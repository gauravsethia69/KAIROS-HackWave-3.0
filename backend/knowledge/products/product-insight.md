---
{
  "id": "product-insight",
  "title": "Soryu Insight",
  "category": "products",
  "status": "reference",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "Soryu Insight",
    "insight",
    "Analytics"
  ],
  "sources": [
    "products:insight:description",
    "products:insight:category",
    "products:insight:lifecycle"
  ],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Soryu Insight

## Verified product record
Record: products/insight. Category: Analytics. Description: Product analytics, adoption and executive insights. Lifecycle was Active at the read-only inspection on 2026-10-11. Live PostgreSQL supersedes this snapshot if these fields change.

## Relational context
client_products connects subscriptions to clients. product_usage contains dated active_users, sessions and errors. Projects, meetings, communications and issues carry product_id. contracts references the client/product pair; use contract_owner_id for accountability. These relationships do not establish a root cause or product SLA by themselves.

## Proposed investigation
Filter to the selected client and product before comparing usage periods. Review product-linked issues and communications alongside the trend. Report a coincident incident as context, not proven causation. If no measurements are visible, report missing evidence rather than drawing an adoption conclusion.
