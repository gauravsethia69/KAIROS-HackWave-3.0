import { describe, expect, it } from 'vitest';
import type { EnterpriseResponse } from '../ai/enterprise';
import { intentAppearance, intentPrimaryClaim, intentWorkspaceLayers } from '../components/intelligence/intentPresentation';

const fixture = (name: string, changes: Partial<EnterpriseResponse> = {}): EnterpriseResponse => ({
  schemaVersion: 2, source:'deterministic-enterprise', status:'ready', title:'Authenticated review',
  intent: {name, date_from:null,date_to:null}, context_token:null, components:[], datasets:{}, evidence:[],
  claims:[], explanations:[], limitations:[], integration_requirements:[], ...changes,
});

describe('KAIROS intent-to-interface presentation',()=>{
  it('chooses visibly different presentation families by backend intent',()=>{
    expect(intentAppearance(fixture('client_meeting_prep')).kind).toBe('meeting');
    expect(intentAppearance(fixture('product_usage_investigation')).kind).toBe('usage');
    expect(intentAppearance(fixture('project_delivery_review')).kind).toBe('project');
    expect(intentAppearance(fixture('support_incident_command')).kind).toBe('support');
    expect(intentAppearance(fixture('team_workload_planning')).kind).toBe('people');
    expect(intentAppearance(fixture('executive_briefing')).kind).toBe('executive');
    expect(intentAppearance(fixture('not_supported')).kind).toBe('lookup');
  });
  it('never invents a verified answer when there are no backend factual claims',()=>{
    expect(intentPrimaryClaim(fixture('ownership_lookup'))).toBeNull();
    expect(intentPrimaryClaim(fixture('ownership_lookup',{claims:[{kind:'proposed_action',text:'Maybe assign it',evidence_ids:[]}]}))).toBeNull();
  });
  it('displays an actual observation, not a proposed action, as the key finding',()=>{
    const result=fixture('project_delivery_review',{claims:[{kind:'proposed_action',text:'Plan follow-up',evidence_ids:[]},{kind:'observation',text:'Atlas Media: 38% complete',evidence_ids:[]}]});
    expect(intentPrimaryClaim(result)).toBe('Atlas Media: 38% complete');
  });
  it('only advertises interactive surfaces that actually mount',()=>{
    const result=fixture('team_workload_planning');
    expect(intentWorkspaceLayers(result,null)).toEqual([]);
    expect(intentWorkspaceLayers(result,'calendar')).toEqual(['Interactive weekly calendar']);
    expect(intentWorkspaceLayers(fixture('product_usage_investigation',{components:[{id:'a',type:'UsageChart',title:'Measured usage',priority:10,order:0,size:'wide',props:{selector:'usage',record_ids:[],binding:'response.datasets'},evidence_ids:[],reason:'Server-backed'}]}),'usage'))
      .toEqual(['Product usage analytics']);
  });
});
