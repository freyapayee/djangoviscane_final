# Android WebView app: status bar color

The black strip showing the clock, signal, and battery is controlled by the Android app, not the Django website.

In the WebView app's `MainActivity.kt`, add these imports:

```kotlin
import android.graphics.Color
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsControllerCompat
```

Then add this inside `onCreate()` after `super.onCreate(...)`:

```kotlin
window.statusBarColor = Color.rgb(11, 107, 56) // VISCANE green: #0B6B38
window.navigationBarColor = Color.rgb(11, 107, 56)

WindowCompat.setDecorFitsSystemWindows(window, true)

WindowInsetsControllerCompat(window, window.decorView).apply {
    isAppearanceLightStatusBars = false
    isAppearanceLightNavigationBars = false
}
```

This changes the status and navigation bars to VISCANE green and keeps their icons white.

If the project uses a theme XML file, also add these entries inside its app theme:

```xml
<item name="android:statusBarColor">#0B6B38</item>
<item name="android:navigationBarColor">#0B6B38</item>
<item name="android:windowLightStatusBar">false</item>
<item name="android:windowLightNavigationBar">false</item>
```

Rebuild and reinstall the APK after making the change.
