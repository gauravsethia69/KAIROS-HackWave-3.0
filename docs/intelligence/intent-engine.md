# Deterministic intent and context

`resolve_intent` consumes `IntentRequest`, the verified identity and visible snapshot. Its normalized output is independent of any model provider. A future separately authorized adapter can produce `ResolvedIntent`; downstream responsibility and composition must still revalidate visible entity IDs.

Supported primary intents:

| Intent | Example |
| --- | --- |
| `client_meeting_prep` | Prepare for tomorrow's OrbitPay client meeting |
| `product_usage_investigation` | Investigate Soryu Insight adoption for this client |
| `project_delivery_review` | Why is Atlas Media Group's reporting project delayed? |
| `support_incident_command` | Summarize urgent support incidents |
| `team_workload_planning` | Show Engineering team workload |
| `executive_briefing` | Prepare a leadership briefing |

`ownership_lookup` handles recorded owner/blocker questions. `entity_lookup` handles assigned work and entity records. Unsupported goals return `unsupported`, not fabricated answers. Classification uses explicit English patterns. Confidence is a heuristic strength, not a calibrated probability.

Names are matched against visible rows using normalized full names, corporate suffix/product-prefix aliases, meaningful partial tokens and conservative word similarity. Exact IDs are supported; human-readable IDs embedded in an ambiguous name cannot override competing names. Competing matches return actual candidates (at most ten). A missing explicit selection returns 404. Meeting requests without a selected client ask for clarification. Broad project/usage requests can intentionally return multiple visible entities; callers should use `selection` to guarantee a particular scope.

## Context protocol

POST either intent or workspace endpoint with `{"input":"Prepare for an OrbitPay meeting"}`. Retain the returned opaque `context_token`. Follow with `{"input":"Investigate usage for this client","context_token":"<returned token>"}`. The client remains selected while meeting components disappear. Send `selection:{"entity_type":"client","entity_id":"<candidate ID>"}` with the original request to answer a clarification.

The token stores only normalized intent, bound to both verified Auth UUID and employee ID. It expires after 15 minutes; the process holds at most 500 contexts. An expired, unknown or different user's token returns 404. Omit the token for a fresh goal. This is an extension of the existing request-context approach, not a background Reflex agent. Restarts discard tokens; multiple workers would require sticky routing or a separately approved shared store.

Supported follow-ups include switching client, narrowing to a project, blocked work, unresolved issues, overdue tasks, last N days, previous-period comparison, table presentation and chart-first order where applicable. Changing goals recomposes components rather than retaining irrelevant widgets. "My" resolves from authorized membership; "my team" resolves its recorded department. Filters persist within a continued goal; start without a token to clear them.

Dates use Asia/Kolkata server time: today, tomorrow, next week (next seven days), last week (ending today), last 1–90 days. Unsupported named weekdays/month windows ask for clarification. This is not general natural-language understanding. No timezone or date is inferred from an LLM.
