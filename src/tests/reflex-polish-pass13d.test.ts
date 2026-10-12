/** View-only regression tests: React markup cannot create or confirm bookings. */
import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ReflexComparison } from '../components/scheduling/ReflexComparison';
import type { ReflexResult } from '../components/scheduling/ReflexComparison';

const candidate = (overrides:Partial<ReflexResult['candidates'][number]>={}):ReflexResult['candidates'][number] => ({
  label:'Requested slot', starts_at:'2026-10-20T10:00:00Z', ends_at:'2026-10-20T11:00:00Z',
  rank:2, recorded_clear:false,truncated:false, affected_employee_count:1,
  recorded_overlap_count:1,overlap_participant_hours:0.5,
  conflicts:[{employee_id:'e1',employee_name:'Anika',title:'Customer call',starts_at:'2026-10-20T10:15:00Z',ends_at:'2026-10-20T10:45:00Z'}],
  more_conflicts:false,notice:'One recorded booking',...overrides,
});
const result = (overrides:Partial<ReflexResult>={}):ReflexResult=>({
  status:'compared',read_only:true,source:'authorized-scheduling-preview',time_zone:'Asia/Kolkata',participants_count:2,
  candidates:[candidate(),candidate({label:'One hour later',starts_at:'2026-10-20T11:00:00Z',ends_at:'2026-10-20T12:00:00Z',rank:1,recorded_clear:true,affected_employee_count:0,recorded_overlap_count:0,overlap_participant_hours:0,conflicts:[]})],
  task_context:{visible_open_tasks:4,estimated_backlog_hours:18,tasks_without_estimates:1,truncated:false,notice:'Backlog estimates, not booked time.'},
  warning:'Not a reservation. Fresh review and confirmation required.',...overrides,
});
const markup=(data:ReflexResult)=>renderToStaticMarkup(createElement(ReflexComparison,{data,onChoose:vi.fn()}));

describe('Reflex visual polish preserves decision and safety contracts',()=>{
  it('uses server rank without changing it; safest observed slot is first',()=>{
    const html=markup(result());
    expect(html.indexOf('One hour later')).toBeLessThan(html.indexOf('Requested slot'));
    expect(html).toContain('First to review');
    expect(html).toContain('No recorded clash');
    expect(html).toContain('Recorded conflict');
    expect(html).toContain('Customer call');
    expect(html).toContain('Asia/Kolkata');
  });
  it('distinguishes a candidate with truncated sources from a truly complete no-clash result',()=>{
    const html=markup(result({candidates:[candidate({rank:1,recorded_clear:true,truncated:true,conflicts:[],recorded_overlap_count:0,overlap_participant_hours:0})]}));
    expect(html).toContain('Incomplete conflict evidence');
    expect(html).toContain('Conflict records may be incomplete');
    expect(html).toContain('No recorded clash does not establish availability');
    expect(html).not.toContain('kr-state--clear');
  });
  it('is only a UI proposal: no automatic booking or request side effects',()=>{
    const html=markup(result());
    expect(html.match(/Use this time in form/g)?.length).toBe(2);
    expect(html).toContain('Nothing has been booked.');
    expect(html).toContain('explicit confirmation');
    expect(html).not.toContain('Confirm &amp; create meeting');
    expect(html).not.toContain('Meeting created');
  });
  it('keeps estimates separate from calendar bookings',()=>{
    const html=markup(result());
    expect(html).toContain('not calendar commitments');
    expect(html).toContain('18');
    expect(html).toContain('without estimates');
  });
  it('renders no-candidate responses defensively without inventing a slot',()=>{
    const html=markup(result({candidates:[]}));
    expect(html).toContain('No comparable time options were returned');
    expect(html).not.toContain('Use this time in form');
  });
  it('shows incomplete conflict-details warning independently of truncated flag',()=>{
    const html=markup(result({candidates:[candidate({rank:1,truncated:false,more_conflicts:true})]}));
    expect(html).toContain('Incomplete conflict evidence');
    expect(html).toContain('Additional overlaps were omitted');
  });
  it('bounds visual percentage on excessive backend overlap values',()=>{
    const html=markup(result({candidates:[candidate({rank:1,overlap_participant_hours:999})]}));
    expect(html).toContain('width:100%');
    expect(html).not.toContain('width:49950%');
  });
});
