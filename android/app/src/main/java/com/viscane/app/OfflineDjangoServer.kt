package com.viscane.app

import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.util.UUID

/** Starts the bundled farmer Django project against a private, app-local SQLite database. */
object OfflineDjangoServer {
    private const val ASSET_ROOT = "django-server"
    private const val SERVER_DIR = "django-server"
    private const val DATABASE_FILE = "viscane-offline.sqlite3"
    private const val SECRET_FILE = "viscane-offline.secret"
    private const val VERSION_PREFS = "offline_django_server"
    private const val VERSION_KEY = "assets_version"

    @Synchronized
    fun start(context: Context): Int {
        val app = context.applicationContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))

        val root = File(app.filesDir, SERVER_DIR)
        val prefs = app.getSharedPreferences(VERSION_PREFS, Context.MODE_PRIVATE)
        if (!root.isDirectory || prefs.getInt(VERSION_KEY, 0) != BuildConfig.VERSION_CODE) {
            if (root.canonicalFile.parentFile != app.filesDir.canonicalFile) {
                error("Unsafe embedded server asset directory")
            }
            // Refresh packaged code in place. The Django runtime stores farmer uploads
            // under this tree, so deleting it during an APK update would erase local data.
            root.mkdirs()
            copyAssets(app, ASSET_ROOT, root)
            prefs.edit().putInt(VERSION_KEY, BuildConfig.VERSION_CODE).apply()
        }

        val secret = File(app.filesDir, SECRET_FILE).let { file ->
            if (!file.exists()) file.writeText(UUID.randomUUID().toString() + UUID.randomUUID())
            file.readText().trim()
        }
        val database = File(app.filesDir, DATABASE_FILE)
        return Python.getInstance().getModule("viscane_embedded")
            .callAttr("start", root.absolutePath, database.absolutePath, secret)
            .toInt()
    }

    private fun copyAssets(context: Context, assetPath: String, destination: File) {
        val entries = context.assets.list(assetPath).orEmpty()
        if (entries.isEmpty()) {
            destination.parentFile?.mkdirs()
            context.assets.open(assetPath).use { input -> destination.outputStream().use(input::copyTo) }
            return
        }
        destination.mkdirs()
        entries.forEach { name ->
            copyAssets(context, "$assetPath/$name", File(destination, name))
        }
    }
}
