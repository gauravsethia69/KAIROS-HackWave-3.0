import { beforeEach, describe, expect, it } from 'vitest';
import { gateLogin } from '../components/transitions/gateLogin';

beforeEach(() => gateLogin.reset());
describe('interactive login transition ticket', () => {
  it('does not replay for a restored session', () => expect(gateLogin.consume()).toBe(false));
  it('is consumed once despite repeated authorization events', () => {
    gateLogin.begin();
    expect(gateLogin.consume()).toBe(true);
    expect(gateLogin.consume()).toBe(false);
  });
  it('clears the ticket when sign-in or employee authorization fails', () => {
    gateLogin.begin(); gateLogin.reset();
    expect(gateLogin.consume()).toBe(false);
  });
  it('allows a later interactive login after logout', () => {
    gateLogin.begin(); expect(gateLogin.consume()).toBe(true);
    gateLogin.reset(); gateLogin.begin();
    expect(gateLogin.consume()).toBe(true);
  });
});
