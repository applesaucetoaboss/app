import { ensureRewardGate, resetRewardGate } from './adGate';

describe('adGate helper', () => {
  beforeEach(() => {
    // Reset localStorage and confirm mock
    localStorage.clear();
    // Default confirm to true unless overridden in a test
    window.confirm = jest.fn(() => true);
    // Ensure no Capacitor native platform in tests
    delete window.Capacitor;
    process.env.REACT_APP_ADMOB_DEBUG_AUTO_UNLOCK = 'false';
  });

  test('returns true immediately when already unlocked', async () => {
    localStorage.setItem('reward_unlocked', '1');
    const ok = await ensureRewardGate();
    expect(ok).toBe(true);
    expect(window.confirm).not.toHaveBeenCalled();
  });

  test('web fallback unlocks when user confirms', async () => {
    window.confirm = jest.fn(() => true);
    const ok = await ensureRewardGate();
    expect(ok).toBe(true);
    expect(localStorage.getItem('reward_unlocked')).toBe('1');
    expect(window.confirm).toHaveBeenCalled();
  });

  test('web fallback denies when user cancels', async () => {
    window.confirm = jest.fn(() => false);
    const ok = await ensureRewardGate();
    expect(ok).toBe(false);
    expect(localStorage.getItem('reward_unlocked')).not.toBe('1');
    expect(window.confirm).toHaveBeenCalled();
  });

  test('debug auto unlock bypasses gate', async () => {
    process.env.REACT_APP_ADMOB_DEBUG_AUTO_UNLOCK = 'true';
    const ok = await ensureRewardGate();
    expect(ok).toBe(true);
    expect(localStorage.getItem('reward_unlocked')).toBe('1');
    expect(window.confirm).not.toHaveBeenCalled();
  });

  test('resetRewardGate clears unlock state', () => {
    localStorage.setItem('reward_unlocked', '1');
    resetRewardGate();
    expect(localStorage.getItem('reward_unlocked')).toBeNull();
  });
});

