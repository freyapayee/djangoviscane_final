# Android readiness — October 3, 2026

The farmer Android implementation builds successfully as a debug APK. Production
distribution is pending the real HTTPS host, deployment configuration, signing
and physical-device acceptance. No production deployment or live data migration
was performed.

## Completed

| Step | Result |
|---|---|
| Django backend / Android project alignment | `../ANDROID.md` now documents the Django WebView workflow |
| Farmer-only APK | Exact-origin/path restrictions, farmer entry at all widths, no release server editing or external-browser menu |
| Farmer server boundary | `VISCANE_FARMER_ONLY=true` blocks administrator endpoints independently of client markers |
| Forms and authentication | CSRF restored, form/AJAX tokens supplied, sessions rotated on login and cleared on logout |
| Uploaded images | Size/content validation; new scans use private storage and ownership-checked image delivery |
| Camera/gallery | Separate native Take Photo and gallery actions; permission origin checks and denial fallback |
| Android lifecycle/layout | System-bar/cutout/keyboard insets, Back handling, page state, refresh completion and connection retry |
| Android build | Gradle wrapper added, JDK 17 / AGP 8.10.1 / Kotlin 2.1.20 / SDK 36 verified |
| Release configuration | HTTPS origin required, cleartext/debugging disabled, backup/transfer exclusions configured |
| Existing build defects | Preference and AppCompat menu XML corrected; application label/icon supplied |

## Verification

- Django: **36 tests passed** using a disposable test database.
- Browser: **57 acceptance checks passed**, including CSRF login/profile updates,
  image upload with a mocked classifier, result display, private-image access,
  administrator blocking and zero page-wide overflow at 320, 360, 390, 412, 768
  and 844×390 landscape sizes. No JavaScript page errors were observed.
- Android: `assembleDebug`, `testDebugUnitTest`, and `lintDebug` **passed**.
  All three navigation test methods passed. Lint reports zero errors and three
  advisories: newer Gradle available, intentionally enabled JavaScript required
  by the web UI, and launcher-logo shape polish.
- Release guard: `preReleaseBuild` correctly refused to run without a configured
  HTTPS farmer origin. No placeholder-host release APK was generated.
- Django deployment check with temporary production settings: no errors; two
  domain-policy advisories for HSTS subdomains/preload. Enable those only after
  verifying the domain-wide HTTPS policy, as documented in the setup guide.

Debug APK: `../android/app/build/outputs/apk/debug/app-debug.apk`.
SHA-256: `1BA371D5543FE9179BB6E3F31418F1702743F45620F872D7A83C6FD75E07E2D9`.
Browser evidence: `.local/android-readiness/verification.json` and screenshots.
Android evidence: `../android/app/build/reports/lint-results-debug.html` and
`../android/app/build/test-results/testDebugUnitTest/`.

The Windows build initially failed in the long workspace cache path. Using the
standard shorter user Gradle cache resolved that failure. No lint baseline or
error suppression was introduced.

## Required before distributing

1. Supply the production farmer HTTPS origin. Deploy the farmer instance with
   `VISCANE_FARMER_ONLY=true`; keep administrators on a separate protected host.
2. Configure TLS, trusted proxy headers, secrets, database, collected static
   assets, persistent private uploads and backups. Explicitly deny the legacy
   `/static/uploads/cv_scans/` directory at the proxy/static server so old scan
   images are available only through authenticated Django delivery.
3. Verify connectivity and real predictions against the deployed classifier.
   The browser upload check used a mock and does not prove model accuracy or
   live-service availability. Secure the classifier hop with TLS/private networking.
4. Generate and preserve a release signing key, then build/sign the APK or AAB
   with the real `farmerBaseUrl`. The debug APK is for local testing.
5. Install on physical Android devices and verify native capture, gallery,
   permissions, rotation, keyboard, enlarged text, offline/retry and complete
   farmer workflows. No device or configured emulator was available in this session.

Existing scan files and database records were retained. New storage behavior does
not require a schema migration. Use [ANDROID.md](../ANDROID.md) for commands and
the release acceptance checklist.
