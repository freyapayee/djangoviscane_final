# VISCANE offline Android starter

This is a standalone native farmer assessment app you can open in Android Studio.
It performs manual agronomic calculations, shows the existing variety-specific
reference guides, saves assessments in private device SQLite storage, and exports
saved assessments as JSON through Android's file picker. It works from the first
launch without a Django server or an internet connection. It requests no internet,
camera, or storage permissions.

This is the offline foundation, not a complete conversion of the Django application.
Photo classification, accounts, admin screens, announcements, server history,
DeepSeek translations, and synchronization are not included. All device users share
the same local history. Uninstalling or clearing app storage deletes that history;
use JSON export to retain a copy. There is no JSON import or server upload yet.

## Open in Android Studio

1. From the Django repository root, regenerate the integration ZIP:
   ```sh
   python3 scripts/export_android_offline.py
   ```
   Output: `artifacts/android/viscane-offline.zip`. Only explicitly selected project
   source and public rules are exported; no database, accounts, uploads, or secrets.
2. Extract the ZIP, then choose **File → Open** and select `viscane-offline`.
   You can also open this repository's `android-offline` folder directly.
3. Use JDK 17 and install Android SDK platform 36 and Build Tools 35.0.0 in SDK
   Manager. The Android plugin is pinned to 8.10.1, with Gradle 8.11.1.
4. This source package does not include a binary Gradle wrapper. Install Gradle
   8.11.1, choose that local Gradle distribution in Android Studio's Gradle settings,
   and sync. Alternatively, in this folder run `gradle wrapper` using Gradle 8.11.1
   to generate the wrapper, then sync using it. Dependencies require internet for
   the first build; the installed app works offline.
5. Select **app**, connect an Android 6.0+ device or emulator, and press **Run**.
   Use **Build → Generate Signed App Bundle / APK** when ready to distribute.
   The starter targets API 35; review current store requirements before publishing.

Build tools and JDK versions follow the official
[Android Gradle plugin compatibility table](https://developer.android.com/build/releases/agp-8-10-0-release-notes).

## Add to an existing Android app

Copy `OfflineCalculator.java` and the generated `OfflineRules.java` into your app,
keeping their package or updating it consistently. They use plain Java with no
Android dependencies. Example:

```java
// VMC 84-524, 1.5 ha, 2 plowings, 3 weedings, 2 fertilizer applications,
// new plant, no RSSI infection, manually observed mature status.
OfflineCalculator.Result result = OfflineCalculator.calculate(
    0, 1.5, 2, 3, 2, 1, false, 2);
double totalLkg = result.totalLkg;
```

Variety indices follow `OfflineRules.VARIETIES`. Crop stages are 1=new plant,
2=first ratoon, 3=second ratoon. Maturity is 0=unknown, 1=not mature, 2=mature,
3=over mature. Counts must be 1–3, area must be positive and finite.

For the screen and persistence, also copy `MainActivity.java` and
`AssessmentStore.java`, and register the activity in your manifest. Launch it with
`startActivity(new Intent(this, com.viscane.offline.MainActivity.class));`.
The generated `assets/offline-rules.json` is a portable public rules bundle if you
prefer to implement a Kotlin client.

## Calculation contract

The exporter reads public constants from `core/services.py` and the actual farmer
route's `custom_weights` from `core/views.py`. Do not substitute default variety
weights: the website currently uses a common override. Regenerate after changing
server calculation rules. A SHA-256 rules version identifies the source snapshot.

Yield uses the sum of negative feature contributions plus maturity adjustment.
Positive contributions affect the website's quality score but do not increase
yield. The starter does not invent a visual confidence or quality score. Maturity
and variety are entered manually and saved as `assessment_source: manual`.
Unknown maturity applies zero maturity adjustment. The reference guides are the
existing English text; the starter does not reproduce the full web recommendation
selection or language system.

`lkgPerTon` matches `predicted_lkg_tc`; `totalTons` matches the website's
`predicted_tc_ha` field, which already includes the selected hectares despite its
name. `totalLkg` is their product. Guides, numeric estimates, and manual observations
do not constitute image model output.

Exported records use UUIDs, Unix milliseconds, a schema version, the rules version,
inputs, and outputs. They are device-local records with no authenticated Django
user association. Future sync needs authenticated APIs, explicit record ownership,
UUID deduplication, validation, conflict handling, and user-visible status before
these records can enter the server database.

## Offline photo recognition still required

The Django project calls a separate `/predict` service. It contains no trained
`.tflite` or `.onnx` model to bundle. To add real offline photo classification:

1. Obtain the trained model and its exact labels, input dimensions, normalization,
   channel order, output interpretation, and model license from the classifier project.
2. Convert it to an Android-supported runtime and bundle the model and metadata.
3. Implement image selection/capture and reproduce preprocessing exactly.
4. Compare on-device outputs with the classifier on a labeled validation dataset,
   including unsupported images. Only then feed verified predictions to the calculator.

## Verification

From the Django root, `python -m unittest scripts.test_android_offline` checks
safe packaging and the generated calculation fixtures against the real backend.
With a JDK available it also compiles and runs the Java calculator across all
three varieties, three stages, both infection states, four maturity states, and
multiple areas. Set `JAVA_HOME` to a full JDK when necessary. Android assembly and
device acceptance are separate checks:

- Disable Wi-Fi and mobile data before first launch, calculate, close/reopen,
  and confirm history remains.
- Export JSON to local Downloads; compare inputs and numeric results with the web
  calculator using the same manually selected variety and maturity.
- Verify invalid/empty area, rotation, large font, export cancellation, and disk errors.

No APK or device verification is implied by a source export.
