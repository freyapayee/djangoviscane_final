package com.viscane.offline

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.Color
import android.graphics.Typeface
import android.content.res.ColorStateList
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.activity.ComponentActivity
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.exifinterface.media.ExifInterface
import java.io.File
import java.util.concurrent.Executors
import java.util.Calendar

class OfflineScanActivity : ComponentActivity() {
    private val worker = Executors.newSingleThreadExecutor()
    private var classifier: OfflineClassifier? = null
    private var cameraUri: Uri? = null
    private lateinit var status: TextView
    private lateinit var preview: ImageView
    private lateinit var camera: Button
    private lateinit var gallery: Button
    private lateinit var history: TextView
    private var farmerId: Long = 0
    private val picker = registerForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) classify(uri)
    }
    private val capture = registerForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        val uri = cameraUri
        if (success && uri != null) classify(uri) else controls(true)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        farmerId = intent.getLongExtra("farmer_id", 0)
        if (farmerId <= 0) { finish(); return }
        cameraUri = savedInstanceState?.getString("cameraUri")?.let(Uri::parse)
        val green = Color.rgb(11, 107, 56)
        val dark = Color.rgb(16, 48, 37)
        WindowInsetsControllerCompat(window, window.decorView).isAppearanceLightStatusBars = false
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(12), dp(16), dp(12))
            setBackgroundColor(green)
        }
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(dp(16) + bars.left, dp(12) + bars.top, dp(16) + bars.right, dp(12) + bars.bottom)
            insets
        }
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(22), dp(20), dp(22))
            background = rounded(green, 24)
        }
        header.addView(TextView(this).apply { text = "Scan Sugarcane"; textSize = 26f; setTextColor(Color.WHITE); setTypeface(null, Typeface.BOLD) })
        header.addView(TextView(this).apply { text = "Offline photo recognition · stored on this device"; textSize = 16f; setTextColor(Color.WHITE) })
        header.addView(TextView(this).apply {
            text = "Offline · ${java.text.SimpleDateFormat("EEE, MMM d", java.util.Locale.getDefault()).format(java.util.Date())}"
            textSize = 18f
            setTextColor(Color.WHITE)
            setTypeface(null, Typeface.BOLD)
            setPadding(0, dp(12), 0, 0)
        })
        root.addView(header, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(16) })

        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(18), dp(18), dp(18))
            background = rounded(Color.WHITE, 22)
            elevation = dp(3).toFloat()
        }
        card.addView(TextView(this).apply { text = "Sugarcane assessment"; textSize = 22f; setTextColor(dark); setTypeface(null, Typeface.BOLD) })
        card.addView(TextView(this).apply { text = "Choose a clear photo. Variety and maturity are estimated on your phone."; textSize = 16f; setTextColor(dark) })
        preview = ImageView(this).apply {
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "Selected sugarcane photo"
            background = rounded(Color.rgb(237, 247, 240), 18)
        }
        card.addView(preview, LinearLayout.LayoutParams(-1, dp(230)).apply { topMargin = dp(14) })
        camera = Button(this).apply { text = "Open camera"; textSize = 16f; isEnabled = false; backgroundTintList = ColorStateList.valueOf(green); setTextColor(Color.WHITE) }
        gallery = Button(this).apply { text = "Upload photo"; textSize = 16f; isEnabled = false; backgroundTintList = ColorStateList.valueOf(green); setTextColor(Color.WHITE) }
        card.addView(camera, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        card.addView(gallery, LinearLayout.LayoutParams(-1, -2))
        status = TextView(this).apply { text = "Loading offline models…"; textSize = 17f; setTextColor(dark); setPadding(0, dp(12), 0, dp(12)) }
        card.addView(ScrollView(this).apply { addView(status) }, LinearLayout.LayoutParams(-1, dp(150)))
        history = TextView(this).apply { text = "Loading pending history…"; textSize = 16f; setTextColor(dark) }
        card.addView(history)
        root.addView(card, LinearLayout.LayoutParams(-1, 0, 1f))
        val navigation = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            background = rounded(Color.WHITE, 20)
        }
        fun nav(label: String, action: () -> Unit) {
            navigation.addView(TextView(this).apply {
                text = label
                textSize = 12f
                gravity = android.view.Gravity.CENTER
                setTextColor(green)
                setTypeface(null, Typeface.BOLD)
                minHeight = dp(66)
                setOnClickListener { action() }
            }, LinearLayout.LayoutParams(0, -2, 1f))
        }
        nav("Home") { finish() }
        nav("Recommendations") { AlertDialog.Builder(this).setMessage("Reconnect to see your current recommendations.").setPositiveButton("OK", null).show() }
        nav("Input Logs") { showPendingHistory() }
        nav("Profile") { AlertDialog.Builder(this).setMessage("Farmer account #$farmerId · Offline scans stay on this device until synchronized.").setPositiveButton("OK", null).show() }
        root.addView(navigation, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        setContentView(root)
        refreshHistory()
        gallery.setOnClickListener { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }
        camera.setOnClickListener {
            try {
                val directory = File(cacheDir, "camera").apply { mkdirs() }
                val photo = File(directory, "capture.jpg")
                cameraUri = FileProvider.getUriForFile(this, "$packageName.fileprovider", photo)
                controls(false)
                capture.launch(cameraUri!!)
            } catch (error: Exception) {
                status.text = "Camera unavailable: ${error.localizedMessage}"
                controls(true)
            }
        }
        worker.execute {
            try {
                classifier = OfflineClassifier(applicationContext)
                runOnUiThread { if (!isDestroyed) { status.text = "Ready · 9 classes · no connection needed"; controls(true) } }
            } catch (error: Exception) {
                runOnUiThread { if (!isDestroyed) status.text = "Could not load models: ${error.localizedMessage}" }
            }
        }
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    private fun rounded(color: Int, radiusDp: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radiusDp).toFloat()
    }

    private fun refreshHistory() {
        worker.execute {
            val message = runCatching {
                val store = OfflineScanStore(this)
                val records = store.pending(farmerId)
                if (records.isEmpty()) "No pending scans on this device."
                else "Pending sync (${store.count(farmerId)})\n" + records.joinToString("\n") {
                    "${it.label.replace("__", " · ").replace('_', ' ')} · ${java.text.DateFormat.getDateTimeInstance().format(java.util.Date(it.createdAt))}"
                }
            }.getOrElse { "Could not read local history: ${it.localizedMessage}" }
            runOnUiThread { if (!isDestroyed) history.text = message }
        }
    }

    private fun showPendingHistory() {
        val periods = arrayOf("All", "This week", "This month", "This year")
        AlertDialog.Builder(this).setTitle("Filter input logs").setItems(periods) { _, index ->
            worker.execute {
                val result = runCatching {
                    val scans = OfflineScanStore(this).summaries(farmerId)
                    val now = Calendar.getInstance()
                    scans.filter { scan ->
                        if (index == 0) true else {
                            val date = Calendar.getInstance().apply { timeInMillis = scan.createdAt }
                            when (index) {
                                1 -> date.get(Calendar.YEAR) == now.get(Calendar.YEAR) && date.get(Calendar.WEEK_OF_YEAR) == now.get(Calendar.WEEK_OF_YEAR)
                                2 -> date.get(Calendar.YEAR) == now.get(Calendar.YEAR) && date.get(Calendar.MONTH) == now.get(Calendar.MONTH)
                                else -> date.get(Calendar.YEAR) == now.get(Calendar.YEAR)
                            }
                        }
                    }
                }
                runOnUiThread {
                    if (isDestroyed) return@runOnUiThread
                    result.onSuccess { scans ->
                        if (scans.isEmpty()) {
                            AlertDialog.Builder(this).setMessage("No pending scans for this period.").setPositiveButton("OK", null).show()
                        } else {
                            val items = scans.map { "${it.label.replace("__", " · ").replace('_', ' ')} · Pending sync" }.toTypedArray()
                            AlertDialog.Builder(this).setTitle("Input Logs · ${periods[index]}").setItems(items) { _, position ->
                                val selected = scans[position]
                                worker.execute {
                                    val photo = runCatching { OfflineScanStore(this).read(farmerId, selected.id).jpeg }
                                    runOnUiThread {
                                        photo.onSuccess {
                                            preview.setImageBitmap(BitmapFactory.decodeByteArray(it, 0, it.size))
                                            status.text = "${selected.label.replace("__", " · ").replace('_', ' ')}\nConfidence: ${"%.1f".format(selected.confidence * 100)}%\nPending sync"
                                        }.onFailure { status.text = "Could not open saved photo: ${it.localizedMessage}" }
                                    }
                                }
                            }.setPositiveButton("Close", null).show()
                        }
                    }.onFailure { error ->
                        AlertDialog.Builder(this).setMessage("Could not read input logs: ${error.localizedMessage}").setPositiveButton("OK", null).show()
                    }
                }
            }
        }.show()
    }

    private fun controls(enabled: Boolean) {
        camera.isEnabled = enabled && classifier != null
        gallery.isEnabled = enabled && classifier != null
    }

    private fun decode(uri: Uri): Bitmap {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        contentResolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, bounds) }
        require(bounds.outWidth > 0 && bounds.outHeight > 0) { "Unsupported or damaged image" }
        // Refuse pathological inputs instead of silently downsampling before model preprocessing.
        require(bounds.outWidth.toLong() * bounds.outHeight <= 25_000_000) { "Choose an image of 25 megapixels or less" }
        require(maxOf(bounds.outWidth, bounds.outHeight).toDouble() / minOf(bounds.outWidth, bounds.outHeight) <= 100) { "Choose a photo with a less extreme aspect ratio" }
        val options = BitmapFactory.Options().apply { inPreferredConfig = Bitmap.Config.ARGB_8888; inScaled = false }
        val decoded = contentResolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, options) }
            ?: error("Could not decode image")
        val orientation = contentResolver.openInputStream(uri).use { stream ->
            requireNotNull(stream)
            ExifInterface(stream).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
        }
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.setScale(-1f, 1f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.setRotate(180f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.setScale(1f, -1f)
            ExifInterface.ORIENTATION_TRANSPOSE -> { matrix.setRotate(90f); matrix.postScale(-1f, 1f) }
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.setRotate(90f)
            ExifInterface.ORIENTATION_TRANSVERSE -> { matrix.setRotate(-90f); matrix.postScale(-1f, 1f) }
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.setRotate(-90f)
        }
        if (matrix.isIdentity) return decoded
        val oriented = Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height, matrix, false)
        if (oriented !== decoded) decoded.recycle()
        return oriented
    }

    private fun classify(uri: Uri) {
        controls(false)
        preview.setImageDrawable(null)
        status.text = "Analyzing photo on this device…"
        worker.execute {
            try {
                val bitmap = decode(uri)
                val predictions = try { classifier!!.classify(bitmap) } catch (error: Throwable) { bitmap.recycle(); throw error }
                val top = predictions.first()
                val saved = runCatching { OfflineScanStore(this).save(farmerId, top, bitmap) }
                runOnUiThread {
                    if (isDestroyed) { bitmap.recycle(); return@runOnUiThread }
                    preview.setImageBitmap(bitmap)
                    status.text = "Variety: ${top.variety}\nMaturity: ${top.maturity}\nConfidence: ${"%.1f".format(top.confidence * 100)}%\n${if (saved.isSuccess) "Saved on device · Pending sync" else "Could not save: ${saved.exceptionOrNull()?.localizedMessage}"}\n\nTop matches:\n" +
                        predictions.take(3).joinToString("\n") { "${it.variety} · ${it.maturity}: ${"%.1f".format(it.confidence * 100)}%" }
                    controls(true)
                    if (saved.isSuccess) refreshHistory()
                }
            } catch (error: Exception) {
                runOnUiThread { if (!isDestroyed) { status.text = "Could not analyze photo: ${error.localizedMessage}"; controls(true) } }
            }
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        cameraUri?.let { outState.putString("cameraUri", it.toString()) }
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        worker.execute { classifier?.close(); classifier = null }
        worker.shutdown()
        super.onDestroy()
    }
}
