import { describe, expect, it, vi } from 'vitest';
import { adaptEnterprisePlan, enterpriseDataset, planEnterprise } from '../ai/enterprise';
import { apiRequest } from '../lib/api';

vi.mock('../lib/api', () => ({apiRequest: vi.fn()}));
const base = {
  schemaVersion: 2, source: 'deterministic-enterprise', status: 'ready', title:'Project delivery review',
  intent: {name:'project_delivery_review',confidence:1,entities:[], blocked_only:false, unresolved_only:false},
  context_token:'opaque-context',
  components: [{id:'ProjectProgress-projects',type:'ProjectProgress',title:'Delivery progress',priority:10,order:0,size:'wide',props:{selector:'projects',record_ids:['p12'],binding:'response.datasets'},evidence_ids:['db:projects:p12:status'],reason:'Source-bound delivery review'}],
  datasets:{projects:[{id:'p12',name:'Customer reporting refresh',client_id:'atlasmedia',owner:'Hana Brooks',progress:35,expected:80,due_date:'2026-10-20',status:'Delayed'}],clients:[],tasks:[],issues:[],meetings:[],communications:[],usage:[],activity:[]},
  evidence:[{id:'db:projects:p12:status',source_type:'database',source_table:'projects',entity:{entity_type:'project',entity_id:'p12'},title:'Customer reporting refresh',field:'status',retrieved_at:'2026-10-11T01:00:00Z',navigation:{kind:'entity_detail',entity:{entity_type:'project',entity_id:'p12'}}}],
  claims:[{kind:'observation',text:'Recorded as delayed.',evidence_ids:['db:projects:p12:status']}],
  explanations:['Projects selected from PostgreSQL.'],limitations:[],integration_requirements:[],
} as const;
describe('deterministic enterprise v2 binding',()=>{
  it('preserves real client and project ids instead of demo-only IDs', async()=>{
    vi.mocked(apiRequest).mockResolvedValue(base);
    const result=await planEnterprise('Review Atlas Media project');
    expect(result.source).toBe('deterministic-enterprise');
    const adapted=adaptEnterprisePlan(result);
    expect(adapted?.layout[0].type).toBe('ProjectProgress');
    expect(adapted?.selectedEntityIds).toEqual([]);
    expect(enterpriseDataset(result).projects[0].client_id).toBe('atlasmedia');
  });
  it('sends a verified selection without browser-supplied employee role',async()=>{
    vi.mocked(apiRequest).mockResolvedValue(base);
    await planEnterprise('Review project','opaque',{entity_type:'project',entity_id:'p12'});
    const options=vi.mocked(apiRequest).mock.calls.at(-1)!;
    expect(options[0]).toBe('/api/intelligence/workspace/plan');
    const body=JSON.parse(String(options[1]?.body));
    expect(body).toEqual({input:'Review project',context_token:'opaque',selection:{entity_type:'project',entity_id:'p12'}});
    expect(body).not.toHaveProperty('employee_id');
  });
  it('rejects evidence IDs absent from server response',async()=>{
    vi.mocked(apiRequest).mockResolvedValue({...base,claims:[{kind:'observation',text:'unsupported',evidence_ids:['missing']}]});
    await expect(planEnterprise('review')).rejects.toThrow('evidence references');
  });
  it('does not synthesize a workspace when server only asks for clarification',async()=>{
    vi.mocked(apiRequest).mockResolvedValue({...base,status:'clarification',components:[],datasets:{},claims:[],evidence:[],intent:{name:'ownership_lookup',confidence:.2,clarification:{question:'Which task?',candidates:[],suggestions:['Provide an exact task ID']}}});
    const result=await planEnterprise('who owns it?');
    expect(adaptEnterprisePlan(result)).toBeNull();
    expect(result.status).toBe('clarification');
  });
});
