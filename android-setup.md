# Android Setup Instructions

This document provides instructions for setting up the Android build environment locally.

## Prerequisites

1. Install Android Studio
2. Install JDK 11
3. Install Node.js and npm
4. Install Python 3.9+

## Local Setup

1. Install Capacitor in the frontend project:
```bash
cd frontend
npm install @capacitor/core @capacitor/cli @capacitor/android
npx cap init "Internet Access Miracle" "com.internetaccessmiracle.app" --web-dir=build
```

2. Build the frontend:
```bash
npm run build
```

3. Add Android platform:
```bash
npx cap add android
```

4. Copy backend to Android assets:
```bash
mkdir -p android/app/src/main/assets/backend
cp -r ../backend/* android/app/src/main/assets/backend/
```

5. Update Android configuration:
```bash
npx cap sync android
```

6. Open in Android Studio:
```bash
npx cap open android
```

## Building APK

1. From Android Studio:
   - Build > Build Bundle(s) / APK(s) > Build APK(s)

2. From command line:
```bash
cd android
./gradlew assembleDebug
```

The APK will be located at `android/app/build/outputs/apk/debug/app-debug.apk`