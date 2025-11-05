// Simple rewarded-ad gate helper.
// Web fallback simulates reward; Android will use AdMob once plugin is installed.

import { registerPlugin } from '@capacitor/core';

const APP_ID = process.env.REACT_APP_ADMOB_APP_ID;
const REWARDED_UNIT_ID = process.env.REACT_APP_ADMOB_REWARDED_UNIT_ID;
const DEBUG_AUTO_UNLOCK = String(process.env.REACT_APP_ADMOB_DEBUG_AUTO_UNLOCK).toLowerCase() === 'true';

export async function ensureRewardGate() {
  // If already unlocked, allow immediately
  if (localStorage.getItem('reward_unlocked') === '1') {
    return true;
  }

  // Debug override to bypass gate during development
  if (DEBUG_AUTO_UNLOCK) {
    localStorage.setItem('reward_unlocked', '1');
    return true;
  }

  // Try Capacitor AdMob plugin if present (runtime check only; requires package installation)
  const isCapacitor = typeof window !== 'undefined' && window.Capacitor;
  const canUsePlugin = isCapacitor && window.Capacitor?.isNativePlatform?.();

  if (canUsePlugin) {
    try {
      // Register the native AdMob plugin without importing its JS package.
      const AdMob = registerPlugin('AdMob');
      // Support multiple possible event name variants to be robust across plugin versions
      const RewardEvents = {
        Rewarded: ['rewardad_on_rewarded', 'Rewarded', 'rewarded'],
        Dismissed: ['rewardad_dismiss', 'Dismissed', 'dismissed'],
        Loaded: ['rewardad_loaded', 'Loaded', 'loaded'],
        FailedToLoad: ['rewardad_failedtoload', 'FailedToLoad', 'failedToLoad'],
        Showed: ['rewardad_showed', 'Showed', 'showed'],
        FailedToShow: ['rewardad_failedtoshow', 'FailedToShow', 'failedToShow'],
      };

      // Initialize SDK (uses manifest App ID or passed appId)
      await AdMob.initialize({ requestTrackingAuthorization: true, initializeForTesting: false, appId: APP_ID });
      if (AdMob.requestTrackingAuthorization) {
        await AdMob.requestTrackingAuthorization();
      }

      let rewarded = false;

      const listeners = [];
      const addL = (names, fn) => {
        if (AdMob.addListener) {
          names.forEach((n) => {
            try { listeners.push(AdMob.addListener(n, fn)); } catch (_) {}
          });
        }
      };

      addL(RewardEvents.Rewarded, () => { rewarded = true; });
      addL(RewardEvents.Dismissed, () => {});
      addL(RewardEvents.FailedToLoad, () => {});
      addL(RewardEvents.FailedToShow, () => {});
      addL(RewardEvents.Loaded, () => {});
      addL(RewardEvents.Showed, () => {});

      await AdMob.prepareRewardVideoAd({ adId: REWARDED_UNIT_ID, isTesting: false });
      await AdMob.showRewardVideoAd();

      listeners.forEach((h) => { try { h.remove(); } catch (_) {} });

      if (rewarded) {
        localStorage.setItem('reward_unlocked', '1');
        return true;
      }
      return false;
    } catch (err) {
      console.warn('AdMob plugin not registered yet or failed; falling back to web simulation.', err);
      // Fall through to web simulation below
    }
  }

  // Web fallback simulation: ask user to confirm watching ad
  const ok = window.confirm('Watch a rewarded ad to unlock connect? (simulation on web)');
  if (ok) {
    // Simulate reward grant
    localStorage.setItem('reward_unlocked', '1');
    return true;
  }
  return false;
}

export function resetRewardGate() {
  localStorage.removeItem('reward_unlocked');
}
