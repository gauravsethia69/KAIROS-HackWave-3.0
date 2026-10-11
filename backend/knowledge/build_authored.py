"""Reproducible authoring source for internal reference and proposed procedures.

Does not query the database. Product descriptions were verified read-only on
2026-10-11. Run explicitly to regenerate the version-controlled Markdown catalog.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent


def build():
    docs = []
    def add(category, slug, title, body, status='proposed', tags=(), sources=()):
        metadata = {'id': slug, 'title': title, 'category': category, 'status': status, 'version': 1,
                    'updated_at': '2026-10-11', 'tags': list(tags), 'sources': list(sources),
                    'classification': 'internal-reference', 'author': 'KAIROS implementation proposal'}
        path = ROOT / category / f'{slug}.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\n' + json.dumps(metadata, indent=2) + '\n---\n# ' + title + '\n\n' + body.strip() + '\n', encoding='utf-8')
        docs.append({'id': slug, 'path': f'{category}/{slug}.md'})

    add('company', 'soryu-overview', 'SORYU SYSTEMS company reference', '''
## Recorded system boundaries
SORYU SYSTEMS is the in-app organization. Its existing morph-ai PostgreSQL database is the authoritative source for employees, departments, clients, products, delivery work and client interactions. This reference does not establish legal corporate facts, revenue, contractual commitments or employee achievements.

## Product portfolio
The recorded products are Soryu CloudOps, Soryu Insight, Soryu Flow and Soryu Guard. Product-specific reference documents quote their verified database descriptions. Client adoption is related through client_products and product_usage; contracts relate a client/product subscription to a recorded contract owner.

## Working with evidence
Use live records for status, owner, due date and usage values. Authored reference documents explain the data model. Procedures marked proposed are recommendations awaiting company approval. A count in a bounded response describes the visible result set, not necessarily the entire business.
''', 'reference', ['company', 'soryu'], ['schema:clients', 'schema:products', 'schema:contracts'])
    add('company', 'organization-reporting', 'Organization and reporting model', '''
## Established relationships
employees.department_id references departments.id. employees.manager_id references employees.id. The seven named departments supplied for this project are Engineering, Customer Success, Product, Sales, Support, Operations and Data & Analytics. Look up actual membership rather than inferring it from a job title.

## Manager interpretation
A manager link identifies a recorded reporting relationship. It does not prove incident authority, approval rights or current availability. A missing manager is reported as missing. Cycles and absent records terminate traversal instead of manufacturing a hierarchy.

## Proposed routing
Start a delivery question with the recorded work owner. If escalation is needed, offer the recorded manager as a possible contact, explicitly as a proposed action. Do not claim that the manager caused or can resolve a blocker.
''', 'reference', ['organization', 'manager', 'department'], ['schema:employees.manager_id', 'schema:employees.department_id'])
    add('company', 'ownership-conventions', 'Responsibilities and ownership conventions', '''
## Owner fields
Projects, tasks and issues use owner_employee_id. Meetings use organizer_employee_id. Contracts use contract_owner_id. Clients use account_manager_id. These foreign keys take precedence over legacy textual owner labels. The browser cannot choose the authenticated employee ID, role or department.

## Dependencies
tasks.blocker_task_id points to a recorded prerequisite task. It is evidence of a dependency, not evidence of fault. Resolve the blocking task and its owner separately, including the case where the prerequisite is already completed.

## Gaps
No recorded owner means unknown ownership. Do not substitute a department head, meeting attendee, communication author or similarly named person. Proposed handoffs must identify an intended target and await a separately authorized write workflow.
''', 'reference', ['owner', 'responsibility', 'blocker'], ['schema:tasks.blocker_task_id', 'schema:projects.owner_employee_id'])
    add('company', 'collaboration-model', 'Cross-department collaboration model', '''
## Proposed coordination
Engineering investigates implementation failures; Support coordinates incident triage; Customer Success brings client context; Product prioritizes trade-offs; Sales checks contract ownership; Operations coordinates schedules; Data & Analytics verifies measurement definitions. These responsibilities are a proposed operating model, not newly recorded assignments.

## A traceable handoff
Attach the source task or issue ID, known status, client/product/project links, current owner and explicit uncertainty. Ask the receiving owner to acknowledge the request. A communication record is evidence that a message exists, not proof that responsibility changed.

## Shared decisions
Use recorded owners and managers for contact suggestions. Leave commitments, deadlines and staffing changes unchanged until an authorized company workflow approves them.
''', tags=['handoff', 'collaboration'])
    add('company', 'evidence-terminology', 'Record and evidence terminology', '''
## Observation
A recorded field value, such as projects.status = Delayed, is an observation. Its evidence includes the exact row and field. It does not automatically explain why the status occurred.

## Calculation
An aggregate or comparison is a calculation over named source records and a documented date window. Daily active users can be averaged by measured day; summing them does not yield unique users. Missing measurements remain missing, not zero.

## Uncertainty and proposed action
An unverified cause is uncertainty. A procedure or next step is a proposed action, not a historical fact. Recorded issue detail is reported as a source's description, never independently verified causation.

## Freshness and navigation
retrieved_at records when live evidence was read. Document version and heading identify reference material. Entity navigation is an internal descriptor resolved through authenticated APIs, not a fabricated URL. Generated briefs are snapshots, never authoritative updates.
''', 'reference', ['evidence', 'observation', 'hypothesis', 'source'])

    departments = [
      ('engineering', 'Engineering', 'implementation, testing, reliability and defect investigation', 'project tasks, assigned issues and technical activity events', 'Support for reproducible incident evidence; Product for prioritization; Operations for change windows', 'Validate reproduction steps, inspect the recorded blocking task and publish a bounded technical finding.'),
      ('customer-success', 'Customer Success', 'client outcomes, meeting preparation and adoption follow-through', 'client accounts, meetings, communications and enablement tasks', 'Support for active incidents; Sales for contract interpretation; Data & Analytics for adoption measurements', 'Prepare a client brief from the account manager link, upcoming meetings, previous commitments and unresolved issues.'),
      ('product', 'Product', 'product intent, acceptance criteria and prioritization', 'product-linked projects, tasks and product feedback', 'Engineering for effort and feasibility; Customer Success for client context; Data & Analytics for measurement', 'Separate a product decision from a delivery blocker and record the evidence needed before reprioritization.'),
      ('sales', 'Sales', 'commercial coordination and contract-owner engagement', 'contracts, client-product relationships and commercial communications', 'Customer Success for account context; Operations for delivery feasibility; recorded contract owner for terms', 'Check recorded status and renewal dates; do not infer legal obligations or promise pricing changes from this workspace.'),
      ('support', 'Support', 'incident intake, severity review and responder coordination', 'issues, related communications, SLA-hour fields and incident activity', 'Engineering for diagnosis; Customer Success for client messaging; Operations for availability', 'Group unresolved urgent issues, identify assigned responders and distinguish the recorded SLA duration from an unverified deadline.'),
      ('operations', 'Operations', 'delivery coordination, dependencies and scheduling', 'owned projects, tasks, schedule blocks and meeting logistics', 'Engineering for prerequisites; Customer Success for client scheduling; department managers for capacity decisions', 'Compare actual versus expected progress and trace recorded blockers before proposing revised work sequencing.'),
      ('data-analytics', 'Data & Analytics', 'metric definitions, usage validation and evidence synthesis', 'product_usage, analytical projects and measurement issues', 'Engineering for instrumentation; Product for success metrics; Customer Success for adoption context', 'Compare like-length periods using measured dates; inspect missing data and affected client-product combinations before suggesting causes.'),
    ]
    for slug, name, responsibility, records, dependencies, workflow in departments:
        add('departments', f'department-{slug}', f'{name} operating reference', f'''
## Status and primary responsibilities
This is a proposed operating description for {name}, not a claim that the department has accepted new work. The proposed remit is {responsibility}.

## Relevant workflow
{workflow} Start with source IDs and current ownership; distinguish completed work from open obligations.

## Records and relationships
Relevant records include {records}. Actual employees are selected by employees.department_id. Their tasks and issues follow owner_employee_id; project ownership is a separate relationship and must not be inferred from task counts.

## Dependencies
Coordinate with {dependencies}. Shared client_id, product_id and project_id relationships provide context, not implicit reassignment.

## Escalation
Propose contacting the assigned employee first, then their recorded manager if available. State missing owners or schedules explicitly. Only an approved company workflow may change an assignment or commitment.
''', tags=[name, 'department', 'workflow', 'ownership'])

    products = [('cloudops', 'Soryu CloudOps', 'Cloud Operations', 'Operational monitoring, deployment reliability and observability'), ('insight', 'Soryu Insight', 'Analytics', 'Product analytics, adoption and executive insights'), ('flow', 'Soryu Flow', 'Workflows', 'Project and work orchestration'), ('guard', 'Soryu Guard', 'Identity & Security', 'Identity administration and enterprise SSO')]
    for product_id, name, category, description in products:
        add('products', f'product-{product_id}', name, f'''
## Verified product record
Record: products/{product_id}. Category: {category}. Description: {description}. Lifecycle was Active at the read-only inspection on 2026-10-11. Live PostgreSQL supersedes this snapshot if these fields change.

## Relational context
client_products connects subscriptions to clients. product_usage contains dated active_users, sessions and errors. Projects, meetings, communications and issues carry product_id. contracts references the client/product pair; use contract_owner_id for accountability. These relationships do not establish a root cause or product SLA by themselves.

## Proposed investigation
Filter to the selected client and product before comparing usage periods. Review product-linked issues and communications alongside the trend. Report a coincident incident as context, not proven causation. If no measurements are visible, report missing evidence rather than drawing an adoption conclusion.
''', 'reference', [name, product_id, category], [f'products:{product_id}:description', f'products:{product_id}:category', f'products:{product_id}:lifecycle'])

    playbooks = [
      ('client-meeting-prep', 'Client meeting preparation', 'client meeting agenda account manager', 'Resolve client ID and the requested meeting date. If more than one client matches, ask the employee to choose.', 'Read meetings and meeting_participants, recent communications, related issues and clients.account_manager_id. Distinguish recorded agenda/summary from suggested talking points.', 'List decisions to confirm, issue owners to contact and missing records. Do not invent commitments or meeting attendance.'),
      ('usage-decline', 'Product usage decline investigation', 'usage adoption decline investigation', 'Resolve the client-product pair and an explicit date window. Compare equal-length adjacent periods.', 'Use product_usage for measured daily activity and sessions. Check issue timestamps and communications. Flag missing days and do not equate summed daily counts with unique users.', 'Separate observed change from possible factors. Propose cohort or instrumentation checks; never assign an incident as the cause solely because dates overlap.'),
      ('delayed-project', 'Delayed project review', 'project delayed delivery review', 'Resolve project and client; inspect status, progress, expected and due_date.', 'List incomplete tasks and follow blocker_task_id. Resolve both task owners and project owner by foreign key. Include recorded activity as context.', 'A Delayed status is not a diagnosis. Ask the owners to validate the critical path and an achievable recovery plan without changing dates.'),
      ('support-triage', 'Support incident triage', 'support incident urgent severity sla', 'Find unresolved High or Critical severity issues and identify their client, product and owner.', 'Read detail, sla_hours, related communications and activity. SLA hours are a recorded duration; a date without a precise start timestamp is insufficient for an exact breach claim.', 'Propose contacting the assigned responder and their recorded manager if escalation is warranted. Do not invent on-call rotations or declare root cause.'),
      ('team-workload', 'Team workload analysis', 'workload capacity schedule team department', 'Resolve department from an explicit entity or derive my team from the authenticated employee record.', 'Group open tasks by owner_employee_id. Show estimated_hours and weekly_capacity_hours separately. Clip schedule blocks to the requested period and deduplicate overlapping occupied intervals.', 'Unscheduled time is not promised availability. Missing estimates and schedule coverage make capacity partial. Any staffing or reassignment is a proposal.'),
      ('executive-briefing', 'Executive briefing generation', 'leadership executive briefing summary', 'Define the reporting window and scope; retain the viewer’s existing record permissions.', 'Read delayed projects, unresolved urgent issues, client health, upcoming meetings and contract status/renewal dates. Do not infer revenue impact or summarize confidential financial fields.', 'Present source-backed observations, uncertainty and named recorded owners. Distinguish incomplete snapshots from company-wide totals.'),
      ('blocker-escalation', 'Task blocker escalation', 'task blocker blocking escalation sso', 'Resolve the exact blocked task. Partial or duplicate titles require clarification.', 'Follow blocker_task_id until no link, missing row, cycle or the bounded depth is reached. Show prerequisite status and owner; a completed prerequisite may be a stale recorded link.', 'Offer the blocker owner and recorded manager as possible contacts. A dependency does not establish personal blame or authority to reassign work.'),
      ('ownership-handoff', 'Cross-department ownership handoff', 'handoff ownership collaboration department', 'Identify the current owner using the entity-specific employee foreign key.', 'Attach source IDs, current status, recorded dependencies, receiving team context and unresolved questions. Use communications only as evidence of recorded messages.', 'Ask the proposed receiving owner to acknowledge. This read-only system neither approves nor writes a handoff; the existing owner remains authoritative until an approved record changes.'),
    ]
    for slug, title, tags, first, evidence, action in playbooks:
        add('playbooks', f'playbook-{slug}', title, f'## Procedure status\nProposed; awaiting company approval. This procedure changes no database assignments or deadlines.\n\n## Scope\n{first}\n\n## Evidence to collect\n{evidence}\n\n## Proposed next action\n{action}\n\n## Stop conditions\nAsk for clarification on competing entity matches. Report missing/unauthorized records without guessing. On dependency outage return an explicit service error rather than a fabricated successful result.', tags=tags.split())
    (ROOT / 'manifest.json').write_text(json.dumps({'version': 1, 'documents': docs}, indent=2) + '\n', encoding='utf-8')
    print(f'Authored {len(docs)} reference/proposed documents; no database access.')

if __name__ == '__main__':
    build()
