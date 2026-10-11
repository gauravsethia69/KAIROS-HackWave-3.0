import { describe,expect,it } from 'vitest';
import { selectedFunctionalView } from '../components/intelligence/FunctionalWorkspace';
import { groupedReferences, recordIdentity } from '../components/intelligence/EnterpriseAnswerView';
import type { EnterpriseResponse } from '../ai/enterprise';
const payload = (name:string, datasets:Record<string,unknown[]>):EnterpriseResponse => ({
  schemaVersion:2,source:'deterministic-enterprise',title:name,status:'ready',
  intent:{name,clarification:null,date_from:null,date_to:null},context_token:null,
  components:[],datasets:datasets as EnterpriseResponse['datasets'],evidence:[],claims:[],explanations:[],limitations:[],integration_requirements:[],
} as EnterpriseResponse);
describe('Functional workspace v2 presentation',()=>{
  it('selects a calendar for schedule data, and workload bars for ordinary workloads',()=>{
    expect(selectedFunctionalView(payload('team_workload_planning',{schedule_summary:[{id:'w1'}],schedule_events:[]}))).toBe('calendar');
    expect(selectedFunctionalView(payload('team_workload_planning',{workload_chart:[{id:'e1'}]}))).toBe('workload');
  });
  it('maps executive, usage, support, and project requests to distinct views',()=>{
    expect(selectedFunctionalView(payload('executive_briefing',{portfolio_summary:[{id:'p'}]}))).toBe('portfolio');
    expect(selectedFunctionalView(payload('product_usage_investigation',{usage:[{id:'u1'}]}))).toBe('usage');
    expect(selectedFunctionalView(payload('support_incident_command',{issues:[{id:'i1'}]}))).toBe('incidents');
    expect(selectedFunctionalView(payload('project_delivery_review',{projects:[{id:'p1'}]}))).toBe('dependencies');
  });
  it('never creates a functional view from missing data',()=>{
    expect(selectedFunctionalView(payload('team_workload_planning',{}))).toBeNull();
  });
  it('groups field-level evidence chips by actual source record, preserving every ID',()=>{
    const ids=['db:issues:i11:status','db:issues:i11:severity','db:issues:i11:status','db:tasks:t1:record'];
    expect(recordIdentity('db:issues:i11:severity')).toBe('db:issues:i11');
    const groups=groupedReferences(ids);
    expect(groups).toHaveLength(2);
    expect(groups[0]).toEqual(['db:issues:i11:status','db:issues:i11:severity']);
    expect(groups.flat()).toEqual([...new Set(ids)]);
  });
});
