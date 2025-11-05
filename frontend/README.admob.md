# AdMob Rewarded Ads Integration

This app gates the main Connect action behind a rewarded ad using Google Mobile Ads SDK via Capacitor.

## IDs

- App ID: `ca-app-pub-7429469900417746~7081746845`
- Rewarded Unit: `ca-app-pub-7429469900417746/8580152032`

These are already set in `frontend/.env`:

```
REACT_APP_ADMOB_APP_ID=ca-app-pub-7429469900417746~7081746845
REACT_APP_ADMOB_REWARDED_UNIT_ID=ca-app-pub-7429469900417746/8580152032
REACT_APP_ADMOB_DEBUG_AUTO_UNLOCK=false
```

## Install and Platform Setup (Android)

1. Install packages:
   - `npm install @capacitor/android @capacitor-community/admob`
2. Add Android platform:
   - `npx cap add android`
3. Sync native:
   - `npx cap sync android`
4. Add App ID to `AndroidManifest.xml` (if not initializing via code):
   - In the `application` tag: 
     ```xml
     <meta-data
         android:name="com.google.android.gms.ads.APPLICATION_ID"
         android:value="ca-app-pub-7429469900417746~7081746845"/>
     ```
   - Note: The code also calls `AdMob.initialize({ appId })` as a fallback.
5. Open Android Studio and run the app.

## How It Works

- The Connect button calls a gate helper (`src/lib/adGate.js`).
- On Android, it uses the native AdMob plugin to show a rewarded ad.
- On web, it uses a simple confirmation as a simulation to keep development smooth.
- After reward, `localStorage.reward_unlocked = '1'` enables Connect without re-watching.

## Testing Tips

- Use test devices or test ads when developing; set `initializeForTesting: true` and pass test device IDs if needed.
- Verify the reward callback fires and the gate unlocks.
- If ads fail frequently during dev, temporarily set `REACT_APP_ADMOB_DEBUG_AUTO_UNLOCK=true` to bypass the gate while you diagnose.

## Policy Compliance

- Review AdMob policies: https://support.google.com/admob/answer/6128543
- Do not incentivize misleading behavior; clearly explain that watching an ad unlocks a feature.
- Avoid placing ads in disruptive positions; use rewarded format for voluntary unlocks.
- Ensure privacy disclosures and consent flows where required (GDPR/CCPA).

## Next Steps

- Replace the web fallback with real rewarded ads after installing the plugin.
- Add banners/interstitials where appropriate, respecting policy and UX.
- Consider frequency capping and graceful failure (e.g., allow limited free connects if ad fails).

## CI Build Notes

- The GitHub Action at `.github/workflows/android-build.yml` installs `@capacitor-community/admob`, syncs Android, and injects the AdMob App ID into `AndroidManifest.xml` during the build.
- It builds a debug APK and uploads it as an artifact named `app-debug`. Download from the Actions run to test on device.

## Local Build Prereqs

- Ensure Node.js and npm (or Yarn) are installed and on PATH.
- From `frontend/`, run: `npm install`, then `npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor-community/admob`, `npm run build`, `npx cap add android`, and `npx cap sync android`.
- Open `frontend/android` in Android Studio, confirm `AndroidManifest.xml` contains the AdMob App ID meta-data, then build and run.
