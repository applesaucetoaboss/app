# Internet Access Miracle

[![Android Build](https://github.com/applesaucetoaboss/app/actions/workflows/android-build.yml/badge.svg?branch=main)](https://github.com/applesaucetoaboss/app/actions/workflows/android-build.yml)

[![Android Build](https://github.com/applesaucetoaboss/app/actions/workflows/android-build.yml/badge.svg?branch=main)](https://github.com/applesaucetoaboss/app/actions/workflows/android-build.yml)

An application that helps users without internet access to establish connections through various methods.

## Overview

This application consists of:
- **Backend**: FastAPI server that discovers and manages internet connection sources
- **Frontend**: React application that provides a user interface
- **Android App**: Mobile version for users without internet access

## Android Build

This project can be built into an Android app using GitHub Actions:

1. The workflow automatically builds when code is pushed to the main branch
2. APK is generated and available as an artifact in GitHub Actions
3. Users can download and install the APK directly on their Android devices

For detailed local setup instructions, see [Android Setup](android-setup.md).

View CI runs: https://github.com/applesaucetoaboss/app/actions

## Privacy Policy (for Google Play)

You need a public URL for your Privacy Policy. Two easy options:

- Backend route: run/deploy the FastAPI server and use `https://your-server-domain/privacy`.
- GitHub Pages: use the included `docs/privacy.html`.

### Enable GitHub Pages
1. Push the repo to GitHub (e.g., `https://github.com/applesaucetoaboss/app`).
2. In GitHub: Settings → Pages → Source: "Deploy from a branch".
3. Select Branch: `main`, Folder: `/docs`, then Save.
4. Your policy will be available at `https://<your-username>.github.io/<repo-name>/privacy.html`.

For the provided repo, the link will be:
- `https://applesaucetoaboss.github.io/app/privacy.html`

Add this URL in Play Console → App content → Privacy policy.

## AdMob Setup

Set these env vars in `frontend/.env`:
- `REACT_APP_ADMOB_APP_ID=ca-app-pub-xxxxxxxxxxxxxxxx~yyyyyyyyyy`
- `REACT_APP_ADMOB_REWARDED_UNIT_ID=ca-app-pub-xxxxxxxxxxxxxxxx/zzzzzzzzzz`
- Optional: `REACT_APP_ADMOB_DEBUG_AUTO_UNLOCK=true` to bypass the gate during dev.

See `frontend/README.admob.md` for details.

### CI AdMob App ID Secret
The CI injects the AdMob App ID into the Android manifest during the build.

- In GitHub: Settings → Secrets and variables → Actions → New repository secret
- Name: `ADMOB_APP_ID`
- Value: your App ID (format `ca-app-pub-xxxxxxxxxxxxxxxx~yyyyyyyyyy`)

If the secret is missing, the CI uses Google’s sample App ID for testing only.

## Development

### Backend
```bash
cd backend
pip install -r requirements.txt
python server.py
```

### Frontend
```bash
cd frontend
npm install
npm start
```

## GitHub Workflow

The project includes a GitHub workflow that:
1. Builds the frontend React application
2. Sets up Capacitor for Android
3. Packages the backend into the Android assets
4. Builds an Android APK
5. Makes the APK available for download
