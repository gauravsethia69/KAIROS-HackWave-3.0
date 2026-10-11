import { describe, expect, it } from 'vitest';
import { istDay, localISTtoUTC, makeProposal } from '../components/scheduling/MeetingScheduler';

describe('KAIROS meeting scheduler data conversion', () => {
  it('turns an IST wall-clock appointment into the right UTC instant', () => {
    expect(localISTtoUTC('2026-10-15T15:00')).toBe('2026-10-15T09:30:00.000Z');
  });
  it('shows the intended date in the employee calendar time zone', () => {
    expect(istDay('2026-10-14T20:00:00Z')).toBe('2026-10-15');
  });
  it('uses stable request key and deduplicates attendees', () => {
    const result=makeProposal({title:'  Team alignment  ',clientId:'orbitpay',projectId:'',purpose:'  Validate agenda ',
      startLocal:'2026-10-15T15:00',duration:60,attendees:['emp001','emp033','emp033'],
      requestId:'8a34f40b-82ce-4198-bc4d-254dc42c255d'});
    expect(result.title).toBe('Team alignment');
    expect(result.project_id).toBeNull();
    expect(result.starts_at).toBe('2026-10-15T09:30:00.000Z');
    expect(result.ends_at).toBe('2026-10-15T10:30:00.000Z');
    expect(result.participant_employee_ids).toEqual(['emp001','emp033']);
  });
  it('rejects invalid time', () => { expect(()=>localISTtoUTC('not-a-date')).toThrow(); });
});
