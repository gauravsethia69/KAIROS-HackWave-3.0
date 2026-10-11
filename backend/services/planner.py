"""Bounded local planning; capability weights are shared with the existing TS planner."""
import json
import re
from pathlib import Path

from ..schemas import WorkspacePlan

CATALOG = json.loads((Path(__file__).resolve().parents[2] / 'src/ai/capabilities.json').read_text(encoding='utf-8'))
CLIENT_OPTIONS = ['Investigate Acme Corp usage', 'Investigate Nova Studio usage']
MEETING_OPTIONS = ['Prepare for Acme Corp meeting', 'Prepare for Nova Studio meeting']
GOALS = [MEETING_OPTIONS[0], CLIENT_OPTIONS[0], 'Review projects falling behind schedule']


def compose(intent='overview', entities=None, filters=None):
    entities = entities or []
    names = ' & '.join('Acme Corp' if e == 'acme' else 'Nova Studio' for e in entities)
    titles = {'overview': 'A little clarity. A lot of possibility.', 'meeting': 'Ready for your next conversation' + (f' with {names}' if names else ''), 'usage': 'Understand what changed' + (f' at {names}' if names else ''), 'projects': 'Bring delivery back on track' + (f' · {names}' if names else '')}
    selected = sorted((c for c in CATALOG if c['weights'][intent] > 0), key=lambda c: -c['weights'][intent])
    layout = [dict(id=f"{c['type']}-{c['selector']}", type=c['type'], selector=c['selector'], title='Project portfolio' if intent == 'overview' and c['type'] == 'ProjectProgress' else c['title'], priority=c['weights'][intent], order=i,
                   size='wide' if c['type'] == 'MetricCards' or i == 0 else 'small' if c['type'] == 'ClientProfile' else 'medium', reason=c['reason']) for i, c in enumerate(selected)]
    return WorkspacePlan.model_validate(dict(schemaVersion=1, intent=intent, title=titles[intent], selectedEntityIds=entities,
        filters=filters or {'days': 30, 'unresolvedOnly': False, 'compare': False}, layout=layout,
        explanations=[f'Recognized goal: {intent}.', f'Scope: {names or "all available clients"}. Widgets ranked by relevance.']))


def clarify(previous, question, options):
    data = previous.model_dump(exclude_none=True)
    data['clarification'] = {'question': question, 'options': options}
    return WorkspacePlan.model_validate(data)


def classify(q):
    if re.search(r'project|behind|schedule|deadline|overdue|delivery', q) and not re.search(r'meeting|training', q):
        return 'projects'
    if re.search(r'usage|adoption|active users|engagement|product activity|drop|declin', q):
        return 'usage'
    if re.search(r'meeting|brief|prepare|catch.?up|client call|review with|talk to', q):
        return 'meeting'
    if re.search(r'overview|dashboard|start over|home', q):
        return 'overview'
    return None


def transform(q, previous):
    data = previous.model_dump(exclude_none=True)
    data.pop('clarification', None)
    layout, filters = data['layout'], data['filters']
    change = ''
    if match := re.search(r'last\s+(\d+)\s+days?', q):
        days = int(match[1])
        if days not in (7, 14, 30):
            return clarify(previous, 'Choose an available date window.', [f'Show only the last {d} days' for d in (7, 14, 30)])
        filters['days'] = days
        change = f'Date window changed to the last {days} days; client and goal retained.'
    elif re.search(r'\b(move|put|bring)\b.*\b(chart|graph)\b.*\b(top|first)\b', q):
        chart = next((w for w in layout if w['type'] == 'UsageChart'), None)
        if not chart:
            return clarify(previous, 'There is no usage chart here. Which client should we investigate?', CLIENT_OPTIONS)
        chart['size'] = 'wide'
        data['layout'] = [chart] + [w for w in layout if w['id'] != chart['id']]
        change = 'Product adoption moved to the top of the workspace.'
    elif re.search(r'\btable\b', q):
        target = next((selector for pattern, selector in [(r'issues?', 'issues'), (r'tasks?', 'tasks'), ('project', 'projects'), ('usage|chart', 'usage')] if re.search(pattern, q)), None)
        target = target or {'usage': 'usage', 'projects': 'projects'}.get(previous.intent)
        if not target:
            return clarify(previous, 'Which information would you like as a table?', ['Show issues as a table', 'Show tasks as a table', 'Show usage as a table'])
        widget = next((w for w in layout if w['selector'] == target and w['type'] != 'MetricCards'), None)
        if not widget:
            return clarify(previous, 'That information is not in this workspace. Choose a goal.', GOALS)
        widget.update(type='DataTable', title=f'{target.title()} · table', size='wide', reason=f'The same {target} records are shown as a table at your request.')
        change = f'Changed {target} to a table; filters and entity selection retained.'
    elif re.search('unresolved|open issues', q):
        filters['unresolvedOnly'] = True
        widget = next((w for w in layout if w['selector'] == 'issues'), None) or dict(id='IssuePanel-issues', type='IssuePanel', title='Unresolved issues', selector='issues', priority=10, order=0, size='wide', reason='You asked to focus on unresolved issues.')
        widget['size'] = 'wide'
        data['layout'] = [widget] + [w for w in layout if w['id'] != widget['id']]
        change = 'Resolved issues hidden; unresolved issues prioritized.'
    elif re.search('compare|previous period', q):
        if not any(w['selector'] == 'usage' for w in layout):
            return clarify(previous, 'Period comparison is available for usage. Choose a client.', CLIENT_OPTIONS)
        filters['compare'] = True
        change = f"Added the preceding {filters['days']}-day period for comparison."
    elif re.search('reset filters|clear filters', q):
        data['filters'] = {'days': 30, 'unresolvedOnly': False, 'compare': False}
        change = 'Filters reset; goal and client retained.'
    else:
        return None
    for i, widget in enumerate(data['layout']):
        widget['order'] = i
    data['explanations'] = [previous.explanations[0], change]
    return WorkspacePlan.model_validate(data)


def local_plan(text, previous):
    q = text.lower().strip()
    mentioned = [e for e in ('acme', 'nova') if e in q]
    intent = classify(q)
    if not mentioned and not re.search('investigate|prepare|review projects|why .*drop|why .*declin', q):
        if result := transform(q, previous):
            return result
    if not intent and mentioned and previous.clarification:
        option = next((o for o in previous.clarification.options if mentioned[0] in o.lower()), None)
        if option:
            return local_plan(option, previous.model_copy(update={'clarification': None}))
    if not intent and mentioned and previous.intent != 'overview' and 'compare' not in q:
        return compose(previous.intent, mentioned, previous.filters.model_dump())
    if not intent:
        return clarify(previous, 'What would you like to accomplish?', GOALS)
    if intent == 'overview':
        return compose()
    if not mentioned and re.search(r'\b(?:with|at)\s+(?!the\b|my\b|our\b)[a-z]', q):
        return clarify(previous, 'Only Acme Corp and Nova Studio are available. Which client should I use?', MEETING_OPTIONS if intent == 'meeting' else CLIENT_OPTIONS)
    if len(mentioned) > 1 and intent == 'meeting':
        return clarify(previous, 'Which client meeting should I prepare?', MEETING_OPTIONS)
    entities = mentioned or ([] if intent == 'projects' else previous.selectedEntityIds)
    if intent in ('meeting', 'usage') and not entities:
        return clarify(previous, 'Which client should this workspace focus on?', MEETING_OPTIONS if intent == 'meeting' else CLIENT_OPTIONS)
    plan = compose(intent, entities, previous.filters.model_dump())
    plan.explanations.append(f'Workspace recomposed from {previous.intent} to {intent}; {len(plan.layout)} relevant widgets selected.')
    return plan
