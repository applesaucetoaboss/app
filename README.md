# Internet Access Miracle

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