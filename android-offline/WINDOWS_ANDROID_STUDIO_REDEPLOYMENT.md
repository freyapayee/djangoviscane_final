# VISCANE Android Studio redeployment and one-app integration (Windows)

## Purpose

Deploy the latest farmer portal UI and combine the offline sugarcane classifier with the existing online Android WebView app **without changing or deleting** the Django computer-vision prediction API, database, farmer history, admin records, or superadmin records.

The current `android-offline` project is a standalone ONNX classifier. It is **not** the Android WebView app shown in the farmer screenshots. To make one application, copy its classifier code and model assets into the existing WebView app project. Do not replace the online app with this standalone project.

## Before changing Android code

1. Deploy the latest Django branch to the server:

   ```bash
   cd /opt/bitnami/projects/djangoviscane_final
   git pull origin main
   python manage.py collectstatic --noinput
   sudo /opt/bitnami/ctlscript.sh restart apache
   python manage.py check
   ```

2. Confirm farmer login, online scan, input logs, recommendations, admin login, and superadmin login work in the phone browser.
3. Create a branch in the **existing Android WebView repository**:

   ```powershell
   git checkout -b feature/offline-farmer-classifier
   ```

4. Back up the production database through the normal server process. Never run `flush`, delete tables, reset migrations, or change Django API URLs.

## Files to copy into the existing WebView app

Copy these files under the WebView app’s matching package name:

```text
app/src/main/java/com/viscane/offline/OfflineClassifier.kt
app/src/main/java/com/viscane/offline/Preprocessing.kt
app/src/main/assets/resnet18.onnx
app/src/main/assets/yolov8.onnx
app/src/main/assets/labels.txt
app/src/main/assets/model_config.json
```

Add these dependencies to the WebView app module’s Gradle file:

```kotlin
implementation("androidx.activity:activity-ktx:1.10.1")
implementation("androidx.exifinterface:exifinterface:1.4.1")
implementation("com.microsoft.onnxruntime:onnxruntime-android:1.22.0")
```

Preserve the models without compression:

```kotlin
androidResources { noCompress += "onnx" }
```

Use the exact nine-label order in `labels.txt`. Do not rename, reorder, quantize, or substitute model files without repeating model-export and parity checks.

## Safe one-app design

| User and connection state | Prediction path | Data source |
| --- | --- | --- |
| Farmer online | Existing Django/API prediction flow | Existing server database |
| Farmer offline | Bundled ONNX classifier | Local encrypted pending-sync queue only |
| Farmer reconnects | Existing authenticated API | Existing server database |
| Admin or superadmin | Existing online WebView/API flow only | Existing server database |

### Required rules

1. Do not remove or replace the existing Django scan endpoint.
2. Do not write directly to the Django database from Android. Server data must continue through authenticated HTTPS API requests.
3. Never run offline classification for admin or superadmin accounts. Their WebView routes stay online-only.
4. Store offline pending data only for the current logged-in farmer; clear it at logout or account change.
5. On reconnect, upload each queued record once using a stable UUID/idempotency key. Mark it sent only after server confirmation to prevent duplicate logs.
6. Do not queue a result for an anonymous user.
7. Encrypt local pending data and delete it after confirmed synchronization.

## WebView bridge rules

The WebView can expose the native classifier only on trusted farmer scan pages:

```kotlin
webView.addJavascriptInterface(FarmerOfflineBridge(this), "ViscaneOffline")
```

The bridge must reject a call unless all are true:

```text
- the logged-in role is farmer
- the current page is a farmer scan route
- the WebView URL belongs to the approved VISCANE HTTPS domain
```

Do not expose the bridge on `/admin`, `/superadmin`, admin-login, superadmin-login, or external URLs. JavaScript should use the existing online scan API when connected and request local classification only while offline. The local result is then queued for the existing API when the farmer reconnects.

The developer must map fields to the existing API schema after inspecting the WebView project and Django endpoint. Do not invent a new production endpoint or change database tables during this Android release.

## Windows Android Studio build steps

1. Install Android Studio, Android SDK Platform 35, Build Tools, and JDK 17.
2. Clone and open the **existing Android WebView app** repository in Android Studio.
3. Switch to the integration branch:

   ```powershell
   git checkout feature/offline-farmer-classifier
   ```

4. Add the files and dependencies above. Keep the WebView activity, deployed VISCANE URL, API base URL, and signing configuration unchanged.
5. Apply the status-bar and navigation-bar UI setup below.
6. In Android Studio, choose **Build > Clean Project**, **Build > Rebuild Project**, then **Run** on a physical phone.
7. Build a debug APK with **Build > Build APK(s)**, or run:

   ```powershell
   .\gradlew.bat clean assembleDebug
   ```

8. Commit after validation:

   ```powershell
   git add .
   git commit -m "Integrate offline farmer classifier with online portal"
   git push origin feature/offline-farmer-classifier
   ```

## Native mobile status-bar UI

The black strip containing the phone clock, signal, and battery is controlled
by the Android WebView app. The Django website cannot color it. Add this to
the existing WebView app's `MainActivity.kt` to match the VISCANE green header.

Add these imports:

```kotlin
import android.graphics.Color
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsControllerCompat
```

Then add this inside `onCreate()` after `super.onCreate(...)`:

```kotlin
window.statusBarColor = Color.rgb(11, 107, 56) // #0B6B38
window.navigationBarColor = Color.rgb(11, 107, 56)

WindowCompat.setDecorFitsSystemWindows(window, true)

WindowInsetsControllerCompat(window, window.decorView).apply {
    isAppearanceLightStatusBars = false
    isAppearanceLightNavigationBars = false
}
```

This keeps the status/navigation icons white and makes the Android system bars
match the farmer portal's solid green header. Do not place this code in the
Django project or in the standalone classifier's activity unless that activity
is the one used for the final combined WebView app.

If the WebView project uses an XML app theme, add these entries inside its
theme as well:

```xml
<item name="android:statusBarColor">#0B6B38</item>
<item name="android:navigationBarColor">#0B6B38</item>
<item name="android:windowLightStatusBar">false</item>
<item name="android:windowLightNavigationBar">false</item>
```

## Mandatory validation

- [ ] Existing farmer login and online scan still work.
- [ ] Existing farmer history and agronomic logs still appear after installing the updated APK.
- [ ] Admin login/dashboard and superadmin login/dashboard work unchanged.
- [ ] Admin and superadmin cannot access the native classifier bridge.
- [ ] No migrations, database resets, model replacements, or API endpoint removals are included.
- [ ] In airplane mode, a logged-in farmer can classify a photo and sees it marked pending synchronization.
- [ ] After reconnecting, exactly one matching scan/log appears in the farmer, admin, and superadmin views.
- [ ] Reopening the app or retrying synchronization does not create a duplicate record.
- [ ] Logging out and signing in as another farmer does not expose the prior farmer’s pending data.

## Copy/paste prompt for the Android developer

```text
Merge the existing VISCANE Android WebView app with the separate android-offline
ONNX classifier project. Keep the Django website, computer-vision API, API URLs,
database, farmer history, admin records, and superadmin records unchanged. Do not
replace the online scan endpoint.

Copy OfflineClassifier.kt, Preprocessing.kt, resnet18.onnx, yolov8.onnx,
labels.txt, and model_config.json into the WebView app. Add ONNX Runtime Android
and ExifInterface dependencies, and do not compress ONNX assets.

Only authenticated farmers on trusted farmer scan pages may use local ONNX
classification when offline. Admin and superadmin must remain online-only and
must not be able to call the native classifier bridge. When a farmer reconnects,
send pending results through the existing authenticated Django API with a stable
idempotency key. Save pending data only for that farmer, clear it on logout or
account change, and delete it after confirmed sync. Never write directly to the
Django database and do not add destructive migrations.

Before release, test online farmer scans, offline farmer scans, reconnect
synchronization without duplicates, farmer history, admin dashboard, and
superadmin dashboard. Build on Windows with JDK 17 and Android SDK 35. Document
every changed file and keep the server API contract backward compatible.
```
