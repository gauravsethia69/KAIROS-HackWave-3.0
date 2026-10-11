---
{
  "id": "evidence-terminology",
  "title": "Record and evidence terminology",
  "category": "company",
  "status": "reference",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "evidence",
    "observation",
    "hypothesis",
    "source"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Record and evidence terminology

## Observation
A recorded field value, such as projects.status = Delayed, is an observation. Its evidence includes the exact row and field. It does not automatically explain why the status occurred.

## Calculation
An aggregate or comparison is a calculation over named source records and a documented date window. Daily active users can be averaged by measured day; summing them does not yield unique users. Missing measurements remain missing, not zero.

## Uncertainty and proposed action
An unverified cause is uncertainty. A procedure or next step is a proposed action, not a historical fact. Recorded issue detail is reported as a source's description, never independently verified causation.

## Freshness and navigation
retrieved_at records when live evidence was read. Document version and heading identify reference material. Entity navigation is an internal descriptor resolved through authenticated APIs, not a fabricated URL. Generated briefs are snapshots, never authoritative updates.
