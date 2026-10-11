from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..schemas import Component, BINDINGS

EntityKind = Literal['employee', 'department', 'client', 'product', 'project', 'task', 'issue', 'meeting', 'contract', 'communication', 'usage', 'schedule', 'activity']
IntentName = Literal['client_meeting_prep', 'product_usage_investigation', 'project_delivery_review', 'support_incident_command', 'team_workload_planning', 'executive_briefing', 'ownership_lookup', 'entity_lookup', 'unsupported']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class EntityRef(Strict):
    entity_type: EntityKind
    entity_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')


class Navigation(Strict):
    kind: Literal['entity_detail', 'knowledge_document']
    entity: EntityRef | None = None
    document_id: str | None = Field(default=None, pattern=r'^[a-z0-9-]+$', max_length=100)
    section: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def target(self):
        if self.kind == 'entity_detail' and (not self.entity or self.document_id):
            raise ValueError('Entity navigation requires only an entity')
        if self.kind == 'knowledge_document' and (not self.document_id or self.entity):
            raise ValueError('Document navigation requires only a document ID')
        return self


class Evidence(Strict):
    id: str
    source_type: Literal['database', 'document']
    source_table: str | None = None
    entity: EntityRef | None = None
    document_id: str | None = None
    title: str
    field: str
    retrieved_at: datetime
    navigation: Navigation


class Claim(Strict):
    kind: Literal['observation', 'calculation', 'uncertainty', 'proposed_action']
    text: str
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def grounded(self):
        if self.kind in ('observation', 'calculation') and not self.evidence_ids:
            raise ValueError('Factual statements require evidence')
        return self


class Candidate(Strict):
    entity: EntityRef
    label: str
    score: float = Field(ge=0, le=1)


class Clarification(Strict):
    question: str
    candidates: list[Candidate] = Field(default_factory=list, max_length=10)
    suggestions: list[str] = Field(default_factory=list, max_length=6)


class IntentRequest(Strict):
    input: str = Field(min_length=1, max_length=2000)
    context_token: str | None = Field(default=None, max_length=200)
    selection: EntityRef | None = None


class ResolvedIntent(Strict):
    name: IntentName
    confidence: float = Field(ge=0, le=1)
    entities: list[EntityRef] = Field(default_factory=list, max_length=10)
    date_from: date | None = None
    date_to: date | None = None
    blocked_only: bool = False
    unresolved_only: bool = False
    overdue_only: bool = False
    compare: bool = False
    presentation: Literal['default', 'table'] = 'default'
    chart_first: bool = False
    clarification: Clarification | None = None
    changes: list[str] = Field(default_factory=list)


class BoundProps(Strict):
    selector: Literal['clients', 'meetings', 'communications', 'usage', 'tasks', 'projects', 'issues', 'insights', 'activity']
    record_ids: list[str] = Field(max_length=250)
    binding: Literal['response.datasets'] = 'response.datasets'


class ComponentPlan(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]+$')
    type: Component
    title: str
    priority: int = Field(ge=1, le=10)
    order: int = Field(ge=0, le=20)
    size: Literal['small', 'medium', 'wide']
    props: BoundProps
    evidence_ids: list[str]
    reason: str

    @model_validator(mode='after')
    def binding_matches(self):
        if self.props.selector not in BINDINGS[self.type]:
            raise ValueError('Unsupported widget binding')
        return self


class Workspace(Strict):
    schemaVersion: Literal[2] = 2
    source: Literal['deterministic-enterprise'] = 'deterministic-enterprise'
    status: Literal['ready', 'partial', 'clarification', 'not_found', 'unsupported']
    title: str
    intent: ResolvedIntent
    context_token: str | None = None
    components: list[ComponentPlan] = Field(max_length=12)
    datasets: dict[str, list[dict]]
    evidence: list[Evidence]
    claims: list[Claim]
    explanations: list[str]
    limitations: list[str]
    integration_requirements: list[str]

    @model_validator(mode='after')
    def references(self):
        evidence = {e.id for e in self.evidence}
        if len(evidence) != len(self.evidence) or len({c.id for c in self.components}) != len(self.components):
            raise ValueError('Duplicate component or evidence IDs')
        for component in self.components:
            available = {str(r.get('id')) for r in self.datasets.get(component.props.selector, [])}
            if not set(component.props.record_ids) <= available:
                raise ValueError('Widget references absent records')
        if any(not set(item.evidence_ids) <= evidence for item in [*self.components, *self.claims]):
            raise ValueError('Unresolved evidence reference')
        return self
