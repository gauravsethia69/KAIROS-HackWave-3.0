// A local interaction ticket, never an authentication or authorization signal.
// Only Root may consume it AFTER the existing backend authorization succeeds.
let pending = false;
export const gateLogin = {
  begin() { pending = true; },
  reset() { pending = false; },
  consume() { const play = pending; pending = false; return play; },
};
