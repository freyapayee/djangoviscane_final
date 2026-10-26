# VISCANE Android Studio redeployment and one-app integration (Windows)

## Purpose

Build **one Android APK** that opens the existing online VISCANE portal and gives authenticated farmers an on-device scan and assessment screen when offline. Keep the existing Django computer-vision API, its separate classifier service, accounts, farmer history, admin, and superadmin routes working.

**Implementation in source:** The `android/` project now starts with the production farmer site when connected, bundles the nine-class ResNet18 and YOLOv8 ONNX models, opens a farmer-only offline scan screen, and stores pending scans encrypted per farmer. Django has a separate authenticated, UUID-based offline upload route and an additive migration. The old local Django fallback remains in source but is no longer the startup/login path. **This is source code, not a verified or deployed APK.** Do not expect sync to work until Faye applies the migration and deploys the new server route.

GitHub's `android-offline/` is the older Java manual-assessment starter shown in the screenshot. Open `android/` for the combined APK. The ONNX source and model files are already copied into `android/app/`; the separate local Kotlin project remains the reference for preprocessing and parity checks.

**Ownership:** The Windows Android developer builds and tests the APK. The server owner (Faye) alone checks the live server, takes backups, and deploys any approved backend work. The Android developer does not need server or database credentials.

## Before changing Android code

1. Faye confirms farmer, admin, and superadmin sign-in; online scan; farmer history; and admin views in the **phone's Chrome browser**. Record the exact working HTTPS origin and route; share the URL, never passwords or server secrets. An HTTP 500 in the APK while Chrome works requires checking the APK URL and a fresh request log before changing Django.
2. The Android developer opens GitHub's **`android/`** project. Confirm its current application ID and release signing key match the already installed APK. Preserve both for an in-place update. Do not send signing secrets through GitHub.
3. Create a branch in this repository:

   ```powershell
   git checkout -b feature/offline-farmer-classifier
   ```

4. Faye takes a production backup through the normal server process before deploying the **additive** `core/migrations/0010_offline_scan_receipt.py` migration and new API routes. Do not run `flush`, delete tables, replace the prediction API, or point the APK at a different user database. Faye alone performs server deployment.

## Files to copy into the existing WebView app

These files are already in GitHub's `android/app/` module. Keep their package names and exact model hashes. Do not replace `android/app/src/main/java/com/viscane/app/MainActivity.kt` with the older Java starter's `MainActivity.java` or use its separate `applicationId`:

```text
app/src/main/java/com/viscane/offline/OfflineClassifier.kt
app/src/main/java/com/viscane/offline/Preprocessing.kt
app/src/main/assets/resnet18.onnx
app/src/main/assets/yolov8.onnx
app/src/main/assets/labels.txt
app/src/main/assets/model_config.json
```

These dependencies are already added to the Groovy `android/app/build.gradle`. Verify them after opening Android Studio; do not add duplicates:

```kotlin
implementation("androidx.activity:activity-ktx:1.10.1")
implementation("androidx.exifinterface:exifinterface:1.4.1")
implementation("com.microsoft.onnxruntime:onnxruntime-android:1.22.0")
```

Preserve the models without compression:

```kotlin
androidResources { noCompress += "onnx" }
```

If the WebView module uses the Groovy `app/build.gradle` shown in Android Studio, the equivalent is:

```groovy
dependencies {
    implementation 'androidx.activity:activity-ktx:1.10.1'
    implementation 'androidx.exifinterface:exifinterface:1.4.1'
    implementation 'com.microsoft.onnxruntime:onnxruntime-android:1.22.0'
}
android {
    androidResources { noCompress += ['onnx'] }
}
```

The `android/` project already declares the Kotlin Android plugin. Preserve its existing version unless Gradle reports a compatibility issue.

Use the exact nine-label order in `labels.txt`. Do not rename, reorder, quantize, or substitute model files without repeating model-export and parity checks.

The ONNX files total about 49 MB. Confirm they are present in the **final APK** and classification works in airplane mode. The old Java starter's disabled button is not proof that the new models are missing; check which Android project actually built the installed APK.

## Safe one-app design

### Fix the current APK's starting route first

The combined app's `MainActivity.kt` now opens the configured **production HTTPS origin** when connected and retains the existing WebView login and cookies. A server HTTP 500 remains an error, rather than triggering the local Django copy with a separate user database. Set `-PfarmerBaseUrl=https://YOUR-ACTUAL-FARMER-HOST/` for the release build. On a phone, verify that Chrome and the APK reach the same host and that the APK accepts the same farmer account.

The embedded Django copy still has its own SQLite database, so the new offline scan Activity does **not** use it for login or history. Offline scan unlocks only after the app obtains a farmer ID from the authenticated production `/api/mobile/session` route. Each encrypted pending record is kept under that farmer ID. Admin and superadmin continue using their unchanged production web routes; `FarmerNavigation.kt` limits this APK to farmer routes.

| User and connection state | Prediction path | Data source |
| --- | --- | --- |
| Farmer online | Existing Django/API prediction flow | Existing server database |
| Farmer offline | Bundled ONNX classifier | Farmer-owned local draft and pending queue |
| Farmer reconnects | Authenticated sync contract, after server support is verified | Existing server database |
| Admin or superadmin | Existing online WebView/API flow only | Existing server database |

### Required rules

1. Do not remove or replace the existing Django scan endpoint.
2. Do not write directly to the Django database from Android. Server data must continue through authenticated HTTPS API requests.
3. Never run offline classification for admin or superadmin accounts. Their WebView routes stay online-only.
4. Bind each offline record to the locally remembered **server farmer ID** from a prior authenticated online session. On sign-out, lock that farmer's pending records; never expose or upload them from another account. Do not discard unsent records silently.
5. Show `Pending sync` on each unsent offline record. Preserve records across app restart and network failures. Explain clearly that pending data is on the device and is not yet visible to admin or superadmin. After confirmation, the server record appears in online history.
6. Use a stable record UUID and server-side deduplication. Mark sent only after the server confirms persistence for the same farmer. Retry without creating a duplicate; do not put a client supplied farmer ID in place of the authenticated server identity.
7. Encrypt sensitive local records and photos. Remove a local copy only after confirmed sync and according to a deliberate retention policy. Do not queue records for someone who has never authenticated online.

### Synchronization is a separate required integration

The existing Django `POST /api/scan/predict` still sends photos to the separate classifier. The combined app **never** posts offline model results there. A new authenticated `POST /api/mobile/offline-scan` route accepts a photo and local result with a stable record UUID. It creates a linked photo and agronomic history row once and labels the model `on_device_ensemble_unverified`, since the server cannot prove what ran on the phone. Farmer history, admin monitoring, and superadmin history can read those rows. `GET /api/mobile/session` identifies the signed-in farmer to the app. Both routes reject the embedded offline Django server.

The app retries pending uploads only against the configured HTTPS production origin with its existing farmer session and CSRF cookie. It removes an encrypted local record only after the server confirms the same UUID and a saved log ID. If the server lacks this route, rejects the session, or fails, the record remains **Pending sync**. Faye must deploy the additive migration and API code before accepting a release that promises farmer-to-admin synchronization; first verify idempotent retries and all three views in staging. The online prediction and calculation routes remain intact.

### Existing offline data from the older APK

The old Java fallback stored local assessments in `assessments.db` without a verified production farmer ID. The new app leaves that database file in place during an in-place update, but **does not automatically upload or display those legacy records** because associating them with an account would be unsafe. Export them from the old screen before updating if they are needed, and reconcile them with Faye before any manual import. Do not uninstall or clear app data to troubleshoot login.

### Server owner deployment sequence (Faye only)

After a production backup and staging verification, merge the reviewed integration branch. On the server, Faye runs:

```bash
cd /opt/bitnami/projects/djangoviscane_final
git pull origin main
python manage.py check
python manage.py migrate --plan
python manage.py migrate
python manage.py collectstatic --noinput
sudo /opt/bitnami/ctlscript.sh restart apache
```

Then verify the existing online scan API, farmer login/history, admin monitoring, and superadmin history before the updated APK is distributed. The groupmate needs only the Android repository, test host, and test farmer account; no server login.

## Farmer-only boundary

The combined app uses a separate native offline Activity, with no JavaScript bridge into the WebView. It opens only after `/api/mobile/session` has returned a real farmer ID during a prior online session. The app sends pending scans only with the current HTTPS WebView session and only when its authenticated server farmer ID matches the record owner. Admin and superadmin accounts stay on their existing online routes; the native offline Activity is not exported.

## Offline screen must match the farmer portal

The screenshot's plain “VISCANE Offline” form is the older Java fallback Activity. The new `OfflineScanActivity.kt` uses a green header, large text, photo-first white card, camera/gallery controls, and Home / Recommendations / Input Logs / Profile navigation. Its Input Logs dialog filters pending history by All / week / month / year and opens saved photos. Keep refining spacing and font against the **actual phone** screenshots; the offline screen is similar to the portal but is not a pixel-perfect copy. It labels unsynced results `Pending sync`.

The current offline screen is native and needs no remote CSS, font, or image download. It does not display fake live weather. It uses `OfflineClassifier.kt` directly, avoiding a JavaScript bridge. The WebView continues to serve online pages; the offline Activity stores local records until authenticated sync confirms them. Test both with airplane mode before launch and after a previously authenticated session.

Match these flows, not just colors: camera/gallery, image preview, scan result, assessment parameters, saved local history with All / week / month / year filters, expandable result details, return to online screen, and accessible back navigation. Use the current `static/style.css` and farmer templates as design reference; avoid copying server templates with Django tags as raw Android assets. Admin and superadmin see their existing online screens or an offline-unavailable message, never farmer offline data.

## Windows Android Studio build steps

1. Install Android Studio, JDK 17, and Android SDK/Build Tools for GitHub's `android/` project (its Gradle module currently sets compile/target SDK 36). Do not open `android-offline/` as the final app.
2. Clone the GitHub repository and open its **`android/`** folder in Android Studio. Confirm its `farmerBaseUrl` matches the HTTPS origin that works in Chrome; avoid a stale IP, test server, or second login database. `127.0.0.1` is only the bundled offline server.
3. Switch to the integration branch created above:

   ```powershell
   git switch feature/offline-farmer-classifier
   ```

4. Review the online-first startup, Kotlin classifier, exact assets, farmer-only offline screen, encrypted pending queue, and `OfflineSync.kt` already in source. Keep `com.viscane.app` if that is the installed app's real application ID, plus the portal URL, online API route, cookie/session handling, and release signing setup. Do not add another farmer credential store.
5. Check the green status bar and offline UI on the real phone. The camera/gallery flow and photo orientation code are in `OfflineScanActivity.kt`.
6. In Android Studio, let Gradle sync, then choose **Build > Rebuild Project** and **Run** on a physical phone. Exercise login and online scan before testing airplane mode.
7. Build a debug APK with **Build > Build APK(s)**, or run in PowerShell if the WebView repository includes a Gradle wrapper:

   ```powershell
   .\gradlew.bat :app:assembleDebug -PfarmerBaseUrl=https://YOUR-ACTUAL-FARMER-HOST/
   ```

   Replace the placeholder with the exact HTTPS origin that works in Chrome, including the final `/`. Pass it for **debug and release** builds; otherwise the debug app defaults to `http://10.0.2.2:5000/` and will not use production credentials. For a release, use the existing private signing setup and increase `versionCode`. Debug builds add `.debug` to the application ID, so they install beside the production app and do not test an in-place update. Faye deploys the server migration and route **before** releasing an APK expected to sync.

8. Commit after validation:

   ```powershell
   git add .
   git commit -m "Integrate offline farmer classifier with online portal"
   git push origin feature/offline-farmer-classifier
   ```

9. To update the installed production app, Faye or the release owner signs with the **existing** release key and verifies the unchanged application ID plus a higher `versionCode`. Installing a debug APK with a different signing key may require uninstalling the old app, which can erase local pending data. Never uninstall or clear app storage to “fix” a login or HTTP 500 problem.

### If the new APK shows HTTP 500 or “invalid credentials”

1. Compare the full HTTPS origin and login path used by Chrome and by the APK. Verify the APK is pointed at the live Django site, not an emulator URL, old IP, test server, or local offline login.
2. Test a fresh request while Faye watches the live Apache error/access logs. Old `DisallowedHost` bot probes or `Not Found` scanner entries do not explain a new APK request by themselves.
3. Confirm WebView cookies, JavaScript, DOM storage, HTTPS redirects, and session persistence follow the existing app's working login implementation. Never send credentials to the offline screen or bundled code.
4. Capture the exact APK URL, time, status, and corresponding traceback; Faye diagnoses the server only if the live request actually reaches it. Keep production data untouched while diagnosing.

## Native mobile status-bar UI

The black strip containing the phone clock, signal, and battery is controlled by Android. The source now sets `Theme.Viscane` bars to green and requests white status icons; `MainActivity.kt` already applies system-bar insets. Verify on the target phone, especially Android edge-to-edge versions, and do not add a second inset handler.

The current Activity includes these imports:

```kotlin
import android.graphics.Color
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsControllerCompat
```

The current `onCreate()` draws green behind the system inset and requests white status icons:

```kotlin
window.decorView.setBackgroundColor(Color.rgb(11, 107, 56))
WindowCompat.setDecorFitsSystemWindows(window, false)
WindowInsetsControllerCompat(window, window.decorView).isAppearanceLightStatusBars = false
```

On supported Android versions this sets white system icons against green bars. Android 15/16 edge-to-edge behavior can make the status bar transparent; then draw the same green behind the inset area rather than relying on `statusBarColor` alone. Verify the title and bottom navigation are not hidden by system bars. Put this in the combined app's Activity/theme, not Django or a separate starter APK.

Check the green values inside `Theme.Viscane` in `android/app/src/main/res/values/themes.xml`:

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
- [ ] Admin and superadmin cannot access the farmer offline Activity or upload route.
- [ ] Only additive migration `0010` is applied; no database resets, online model replacements, or existing API endpoint removals occur.
- [ ] One installed APK and launcher icon open online farmer pages and the visually matched offline farmer screen; no separate “VISCANE Offline” app is required.
- [ ] The final APK contains both ONNX models and nine labels, and camera/gallery classification works in airplane mode on real photos.
- [ ] The offline screen's green header, readable font, photo card, bottom navigation, and log filters are checked against the online UI on the actual phone. Refine remaining visual differences before release.
- [ ] A previously authenticated farmer can save an offline result, reopen the app, and still see `Pending sync`; a fresh device with no prior login cannot impersonate a farmer.
- [ ] Logging out and signing in as another farmer does not expose or submit the prior farmer’s pending data.
- [ ] **Release gate for sync:** Faye has deployed migration `0010` and the new routes after backup; the authenticated farmer and UUID deduplication are tested, and one reconnected record appears exactly once in farmer history, admin monitoring, and superadmin history. Until then, records remain `Pending sync`.
- [ ] Installing as an update preserves the app's online session/local pending records and does not require wiping app data.

## Copy/paste prompt for the Android developer

```text
Open GitHub's android/ project in Android Studio on Windows. Build ONE update APK
with the SAME production applicationId and release signing key. The nine-class
ONNX files and classifier code are already under android/app; do not use the
older android-offline Java project as the final app.

Check the new online-first MainActivity: existing farmer credentials must work
against the same HTTPS host as Chrome. A server HTTP 500 must stay visible as
a server error. Check the native OfflineScanActivity in airplane mode: camera,
gallery, EXIF orientation, green header, picture-first result, Input Logs
filters, and per-farmer Pending sync data must work after app restart.

After Faye deploys additive Django migration 0010 and the new /api/mobile/
routes, reconnect and verify exactly one record per UUID in farmer history,
admin monitoring, and superadmin history. The existing /api/scan/predict
classifier route must still work for online scans. If the server route is not
ready or login fails, pending records must remain on the phone.

Test a second farmer and both admin roles. Confirm the offline Activity never
shows another farmer's pending scans. Verify an in-place release update keeps
the existing session and pending data. Report build output, device screenshots,
remaining UI differences, and the APK applicationId/versionCode/signature.
```

## Copy/paste prompt for Faye (server owner)

```text
Back up production. Review and test the additive core migration 0010 and the
new /api/mobile/session and /api/mobile/offline-scan routes on staging. Confirm
farmer session ownership, CSRF, nine-class label validation, model hashes,
duplicate UUID retry, and visibility in farmer/admin/superadmin history.
Verify the existing online /api/scan/predict still uses the classifier service.
Deploy the migration and server code yourself before an APK is released with
sync expectations. Give the Android developer a test account and HTTPS host,
not SSH/database credentials.
```
