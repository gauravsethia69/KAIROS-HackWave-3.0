from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Entity = Literal['acme', 'nova']
Component = Literal['ClientProfile', 'MeetingBrief', 'UsageChart', 'MetricCards', 'ActivityTimeline', 'TaskList', 'ProjectProgress', 'IssuePanel', 'DataTable', 'InsightPanel']
Selector = Literal['clients', 'meetings', 'communications', 'usage', 'tasks', 'projects', 'issues', 'insights', 'activity']
BINDINGS = {
    'ClientProfile': ['clients'], 'MeetingBrief': ['meetings'], 'UsageChart': ['usage'], 'MetricCards': ['usage'],
    'ActivityTimeline': ['activity', 'communications', 'meetings'], 'TaskList': ['tasks'], 'ProjectProgress': ['projects'],
    'IssuePanel': ['issues'], 'DataTable': ['usage', 'tasks', 'projects', 'issues', 'communications', 'meetings', 'clients'], 'InsightPanel': ['insights'],
}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Filters(Strict):
    days: Literal[7, 14, 30]
    unresolvedOnly: bool
    compare: bool


class Widget(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', max_length=64)
    type: Component
    title: str = Field(min_length=1, max_length=100)
    selector: Selector
    priority: int = Field(ge=1, le=10)
    size: Literal['small', 'medium', 'wide']
    order: int = Field(ge=0, le=30)
    reason: str = Field(min_length=1, max_length=500)


class Clarification(Strict):
    question: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=4)

    @model_validator(mode='after')
    def bounded_options(self):
        if any(not 1 <= len(o) <= 160 for o in self.options):
            raise ValueError('Invalid clarification option length')
        return self


class WorkspacePlan(Strict):
    schemaVersion: Literal[1]
    intent: Literal['overview', 'meeting', 'usage', 'projects']
    title: str = Field(min_length=1, max_length=140)
    selectedEntityIds: list[Entity] = Field(max_length=2)
    filters: Filters
    layout: list[Widget] = Field(min_length=1, max_length=12)
    explanations: list[str] = Field(min_length=1, max_length=16)
    clarification: Clarification | None = None

    @model_validator(mode='after')
    def compatible(self):
        if len({w.id for w in self.layout}) != len(self.layout):
            raise ValueError('Instance IDs must be unique')
        if any(w.selector not in BINDINGS[w.type] for w in self.layout):
            raise ValueError('Unsupported component binding')
        if any(len(e) > 500 for e in self.explanations):
            raise ValueError('Explanation too long')
        return self


class PlanRequest(Strict):
    input: str = Field(min_length=1, max_length=2000)
    previous: WorkspacePlan
    use_ai: bool = False


class PlanResponse(Strict):
    plan: WorkspacePlan
    source: Literal['live', 'deterministic', 'fallback']
    message: str


class SessionCreate(Strict):
    plan: WorkspacePlan


class SessionRecord(BaseModel):
    id: UUID
    title: str
    plan: WorkspacePlan
    created_at: datetime


class Client(BaseModel):
    id: str
    name: str
    sector: str
    contact: str
    email: str
    owner: str
    plan: str
    seats: int
    health: str


class Meeting(BaseModel):
    id: str
    client_id: str
    title: str
    date: date
    summary: str
    attendees: str
    upcoming: bool


class Usage(BaseModel):
    id: str
    client_id: str
    date: date
    active_users: int
    sessions: int
    errors: int


class Project(BaseModel):
    id: str
    client_id: str
    name: str
    owner: str
    progress: int
    expected: int
    due_date: date
    status: str


class Task(BaseModel):
    id: str
    client_id: str
    project_id: str
    title: str
    owner: str
    due_date: date
    status: str
    priority: str


class Communication(BaseModel):
    id: str
    client_id: str
    date: date
    author: str
    channel: str
    message: str


class Issue(BaseModel):
    id: str
    client_id: str
    project_id: str
    title: str
    date: date
    status: str
    severity: str
    owner: str
    detail: str
