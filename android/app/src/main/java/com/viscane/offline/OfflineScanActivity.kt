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
import android.text.InputType
import android.util.Base64
import android.webkit.CookieManager
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
import java.util.Locale

class OfflineScanActivity : ComponentActivity() {
    private val worker = Executors.newSingleThreadExecutor()
    private var classifier: OfflineClassifier? = null
    private var cameraUri: Uri? = null
    private lateinit var status: TextView
    private lateinit var result: TextView
    private lateinit var preview: ImageView
    private lateinit var camera: Button
    private lateinit var gallery: Button
    private lateinit var history: TextView
    private lateinit var area: EditText
    private lateinit var variety: Spinner
    private lateinit var plowing: Spinner
    private lateinit var weeding: Spinner
    private lateinit var fertilizer: Spinner
    private lateinit var stage: Spinner
    private lateinit var infection: Spinner
    private lateinit var maturity: Spinner
    private lateinit var assessment: TextView
    private lateinit var recommendationsView: TextView
    private lateinit var contentScroll: ScrollView
    private var latestScanId: String? = null
    private var latestScanLabel: String? = null
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
        if (farmerId <= 0 || getSharedPreferences("farmer_offline_access", MODE_PRIVATE)
                .getLong("farmer_id", 0) != farmerId) { finish(); return }
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
        header.addView(Button(this).apply {
            text = "Farmer menu"; textSize = 16f
            setOnClickListener { showFarmerMenu() }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
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
        result = TextView(this).apply {
            visibility = android.view.View.GONE
            textSize = 20f
            setTextColor(dark)
            setTypeface(null, Typeface.BOLD)
            setPadding(dp(16), dp(16), dp(16), dp(16))
            background = rounded(Color.rgb(232, 247, 237), 18)
        }
        card.addView(result, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        status = TextView(this).apply { text = "Loading offline models…"; textSize = 16f; setTextColor(dark); setPadding(0, dp(12), 0, dp(12)) }
        card.addView(status)
        card.addView(TextView(this).apply {
            text = "Assessment parameters"; textSize = 22f; setTextColor(dark); setTypeface(null, Typeface.BOLD)
            setPadding(0, dp(16), 0, dp(4))
        })
        card.addView(TextView(this).apply {
            text = "Use a scan result or enter the variety and maturity yourself. Calculations and guidance run on this phone."
            textSize = 16f; setTextColor(dark)
        })
        variety = choice(card, "Sugarcane variety", OfflineRules.VARIETIES)
        card.addView(TextView(this).apply { text = "Area in hectares"; textSize = 17f; setTextColor(dark) })
        area = EditText(this).apply {
            hint = "e.g. 1.5"
            textSize = 18f
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL
            contentDescription = "Area in hectares"
        }
        card.addView(area)
        val counts = arrayOf("1 time", "2 times", "3 times")
        plowing = choice(card, "Plowing", counts)
        weeding = choice(card, "Weeding", counts)
        fertilizer = choice(card, "Fertilizer applications", counts)
        stage = choice(card, "Crop stage", arrayOf("New plant", "1st ratoon", "2nd ratoon"))
        infection = choice(card, "RSSI infection observed", arrayOf("No", "Yes"))
        maturity = choice(card, "Maturity", arrayOf("Unknown / manual", "Not mature", "Mature", "Over mature"))
        card.addView(Button(this).apply {
            text = "Calculate and save on this phone"; textSize = 16f
            backgroundTintList = ColorStateList.valueOf(green); setTextColor(Color.WHITE)
            setOnClickListener { calculateAssessment() }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
        assessment = TextView(this).apply { textSize = 18f; setTextColor(dark); setPadding(0, dp(10), 0, dp(8)) }
        card.addView(assessment)
        recommendationsView = TextView(this).apply { textSize = 17f; setTextColor(dark) }
        card.addView(recommendationsView)
        history = TextView(this).apply { text = "Loading saved results…"; textSize = 16f; setTextColor(dark) }
        card.addView(history)
        contentScroll = ScrollView(this).apply { fillViewport = true; addView(card) }
        root.addView(contentScroll, LinearLayout.LayoutParams(-1, 0, 1f))
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
        nav("Home") { contentScroll.smoothScrollTo(0, 0) }
        nav("Recommendations") { showRecommendations() }
        nav("Input Logs") { showSavedHistory() }
        nav("Profile") { showProfile() }
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

    private fun choice(card: LinearLayout, label: String, options: Array<String>): Spinner {
        card.addView(TextView(this).apply {
            text = label; textSize = 17f; setTextColor(Color.rgb(16, 48, 37))
            setPadding(0, dp(12), 0, 0)
        })
        return Spinner(this).also { spinner ->
            spinner.contentDescription = label
            spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, options).apply {
                setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            }
            card.addView(spinner)
        }
    }

    private fun formatAssessment(record: org.json.JSONObject): String = String.format(Locale.getDefault(),
        "Estimated LKG/TC: %.2f\nEstimated total cane: %.2f tons\nEstimated total LKG: %.2f",
        record.getDouble("lkg_per_ton"), record.getDouble("total_tons"), record.getDouble("total_lkg"))

    private fun formatRecommendations(record: org.json.JSONObject): String {
        val items = record.getJSONArray("recommendations")
        return (0 until items.length()).joinToString("\n\n") { index ->
            val item = items.getJSONObject(index)
            "${item.getString("category")} · ${item.getString("title")}\n${item.getString("meta")}"
        }
    }

    private fun calculateAssessment() {
        try {
            val hectares = area.text.toString().trim().replace(',', '.').toDouble()
            val v = variety.selectedItemPosition
            val p = plowing.selectedItemPosition + 1
            val w = weeding.selectedItemPosition + 1
            val f = fertilizer.selectedItemPosition + 1
            val s = stage.selectedItemPosition + 1
            val infected = infection.selectedItemPosition == 1
            val m = maturity.selectedItemPosition
            val estimate = OfflineCalculator.calculate(v, hectares, p, w, f, s, infected, m)
            val guides = OfflineRecommendations.generate(v, hectares, p, w, f, s, infected, m, estimate)
            val estimateText = String.format(Locale.getDefault(),
                "Estimated LKG/TC: %.2f\nEstimated total cane: %.2f tons\nEstimated total LKG: %.2f",
                estimate.lkgPerTon, estimate.totalTons, estimate.totalLkg)
            recommendationsView.text = "Recommendations\n\n" + guides.joinToString("\n\n") {
                "${it.category} · ${it.title}\n${it.detail}"
            }
            val matchedScan = latestScanId?.takeIf {
                val expected = when (v) { 0 -> "524"; 1 -> "847"; else -> "Mauritio" } + "__" +
                    arrayOf("", "Not_Mature", "Mature", "Over_Mature")[m]
                latestScanLabel == expected
            }
            val saved = runCatching { OfflineAssessmentStore(this).save(farmerId, v, hectares, p, w, f, s,
                infected, m, estimate, guides, matchedScan) }
            assessment.text = "$estimateText\n" + if (saved.isSuccess)
                "Saved on this phone · Server copy waiting · ${if (matchedScan == null) "Manual inputs" else "Linked to this scan"}"
            else "Result ready, but local save failed: ${saved.exceptionOrNull()?.localizedMessage}"
            if (saved.isSuccess) refreshHistory()
        } catch (error: Exception) {
            assessment.text = "Could not calculate or save: ${error.localizedMessage}"
        }
    }

    private fun showRecommendations() {
        val current = recommendationsView.text.toString()
        if (current.isNotBlank()) {
            AlertDialog.Builder(this).setTitle("Offline recommendations").setMessage(current).setPositiveButton("OK", null).show()
            return
        }
        worker.execute {
            val latest = runCatching {
                Pair(OfflineAssessmentStore(this).records(farmerId).firstOrNull(),
                    OfflineFarmerCache(this).snapshot(farmerId)?.optJSONArray("recommendations"))
            }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                latest.onSuccess { (record, cached) ->
                    val message = when {
                        record != null -> formatRecommendations(record)
                        cached != null && cached.length() > 0 -> "Saved online recommendations (from last connection)\n\n" +
                            (0 until cached.length()).joinToString("\n\n") {
                                cached.getJSONObject(it).let { item ->
                                    "${item.optString("category")} · ${item.optString("title")}\n${item.optString("meta")}"
                                }
                            }
                        else -> "Enter assessment parameters and calculate to generate recommendations on this phone."
                    }
                    AlertDialog.Builder(this).setTitle("Offline recommendations")
                        .setMessage(message).setPositiveButton("OK", null).show()
                }.onFailure { error ->
                    AlertDialog.Builder(this).setMessage("Could not read saved recommendations: ${error.localizedMessage}")
                        .setPositiveButton("OK", null).show()
                }
            }
        }
    }

    private fun showFarmerMenu() {
        val items = arrayOf("Home", "Scan and assessment", "Recommendations", "Input Logs",
            "Profile", "News and announcements", "Notifications", "Feedback", "About VISCANE", "Tutorial",
            "Sign out on this phone")
        AlertDialog.Builder(this).setTitle("Offline farmer menu").setItems(items) { _, selected ->
            when (selected) {
                0, 1 -> contentScroll.smoothScrollTo(0, 0)
                2 -> showRecommendations()
                3 -> showSavedHistory()
                4 -> showProfile()
                5 -> showAnnouncements("News and announcements")
                6 -> showAnnouncements("Notifications")
                7 -> showFeedback()
                8 -> AlertDialog.Builder(this).setTitle("About VISCANE")
                    .setMessage("VISCANE supports sugarcane farmers with on-device variety and maturity recognition, agronomic estimates, and guidance. Saved scans and assessments synchronize with the farmer portal when connected.")
                    .setPositiveButton("OK", null).show()
                9 -> AlertDialog.Builder(this).setTitle("Offline tutorial")
                    .setMessage("1. Sign in online once.\n2. Open Offline Farmer Workspace.\n3. Capture or choose a sugarcane photo.\n4. Check the variety and maturity.\n5. Enter area and agronomic inputs, then calculate.\n6. Read recommendations and Input Logs.\n7. Reconnect using the same account to sync server copies.")
                    .setPositiveButton("OK", null).show()
                10 -> AlertDialog.Builder(this).setTitle("Sign out on this phone")
                    .setMessage("Offline work stays encrypted for this farmer. Signing in online again with the same account will unlock it. Continue?")
                    .setNegativeButton("Cancel", null)
                    .setPositiveButton("Sign out") { _, _ ->
                        getSharedPreferences("farmer_offline_access", MODE_PRIVATE)
                            .edit().remove("farmer_id").apply()
                        CookieManager.getInstance().removeAllCookies {
                            CookieManager.getInstance().flush()
                        }
                        finishAffinity()
                    }.show()
            }
        }.show()
    }

    private fun showProfile() {
        worker.execute {
            val cached = runCatching { OfflineFarmerCache(this).snapshot(farmerId) }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                cached.onSuccess { snapshot ->
                    val profile = snapshot?.optJSONObject("profile")
                    val draft = runCatching { OfflineFarmerCache(this).profileDraft(farmerId) }.getOrNull()
                    val message = if (profile == null) "Farmer account #$farmerId. Connect once to save your profile details on this phone."
                        else "${profile.optString("name")}\n${profile.optString("email")}\n${profile.optString("phone")}\n${profile.optString("barangay")}, ${profile.optString("municipality")}, ${profile.optString("province")}\n\nLast updated: ${snapshot.optString("fetched_at")}"
                    val pendingMessage = if (draft == null) "" else "\n\nProfile edit saved on this phone. Server confirmation is still waiting." +
                        draft.optString("sync_error").takeIf { it.isNotBlank() }?.let { "\nReview needed: $it" }.orEmpty()
                    val profileView = LinearLayout(this).apply {
                        orientation = LinearLayout.VERTICAL
                        setPadding(dp(18), dp(8), dp(18), dp(8))
                    }
                    profile?.optString("photo_base64")?.takeIf { it.isNotBlank() }?.let { encoded ->
                        runCatching { Base64.decode(encoded, Base64.DEFAULT) }.getOrNull()?.let { bytes ->
                            profileView.addView(ImageView(this).apply {
                                setImageBitmap(BitmapFactory.decodeByteArray(bytes, 0, bytes.size))
                                scaleType = ImageView.ScaleType.FIT_CENTER
                                contentDescription = "Saved profile photo"
                            }, LinearLayout.LayoutParams(-1, dp(160)))
                        }
                    }
                    profileView.addView(TextView(this).apply {
                        text = message + pendingMessage; textSize = 17f; setPadding(0, dp(8), 0, dp(8))
                    })
                    AlertDialog.Builder(this).setTitle("Saved profile")
                        .setView(ScrollView(this).apply { addView(profileView) })
                        .setNeutralButton("Edit details") { _, _ ->
                            if (profile != null) showProfileEditor(profile)
                            else AlertDialog.Builder(this).setMessage("Connect once to load your profile before editing it offline.")
                                .setPositiveButton("OK", null).show()
                        }
                        .setNegativeButton("Password / photo") { _, _ ->
                            AlertDialog.Builder(this).setMessage("Password changes require online verification of your current password. Photo updates need an authenticated upload. Your saved profile and offline work remain available now.")
                                .setPositiveButton("OK", null).show()
                        }.setPositiveButton("Close", null).show()
                }.onFailure { error ->
                    AlertDialog.Builder(this).setMessage("Could not read saved profile: ${error.localizedMessage}")
                        .setPositiveButton("OK", null).show()
                }
            }
        }
    }

    private fun showProfileEditor(profile: org.json.JSONObject) {
        val fields = linkedMapOf<String, EditText>()
        val labels = linkedMapOf("email" to "Email", "phone" to "Phone", "province" to "Province",
            "municipality" to "Municipality", "barangay" to "Barangay")
        val form = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(8), dp(18), dp(8))
        }
        labels.forEach { (key, label) ->
            form.addView(TextView(this).apply { text = label; textSize = 16f })
            fields[key] = EditText(this).also {
                it.setText(profile.optString(key))
                it.textSize = 17f
                it.isSingleLine = true
                form.addView(it)
            }
        }
        AlertDialog.Builder(this).setTitle("Edit profile offline")
            .setView(ScrollView(this).apply { addView(form) })
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Save on phone") { _, _ ->
                val values = fields.mapValues { it.value.text.toString() }
                worker.execute {
                    val saved = runCatching { OfflineFarmerCache(this).saveProfileDraft(farmerId,
                        profile.getString("email"), profile.getString("version"),
                        values.getValue("email"), values.getValue("phone"),
                        values.getValue("province"), values.getValue("municipality"), values.getValue("barangay")) }
                    runOnUiThread {
                        if (isDestroyed) return@runOnUiThread
                        AlertDialog.Builder(this).setMessage(if (saved.isSuccess)
                            "Profile changes are saved on this phone and will be checked by the server when you reconnect."
                            else "Could not save profile changes: ${saved.exceptionOrNull()?.localizedMessage}")
                            .setPositiveButton("OK", null).show()
                    }
                }
            }.show()
    }

    private fun showAnnouncements(title: String) {
        worker.execute {
            val cached = runCatching { Pair(OfflineFarmerCache(this).snapshot(farmerId),
                if (title == "Notifications") OfflineAssessmentStore(this).records(farmerId).firstOrNull() else null) }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                cached.onSuccess { (snapshot, recentAssessment) ->
                    val announcements = snapshot?.optJSONArray("announcements")
                    val news = if (announcements == null) "Connect once to save announcements on this phone. New announcements need internet."
                        else if (announcements.length() == 0) "No saved announcements yet."
                        else (0 until announcements.length()).joinToString("\n\n") { index ->
                            announcements.getJSONObject(index).let { "${it.optString("title")}\n${it.optString("message")}" }
                        }
                    val message = if (recentAssessment == null) news else
                        "Latest assessment suggestions\n${formatRecommendations(recentAssessment)}\n\nSaved announcements\n$news"
                    val dialog = AlertDialog.Builder(this).setTitle("$title · saved copy")
                        .setMessage(message).setPositiveButton("OK", null)
                    if (title == "Notifications" && announcements != null && announcements.length() > 0) {
                        dialog.setNeutralButton("Mark read") { _, _ ->
                            worker.execute {
                                val saved = runCatching { OfflineFarmerCache(this).markAnnouncementsRead(farmerId,
                                    announcements.getJSONObject(0).getInt("id")) }
                                runOnUiThread {
                                    if (isDestroyed) return@runOnUiThread
                                    AlertDialog.Builder(this).setMessage(if (saved.isSuccess)
                                        "Marked read on this phone. The online notification state will update after reconnecting."
                                        else "Could not save read state: ${saved.exceptionOrNull()?.localizedMessage}")
                                        .setPositiveButton("OK", null).show()
                                }
                            }
                        }
                    }
                    dialog.show()
                }.onFailure { error ->
                    AlertDialog.Builder(this).setMessage("Could not read saved announcements: ${error.localizedMessage}")
                        .setPositiveButton("OK", null).show()
                }
            }
        }
    }

    private fun showFeedback() {
        val field = EditText(this).apply {
            hint = "Write feedback for the VISCANE team"
            minLines = 3
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
        }
        AlertDialog.Builder(this).setTitle("Feedback · saved until connected")
            .setView(field)
            .setNeutralButton("Saved feedback") { _, _ -> showFeedbackHistory() }
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Save") { _, _ ->
                worker.execute {
                    val saved = runCatching { OfflineFarmerCache(this).saveFeedback(farmerId, field.text.toString()) }
                    runOnUiThread {
                        if (isDestroyed) return@runOnUiThread
                        AlertDialog.Builder(this).setMessage(if (saved.isSuccess)
                            "Feedback saved on this phone. Its server copy will sync when you reconnect."
                            else "Could not save feedback: ${saved.exceptionOrNull()?.localizedMessage}")
                            .setPositiveButton("OK", null).show()
                    }
                }
            }.show()
    }

    private fun showFeedbackHistory() {
        worker.execute {
            val saved = runCatching {
                val cache = OfflineFarmerCache(this)
                val localRecords = cache.feedback(farmerId)
                val localIds = localRecords.map { it.getString("id") }.toSet()
                val online = cache.snapshot(farmerId)?.optJSONArray("feedback")
                val remoteByOfflineId = if (online == null) emptyMap() else (0 until online.length()).map {
                    online.getJSONObject(it)
                }.filter { it.optString("offline_id").isNotBlank() }.associateBy { it.optString("offline_id") }
                fun replyText(item: org.json.JSONObject?): String {
                    val replies = item?.optJSONArray("replies") ?: return ""
                    return (0 until replies.length()).joinToString("") { index ->
                        "\nAdmin reply: ${replies.getJSONObject(index).optString("message")}"
                    }
                }
                val local = localRecords.map {
                    "${it.getString("message")} · ${if (it.getBoolean("synced")) "Server copy saved" else "Server copy waiting"}" +
                        replyText(remoteByOfflineId[it.getString("id")])
                }
                val remote = if (online == null) emptyList() else (0 until online.length()).map {
                    val item = online.getJSONObject(it)
                    if (item.optString("offline_id") in localIds) return@map ""
                    item.optString("message") + " · Last online copy" + replyText(item)
                }
                (local + remote).filter { it.isNotBlank() }.distinct().joinToString("\n\n")
                    .ifBlank { "No saved feedback yet." }
            }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                AlertDialog.Builder(this).setTitle("Saved feedback")
                    .setMessage(saved.getOrElse { "Could not read feedback: ${it.localizedMessage}" })
                    .setPositiveButton("OK", null).show()
            }
        }
    }

    private fun refreshHistory() {
        worker.execute {
            val message = runCatching {
                val store = OfflineScanStore(this)
                val records = store.summaries(farmerId)
                val assessments = OfflineAssessmentStore(this).records(farmerId)
                val onlineCount = OfflineFarmerCache(this).snapshot(farmerId)?.optJSONArray("history")?.length() ?: 0
                "Saved scans: ${store.totalCount(farmerId)} · Saved assessments: ${assessments.size} · Cached online records: $onlineCount · Server copies waiting: ${store.pendingCount(farmerId) + assessments.count { !it.getBoolean("synced") }}" +
                    if (records.isEmpty() && assessments.isEmpty()) "\nNo saved offline work on this device yet."
                    else "\n" + records.take(2).joinToString("\n") {
                        "Scan · ${displayVariety(it.label.substringBefore("__"))} · ${it.label.substringAfter("__").replace('_', ' ')}"
                    } + assessments.take(2).joinToString("") {
                        "\nAssessment · ${OfflineRules.VARIETIES[it.getInt("variety")]} · ${"%.2f".format(it.getDouble("total_lkg"))} LKG"
                    }
            }.getOrElse { "Could not read local history: ${it.localizedMessage}" }
            runOnUiThread { if (!isDestroyed) history.text = message }
        }
    }

    private fun displayVariety(value: String) = when (value) {
        "524" -> "VMC 84-524"
        "847" -> "VMC 84-947"
        "Mauritio" -> "MAURITIO RC888"
        else -> value
    }

    private fun showResult(label: String, confidence: Float, saveState: String, topMatches: String = "") {
        val variety = displayVariety(label.substringBefore("__"))
        val maturity = label.substringAfter("__").replace('_', ' ')
        result.text = "RESULT READY ON THIS DEVICE\n\nVariety: $variety\nMaturity: $maturity\nConfidence: ${"%.1f".format(confidence * 100)}%"
        result.visibility = android.view.View.VISIBLE
        status.text = saveState + if (topMatches.isBlank()) "" else "\n\nOther model matches:\n$topMatches"
    }

    private fun showSavedHistory() {
        val periods = arrayOf("All", "This week", "This month", "This year")
        AlertDialog.Builder(this).setTitle("Filter input logs").setItems(periods) { _, index ->
            worker.execute {
                val result = runCatching {
                    val scans = OfflineScanStore(this).summaries(farmerId)
                    val assessments = OfflineAssessmentStore(this).records(farmerId)
                    val cached = OfflineFarmerCache(this).snapshot(farmerId)?.optJSONArray("history")
                    val online = if (cached == null) emptyList() else (0 until cached.length()).map {
                        cached.getJSONObject(it)
                    }
                    val now = Calendar.getInstance()
                    fun inPeriod(createdAt: Long): Boolean {
                        return if (index == 0) true else {
                            val date = Calendar.getInstance().apply { timeInMillis = createdAt }
                            when (index) {
                                1 -> date.get(Calendar.YEAR) == now.get(Calendar.YEAR) && date.get(Calendar.WEEK_OF_YEAR) == now.get(Calendar.WEEK_OF_YEAR)
                                2 -> date.get(Calendar.YEAR) == now.get(Calendar.YEAR) && date.get(Calendar.MONTH) == now.get(Calendar.MONTH)
                                else -> date.get(Calendar.YEAR) == now.get(Calendar.YEAR)
                            }
                        }
                    }
                    Triple(scans.filter { inPeriod(it.createdAt) }, assessments.filter { inPeriod(it.getLong("created_at")) },
                        online.filter { inPeriod(it.getLong("created_at_ms")) })
                }
                runOnUiThread {
                    if (isDestroyed) return@runOnUiThread
                    result.onSuccess { (scans, assessments, online) ->
                        if (scans.isEmpty() && assessments.isEmpty() && online.isEmpty()) {
                            AlertDialog.Builder(this).setMessage("No saved offline results for this period.").setPositiveButton("OK", null).show()
                        } else {
                            val entries = (scans.map { it.createdAt to ("Scan · ${displayVariety(it.label.substringBefore("__"))} · ${it.label.substringAfter("__").replace('_', ' ')}" to it) } +
                                assessments.map { it.getLong("created_at") to ("Assessment · ${OfflineRules.VARIETIES[it.getInt("variety")]} · ${"%.2f".format(it.getDouble("total_lkg"))} LKG · ${if (it.getBoolean("synced")) "Server copy saved" else "Server copy waiting"}" to it) } +
                                online.map { it.getLong("created_at_ms") to ("Online history · ${it.optString("variety")} · ${it.optString("created_at").take(10)}" to it) })
                                .sortedByDescending { it.first }
                            val items = entries.map { it.second.first }.toTypedArray()
                            AlertDialog.Builder(this).setTitle("Input Logs · ${periods[index]}").setItems(items) { _, position ->
                                val selected = entries[position].second.second
                                if (selected is org.json.JSONObject) {
                                    if (selected.optBoolean("cached_online")) {
                                        val estimates = if (selected.isNull("lkg_per_ton")) "No agronomic estimate for this record."
                                            else formatAssessment(selected)
                                        val details = "${selected.optString("variety")} · ${selected.optString("created_at").take(10)}\n\n$estimates" +
                                            if ((selected.optJSONArray("recommendations")?.length() ?: 0) > 0)
                                                "\n\nRecommendations\n${formatRecommendations(selected)}" else ""
                                        AlertDialog.Builder(this).setTitle("Saved online history")
                                            .setMessage(details).setPositiveButton("OK", null).show()
                                        return@setItems
                                    }
                                    latestScanId = null
                                    latestScanLabel = null
                                    variety.setSelection(selected.getInt("variety"))
                                    area.setText(selected.getDouble("hectares").toString())
                                    plowing.setSelection(selected.getInt("plowing") - 1)
                                    weeding.setSelection(selected.getInt("weeding") - 1)
                                    fertilizer.setSelection(selected.getInt("fertilizer") - 1)
                                    stage.setSelection(selected.getInt("stage") - 1)
                                    infection.setSelection(if (selected.getBoolean("infected")) 1 else 0)
                                    maturity.setSelection(selected.getInt("maturity"))
                                    assessment.text = "${formatAssessment(selected)}\nSaved on this phone · ${if (selected.getBoolean("synced")) "Server copy saved" else "Server copy waiting"}"
                                    recommendationsView.text = "Recommendations\n\n${formatRecommendations(selected)}"
                                    return@setItems
                                }
                                val scan = selected as PendingScanSummary
                                worker.execute {
                                    val photo = runCatching { OfflineScanStore(this).read(farmerId, scan.id).jpeg }
                                    runOnUiThread {
                                        photo.onSuccess {
                                            preview.setImageBitmap(BitmapFactory.decodeByteArray(it, 0, it.size))
                                            latestScanId = scan.id
                                            latestScanLabel = scan.label
                                            applyScanLabel(scan.label)
                                            showResult(scan.label, scan.confidence,
                                                if (scan.synced) "Saved on this phone · Also synchronized to the server."
                                                else "Saved on this phone · Server copy waiting for connection.")
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

    private fun applyScanLabel(label: String) {
        variety.setSelection(when (label.substringBefore("__")) { "524" -> 0; "847" -> 1; else -> 2 })
        maturity.setSelection(when (label.substringAfter("__")) {
            "Not_Mature" -> 1; "Mature" -> 2; "Over_Mature" -> 3; else -> 0
        })
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
        result.visibility = android.view.View.GONE
        latestScanId = null
        latestScanLabel = null
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
                    latestScanId = saved.getOrNull()?.id
                    latestScanLabel = top.label
                    applyScanLabel(top.label)
                    showResult(top.label, top.confidence,
                        if (saved.isSuccess) "Saved on this phone. You can use this result now. A server copy will sync when connected."
                        else "Result ready, but it could not be saved on this phone: ${saved.exceptionOrNull()?.localizedMessage}",
                        predictions.drop(1).take(2).joinToString("\n") {
                            "${displayVariety(it.variety)} · ${it.maturity}: ${"%.1f".format(it.confidence * 100)}%"
                        })
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

    override fun onResume() {
        super.onResume()
        if (farmerId > 0 && getSharedPreferences("farmer_offline_access", MODE_PRIVATE)
                .getLong("farmer_id", 0) != farmerId) { finish(); return }
        if (::history.isInitialized && farmerId > 0) refreshHistory()
    }

    override fun onDestroy() {
        worker.execute { classifier?.close(); classifier = null }
        worker.shutdown()
        super.onDestroy()
    }
}
