# Rebuild the VISCANE APK on Windows

Use this guide to build the combined VISCANE app with the current offline scanner and assessment screen. The source changes appear on a phone only after you pull the latest code, rebuild the APK, and install it.

## 1. Install Android Studio

Install the latest stable Android Studio for Windows from [developer.android.com/studio](https://developer.android.com/studio/install). Complete the setup wizard and install the Android SDK packages it recommends. This project compiles against Android SDK 36; Android Studio can install that platform through **Tools → SDK Manager**. Use Android Studio's bundled Gradle JDK unless Gradle reports a Java version error.

## 2. Get the latest project from GitHub

Clone this repository or update the checkout that contains the changes you want to build. Replace `OWNER/REPOSITORY` with this GitHub repository's path. If the changes are on `feature/offline-farmer-classifier`, run:

```powershell
git clone https://github.com/OWNER/REPOSITORY.git
cd REPOSITORY
git fetch origin
git switch feature/offline-farmer-classifier
git pull origin feature/offline-farmer-classifier
```

If you already have the repository, open PowerShell in that folder and run the last three commands.

## 3. Open the correct Android project

In Android Studio, choose **Open** and select the repository's **`android/`** folder. Wait for Gradle Sync to complete. Do not select the older `android-offline/` starter project; it builds a different app and will not include the current combined-app changes.

## 4. Build a test APK

In PowerShell, change into the `android/` folder and run:

```powershell
cd android
.\gradlew.bat :app:assembleDebug -PfarmerBaseUrl=https://YOUR-FARMER-HOST/
```

Replace `https://YOUR-FARMER-HOST/` with the exact HTTPS address that opens the farmer portal in Chrome, including the final `/`. The debug build needs this setting to use that portal. Android Studio can also build it with **Build → Build APK(s)** after you open the `android/` project.

The debug APK is written to:

```text
android\app\build\outputs\apk\debug\app-debug.apk
```

Copy `app-debug.apk` to the phone and install it. The debug app has a `.debug` application ID, so it installs separately from the production app. Sign in online once with the farmer account, then turn on airplane mode and check the offline workspace. Verify photo capture and upload, the result review buttons, agronomic inputs, and scrolling.

## Updating the production app

A debug APK is for testing; it will not replace the installed production app. An in-place production update needs the same application ID, the existing release signing key, a higher `versionCode`, and the correct production HTTPS address. Only the release owner should sign that APK. Do not uninstall the installed app or clear its storage to work around a signing problem; that may delete offline work saved on the phone.

## If the changes still do not appear

- Confirm the Android Studio project is the repository's `android/` folder.
- Confirm Git pulled the commit containing the changes before building.
- Check the build output time and install the newly generated `app-debug.apk`.
- If testing the production app, confirm the release was rebuilt and signed with the existing release key.
