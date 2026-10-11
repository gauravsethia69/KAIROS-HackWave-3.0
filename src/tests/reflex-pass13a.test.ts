import { describe, expect, it } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ReflexComparison } from '../components/scheduling/ReflexComparison';
import type { ReflexResult } from '../components/scheduling/ReflexComparison';

const testData:ReflexResult = {
  status:'compared',read_only:true,source:'authorized-scheduling-preview',time_zone:'Asia/Kolkata',participants_count:2,
  candidates:[
    {label:'Requested slot',starts_at:'2026-10-20T10:00:00Z',ends_at:'2026-10-20T11:00:00Z',rank:2,recorded_clear:false,truncated:false,affected_employee_count:1,recorded_overlap_count:1,overlap_participant_hours:0.5,conflicts:[{employee_id:'e1',employee_name:'Avery',title:'Other booking',starts_at:'2026-10-20T10:30:00Z',ends_at:'2026-10-20T11:30:00Z'}],more_conflicts:false,notice:'Conflict'},
    {label:'One hour later',starts_at:'2026-10-20T11:00:00Z',ends_at:'2026-10-20T12:00:00Z',rank:1,recorded_clear:true,truncated:false,affected_employee_count:0,recorded_overlap_count:0,overlap_participant_hours:0,conflicts:[],more_conflicts:false,notice:'No recorded clash'},
  ],
  task_context:{visible_open_tasks:4,estimated_backlog_hours:18,tasks_without_estimates:1,truncated:false,notice:'Task estimates are backlog, not meetings.'},
  warning:'Not a reservation. Fresh review and confirmation required.',
};

describe('Reflex decisions are visible but never automatically written', () => {
  it('ranks the recorded-clear alternative first and shows evidence caveats', () => {
    const html=renderToStaticMarkup(createElement(ReflexComparison,{data:testData,onChoose:()=>{}}));
    expect(html.indexOf('One hour later')).toBeLessThan(html.indexOf('Requested slot'));
    expect(html).toContain('No recorded clash');
    expect(html).toContain('Other booking');
    expect(html).toContain('18');
    expect(html).toContain('Not a reservation');
    expect(html).toContain('Use this time in form');
    expect(html).not.toContain('Confirm &amp; create meeting');
  });
});
