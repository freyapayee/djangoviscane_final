# Farmer-only Android implementation

The implemented client is the Kotlin WebView project in `../android/`, connected
to this Django backend. See [ANDROID.md](../ANDROID.md) for setup, deployment,
signing and acceptance checks. Administrator screens belong to the protected
website and are excluded from the APK.

The APK validates the exact origin and farmer routes. Production requires an
HTTPS origin; Django VISCANE_FARMER_ONLY=true blocks administrator endpoints
independently of client headers. Cookie sessions and CSRF protect server-rendered
forms; images are validated before reaching the classifier. Native capture and
gallery upload are separate actions.

Farmer scope: authentication, dashboard, scan capture/upload/results, agronomic
assessment, recommendations, history, announcements, feedback and profile.
The APK requires a running server and has no offline predictions.

Room, Retrofit, Compose, CameraX and token authentication are optional future
native rewrite work, not prerequisites for the current APK. Define versioned
farmer JSON APIs first if pursuing that rewrite. Continue enforcing authorization
and record ownership on Django. Do not add administrator screens to this APK.
