# VISCANE Android Studio redeployment and one-app integration (Windows)

## Purpose

Build **one Android APK** that opens the existing online VISCANE portal and gives authenticated farmers an on-device scan and assessment screen when offline. Keep the existing Django computer-vision API, its separate classifier service, accounts, farmer history, admin, and superadmin routes working.

**Current state:** The GitHub repository now contains `android/`, a WebView APK with an embedded Django copy and a basic offline assessment Activity. It starts the **local** Django server at `127.0.0.1` on every launch (`android/app/src/main/java/com/viscane/app/MainActivity.kt`), with a separate app-local SQLite database (`OfflineDjangoServer.kt`). That explains why a farmer's existing server credentials can fail in the APK while Chrome login works: the local user database is different. Local farmer records do **not** currently sync to the production database, so admin and superadmin cannot see them. The fallback assessment screen in the screenshot has no bundled recognition model. These instructions describe the required corrections; a working synchronized APK is **not yet verified**.

Faye's local `/Users/fayecuevas/Documents/deployment/android-offline` folder contains a separate Kotlin ONNX classifier with both nine-class models. GitHub's `android-offline/` is an older Java manual-assessment starter. The Android developer needs Faye's Kotlin source/model files in addition to GitHub's `android/` project.

**Ownership:** The Windows Android developer builds and tests the APK. The server owner (Faye) alone checks the live server, takes backups, and deploys any approved backend work. The Android developer does not need server or database credentials.

## Before changing Android code

1. Faye confirms farmer, admin, and superadmin sign-in; online scan; farmer history; and admin views in the **phone's Chrome browser**. Record the exact working HTTPS origin and route; share the URL, never passwords or server secrets. An HTTP 500 in the APK while Chrome works requires checking the APK URL and a fresh request log before changing Django.
2. The Android developer opens GitHub's **`android/`** project and obtains Faye's separate Kotlin classifier source/assets. Confirm its current application ID and release signing key match the already installed APK. Preserve both for an in-place update. The Kotlin models are currently local to Faye's deployment folder; they are **not** supplied by GitHub's Java starter. Do not send signing secrets through GitHub.
3. Create a branch in this repository:

   ```powershell
   git checkout -b feature/offline-farmer-classifier
   ```

4. Faye takes a production backup through the normal server process before any **separately approved** server change. This Android-only phase needs no `git pull`, `collectstatic`, Apache restart, database migration, `flush`, or changes to prediction API URLs.

## Files to copy into the existing WebView app

Copy these files **from Faye's local Kotlin classifier project** into GitHub's `android/app/` module; adapt package declarations/imports to `com.viscane.app` as needed. Do not replace `android/app/src/main/java/com/viscane/app/MainActivity.kt` with the older Java starter's `MainActivity.java` or use its separate `applicationId`:

```text
app/src/main/java/com/viscane/offline/OfflineClassifier.kt
app/src/main/java/com/viscane/offline/Preprocessing.kt
app/src/main/assets/resnet18.onnx
app/src/main/assets/yolov8.onnx
app/src/main/assets/labels.txt
app/src/main/assets/model_config.json
```

Add only missing dependencies to the WebView app module’s Gradle file (Kotlin DSL shown; translate to Groovy syntax if its file is `build.gradle`):

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

The WebView project also needs a Kotlin Android plugin compatible with its existing Android Gradle plugin before `.kt` files compile. Let Android Studio propose a compatible version; do not paste a second conflicting plugin declaration.

Use the exact nine-label order in `labels.txt`. Do not rename, reorder, quantize, or substitute model files without repeating model-export and parity checks.

The ONNX files total about 49 MB. Confirm they are present in the **final APK** and classification works in airplane mode. The old Java starter's disabled button is not proof that the new models are missing; check which Android project actually built the installed APK.

## Safe one-app design

### Fix the current APK's starting route first

In GitHub's `android/app/src/main/java/com/viscane/app/MainActivity.kt`, `onCreate()` currently calls `loadOfflineDjango()` unconditionally. The embedded Django server then serves `/auth` from its own SQLite database. Change startup to load the configured **production HTTPS origin** when reachable, preserving WebView cookies and the server's existing login. Fall back to the bundled farmer UI only when the site is unreachable and a farmer previously authenticated online on this device. Do not interpret an HTTP 500 as proof of no network: show the error and log the exact request, rather than silently switching to a different user database. Set `-PfarmerBaseUrl=https://YOUR-ACTUAL-FARMER-HOST/` for the release build; the current Gradle file requires it but the current startup path does not use it first.

The bundled Django copy is useful for visual consistency, but its local SQLite database is **not** the server's database. A farmer must never be asked to create a second “offline” account or be told local records are on the server. The developer must define how the app securely recognizes a previously authenticated farmer offline, and keep the local farmer data separated by account. Admin and superadmin continue using their unchanged production web routes; the Android app's `FarmerNavigation.kt` intentionally limits this APK to farmer routes.

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
5. Show `Pending sync`, `Synced`, or `Needs attention` on each offline record. Preserve drafts across app restart and network failures. Explain clearly that pending data is on the device and is not yet visible to admin or superadmin.
6. Use a stable record UUID and server-side deduplication. Mark sent only after the server confirms persistence for the same farmer. Retry without creating a duplicate; do not put a client supplied farmer ID in place of the authenticated server identity.
7. Encrypt sensitive local records and photos. Remove a local copy only after confirmed sync and according to a deliberate retention policy. Do not queue records for someone who has never authenticated online.

### Synchronization is a separate required integration

The current Django `POST /api/scan/predict` sends a photo to the existing classifier and saves its **server** prediction context. It is not an offline-result upload endpoint. The calculation route creates agronomic logs but currently has no demonstrated client UUID deduplication contract. Posting a local model result to either route as though it were a server scan can produce inconsistent history or duplicate entries. **Do not claim sync works by calling either route without a reviewed contract.**

Faye and the Android developer must agree on a small, authenticated server sync contract before enabling uploads. It must verify the logged-in farmer on the server, validate the nine-class label/model version and fields, accept a stable UUID idempotently, return the canonical server record ID, and make that record appear in existing farmer history and admin/superadmin read views. The server owner implements and deploys that additive endpoint only after backup, review, and staging tests; leave existing online prediction and calculation routes intact. Until then, keep offline records locally with an honest `Pending sync` label and disable automatic upload. The app must never say `Synced` merely because connectivity returned.

## WebView bridge rules

If the combined app uses a JavaScript bridge, expose the native classifier only on trusted farmer scan pages. This is **illustrative**, not drop-in secure code:

```kotlin
webView.addJavascriptInterface(FarmerOfflineBridge(this), "ViscaneOffline")
```

The bridge must reject a call unless all are true:

```text
- the logged-in role is farmer
- the current page is a farmer scan route
- the WebView URL belongs to the approved VISCANE HTTPS domain
```

Do not expose the bridge on `/admin`, `/superadmin`, admin-login, superadmin-login, or external URLs. Verify origin and farmer authorization for **each bridge call**, not just when the WebView first loads. `addJavascriptInterface` exposes its object to frames and cannot by itself prove the caller's origin; a separate native farmer screen avoids that bridge risk. Online scans keep using the existing server API. Offline scans use the bundled models and local queue.

The developer must inspect the actual WebView source before choosing a bridge or native screen. Do not invent a production endpoint inside the APK or change database tables during this Android-only phase.

## Offline screen must match the farmer portal

The screenshot's plain “VISCANE Offline” form is the basic Java fallback Activity already copied into `android/`; it is not the intended final UI. Present offline mode as a **farmer screen within the same app**. Use the existing farmer portal as the visual reference: solid green header, the same font and readable sizes, white rounded panels, matching green buttons, picture-first scan card, compact detail dropdown, weather/date placement, and the same Home / Recommendations / Input Logs / Profile bottom navigation. Keep system status and navigation bars coordinated with the header and Android safe areas. Give offline mode a small visible indicator and show `Pending sync` beside local history items.

Recommended approach: reuse the farmer templates/styles that `android/app/build.gradle` already packages into `django-server` assets, while routing offline scan/classification and local history through dedicated local code. Do not rely on server-only template data or the local Django user table as if it were synchronized with production. The offline page must contain **no remote CSS, JavaScript, font, or image dependencies** and must not display a fake live weather value; use device date and an explicit offline weather state. Keep online WebView cookies, login, and portal navigation intact. The offline page calls native model inference through a narrowly scoped interface or opens a native classifier Activity. Test it with airplane mode before launch and after a previously authenticated session.

Match these flows, not just colors: camera/gallery, image preview, scan result, assessment parameters, saved local history with All / week / month / year filters, expandable result details, return to online screen, and accessible back navigation. Use the current `static/style.css` and farmer templates as design reference; avoid copying server templates with Django tags as raw Android assets. Admin and superadmin see their existing online screens or an offline-unavailable message, never farmer offline data.

## Windows Android Studio build steps

1. Install Android Studio, JDK 17, and Android SDK/Build Tools for GitHub's `android/` project (its Gradle module currently sets compile/target SDK 36). Do not open `android-offline/` as the final app.
2. Clone the GitHub repository and open its **`android/`** folder in Android Studio. Confirm its `farmerBaseUrl` matches the HTTPS origin that works in Chrome; avoid a stale IP, test server, or second login database. `127.0.0.1` is only the bundled offline server.
3. Switch to the integration branch created above:

   ```powershell
   git switch feature/offline-farmer-classifier
   ```

4. Fix online-first startup, then add the Kotlin classifier, exact assets, farmer-only offline screen, and pending queue. Keep `com.viscane.app` if that is the installed app's real application ID, the portal URL, online API route, cookie/session handling, and release signing setup. Do not add another farmer credential store.
5. Apply the status-bar setup below and match the offline UI checklist above. Use Android's camera/gallery contracts already implemented in the Kotlin project, adapting them to the WebView app.
6. In Android Studio, let Gradle sync, then choose **Build > Rebuild Project** and **Run** on a physical phone. Exercise login and online scan before testing airplane mode.
7. Build a debug APK with **Build > Build APK(s)**, or run in PowerShell if the WebView repository includes a Gradle wrapper:

   ```powershell
   .\gradlew.bat :app:assembleDebug
   ```

   For a **release** build, provide the real HTTPS origin through `-PfarmerBaseUrl=...`, use the existing private signing setup, and increase `versionCode`. Debug builds in this project add `.debug` to the application ID, so they install beside the production app and do not test an in-place update.

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

The black strip containing the phone clock, signal, and battery is controlled by Android. GitHub's `android/app/src/main/res/values/themes.xml` currently sets the bars to black, while `MainActivity.kt` already opts into edge-to-edge and applies system-bar insets. Change those **existing** settings in `android/`, then verify on the target phone; do not add a second inset handler.

Add these imports:

```kotlin
import android.graphics.Color
import androidx.core.view.WindowInsetsControllerCompat
```

Then add this inside `onCreate()` after `super.onCreate(...)`:

```kotlin
window.statusBarColor = Color.rgb(11, 107, 56) // #0B6B38
window.navigationBarColor = Color.rgb(11, 107, 56)

WindowInsetsControllerCompat(window, window.decorView).apply {
    isAppearanceLightStatusBars = false
    isAppearanceLightNavigationBars = false
}
```

On supported Android versions this sets white system icons against green bars. Android 15/16 edge-to-edge behavior can make the status bar transparent; then draw the same green behind the inset area rather than relying on `statusBarColor` alone. Verify the title and bottom navigation are not hidden by system bars. Put this in the combined app's Activity/theme, not Django or a separate starter APK.

Replace the existing black values inside `Theme.Viscane` in `android/app/src/main/res/values/themes.xml`:

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
- [ ] One installed APK and launcher icon open online farmer pages and the visually matched offline farmer screen; no separate “VISCANE Offline” app is required.
- [ ] The final APK contains both ONNX models and nine labels, and camera/gallery classification works in airplane mode on real photos.
- [ ] The offline screen matches the online green header, font, scan card, bottom navigation, log filters, and expandable details on the actual phone.
- [ ] A previously authenticated farmer can save an offline result, reopen the app, and still see `Pending sync`; a fresh device with no prior login cannot impersonate a farmer.
- [ ] Logging out and signing in as another farmer does not expose or submit the prior farmer’s pending data.
- [ ] **Release gate for sync:** a reviewed server endpoint exists, server ownership and UUID deduplication are tested, and one reconnected record appears exactly once in farmer history plus admin and superadmin views. If this gate is unmet, keep sync disabled and label records `Pending sync`.
- [ ] Installing as an update preserves the app's online session/local pending records and does not require wiping app data.

## Copy/paste prompt for the Android developer

```text
Work in GitHub's android/ WebView project and produce ONE update APK with the
SAME production applicationId and release signing key. Faye must also share
the separate local Kotlin classifier project; it is not in GitHub's older
android-offline Java starter. The basic Java fallback screen has no bundled
model. The separate Kotlin classifier project contains resnet18.onnx,
yolov8.onnx, labels.txt (nine exact classes), model_config.json,
OfflineClassifier.kt, and Preprocessing.kt. Port these into the existing APK;
do not replace the WebView Activity or online login with the starter Activity.

The current WebView Activity always starts an embedded local Django server with
its own SQLite users. Make it open the configured production HTTPS farmer site
first when reachable, and use the bundled farmer UI only as an offline fallback
for a farmer previously authenticated online. Do not switch to local Django
because of an HTTP 500. Fix the URL/login issue before doing classifier work.

For logged-in farmers, retain the existing online Django pages and online scan
API. When unreachable, show a bundled farmer offline screen with the same solid
green header, large readable font, scan card, bottom navigation, filtered logs,
and expandable details as the online portal. Bundle every needed CSS/icon/font
asset so it works in airplane mode. Add camera/gallery and local ONNX inference.
Save results per authenticated farmer as encrypted pending records and clearly
mark them Pending sync until the server confirms persistence. Keep admin and
superadmin routes online-only and protect them from any farmer offline bridge.

Do not alter the computer-vision API, separate classifier service, Django user
records, or existing history. The current /api/scan/predict route is NOT an
offline-result sync endpoint. Before implementing sync, coordinate with Faye on
an authenticated, farmer-owned, UUID-idempotent server contract that makes one
record visible to farmer, admin, and superadmin. Faye alone handles server
backup/deployment. Without that contract, leave auto-sync disabled and report
the blocker honestly; do not fabricate server success or duplicate records.

On Windows, build and test the combined APK on a physical phone. Verify Chrome
and APK use the same production HTTPS URL; test online login and scan, airplane
mode, app restart, reconnect, no duplicate history, both admin roles, and an
in-place update retaining data. Document changed files, exact test results,
remaining sync dependency, and APK applicationId/versionCode/signature.
```

## Copy/paste prompt for Faye (server owner)

```text
Please review the Android developer's proposed offline sync payload and UUID.
Check that the server authenticates the farmer from its existing session/token,
validates the model/version/labels, stores an offline scan once per UUID and
farmer, and returns the canonical record ID. Confirm the resulting history is
visible in existing farmer, admin, and superadmin views. Preserve the online
prediction API and current data. Back up production first, test in staging,
then deploy any additive backend change yourself. Give the Android developer
the endpoint contract and test account, not SSH/database credentials.
```
