package com.viscane.offline

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.Color
import android.graphics.Typeface
import android.Manifest
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.text.InputType
import android.text.InputFilter
import android.util.Base64
import android.webkit.CookieManager
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.activity.ComponentActivity
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.core.content.ContextCompat
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
    private lateinit var homeCard: LinearLayout
    private lateinit var reviewActions: LinearLayout
    private lateinit var detailsPanel: LinearLayout
    private lateinit var agronomicInputs: LinearLayout
    private lateinit var plotName: EditText
    private lateinit var confidenceDetails: TextView
    private var latestScanId: String? = null
    private var latestScanLabel: String? = null
    private var farmerId: Long = 0
    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) launchCamera() else {
            status.text = "Camera permission is needed to take a photo. You can still upload a photo from your gallery."
            controls(true)
        }
    }
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
        val green = Color.rgb(62, 124, 74)
        val dark = Color.rgb(31, 41, 51)
        val sage = Color.rgb(232, 242, 232)
        val cream = Color.rgb(248, 244, 234)
        WindowInsetsControllerCompat(window, window.decorView).isAppearanceLightStatusBars = false
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(12), dp(16), dp(12))
            setBackgroundColor(cream)
        }
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(dp(16) + bars.left, dp(12) + bars.top, dp(16) + bars.right, dp(12) + bars.bottom)
            insets
        }
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = rounded(Color.WHITE, 20)
            elevation = dp(3).toFloat()
        }
        header.addView(ImageView(this).apply {
            setImageResource(R.drawable.app_logo)
            contentDescription = "VISCANE"
            scaleType = ImageView.ScaleType.CENTER_CROP
            background = rounded(sage, 12)
            clipToOutline = true
        }, LinearLayout.LayoutParams(dp(48), dp(48)).apply { rightMargin = dp(12) })
        val brand = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = android.view.Gravity.CENTER_VERTICAL }
        brand.addView(TextView(this).apply { text = "VISCANE"; textSize = 14f; setTextColor(green); setTypeface(null, Typeface.BOLD) })
        brand.addView(TextView(this).apply { text = "Scan Sugarcane"; textSize = 21f; setTextColor(dark); setTypeface(null, Typeface.BOLD) })
        brand.addView(TextView(this).apply {
            text = "Offline · ${java.text.SimpleDateFormat("EEE, MMM d", java.util.Locale.getDefault()).format(java.util.Date())} · Saved on this device"
            textSize = 12f
            setTextColor(Color.rgb(102, 112, 133))
        })
        header.addView(brand, LinearLayout.LayoutParams(0, -2, 1f))
        header.addView(Button(this).apply {
            text = "Menu"; textSize = 14f
            backgroundTintList = ColorStateList.valueOf(sage)
            setTextColor(green)
            setOnClickListener { showFarmerMenu() }
        }, LinearLayout.LayoutParams(-2, -2).apply { leftMargin = dp(8) })
        root.addView(header, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(14) })

        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(18), dp(18), dp(18))
            background = rounded(Color.WHITE, 20)
            elevation = dp(3).toFloat()
        }
        homeCard = card
        card.addView(TextView(this).apply { text = "Sugarcane assessment"; textSize = 22f; setTextColor(dark); setTypeface(null, Typeface.BOLD) })
        card.addView(TextView(this).apply { text = "Choose a clear photo. Variety and maturity are estimated on your phone."; textSize = 16f; setTextColor(dark) })
        val scanStepper = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(10), dp(10), dp(10), dp(10))
            background = rounded(sage, 12)
        }
        listOf("1  Photo", "2  Review", "3  Details").forEach { label ->
            scanStepper.addView(TextView(this).apply {
                text = label
                textSize = 13f
                gravity = android.view.Gravity.CENTER
                setTextColor(green)
                setTypeface(null, Typeface.BOLD)
            }, LinearLayout.LayoutParams(0, -2, 1f))
        }
        card.addView(scanStepper, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        preview = ImageView(this).apply {
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "Selected sugarcane photo"
            background = rounded(Color.rgb(237, 247, 240), 18)
        }
        card.addView(preview, LinearLayout.LayoutParams(-1, dp(230)).apply { topMargin = dp(14) })
        camera = Button(this).apply {
            text = "Use camera"; textSize = 16f; isEnabled = false
            backgroundTintList = ColorStateList.valueOf(green); setTextColor(Color.WHITE)
            setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_camera_white, 0, 0, 0)
            compoundDrawablePadding = dp(8)
        }
        gallery = Button(this).apply {
            text = "Choose photo"; textSize = 16f; isEnabled = false
            backgroundTintList = ColorStateList.valueOf(sage); setTextColor(green)
            setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_image, 0, 0, 0)
            compoundDrawablePadding = dp(8)
        }
        card.addView(camera, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        card.addView(gallery, LinearLayout.LayoutParams(-1, -2))
        result = TextView(this).apply {
            visibility = android.view.View.GONE
            textSize = 20f
            setTextColor(dark)
            setTypeface(null, Typeface.BOLD)
            setPadding(dp(16), dp(16), dp(16), dp(16))
            background = rounded(sage, 18)
            setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_sparkles, 0, 0, 0)
            compoundDrawablePadding = dp(10)
        }
        card.addView(result, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        reviewActions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            visibility = android.view.View.GONE
        }
        val changePhoto = Button(this).apply {
            text = "Change photo"; textSize = 13f
            backgroundTintList = ColorStateList.valueOf(sage); setTextColor(green)
            setOnClickListener { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }
        }
        val useResult = Button(this).apply {
            text = "Use this result"; textSize = 13f
            backgroundTintList = ColorStateList.valueOf(green); setTextColor(Color.WHITE)
            setOnClickListener { openAssessmentDetails() }
        }
        reviewActions.addView(changePhoto, LinearLayout.LayoutParams(0, -2, 1f).apply { rightMargin = dp(6) })
        reviewActions.addView(useResult, LinearLayout.LayoutParams(0, -2, 1f).apply { leftMargin = dp(6) })
        card.addView(reviewActions, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
        status = TextView(this).apply { text = "Loading offline models…"; textSize = 16f; setTextColor(dark); setPadding(0, dp(12), 0, dp(12)) }
        card.addView(status)
        card.addView(Button(this).apply {
            text = "Continue without a photo · enter manually"; textSize = 14f
            backgroundTintList = ColorStateList.valueOf(sage); setTextColor(green)
            setOnClickListener {
                latestScanId = null
                latestScanLabel = null
                reviewActions.visibility = android.view.View.GONE
                result.visibility = android.view.View.GONE
                openAssessmentDetails()
            }
        }, LinearLayout.LayoutParams(-1, -2))
        detailsPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = android.view.View.GONE
            setPadding(dp(16), dp(16), dp(16), dp(16))
            background = rounded(Color.WHITE, 16)
        }
        detailsPanel.addView(TextView(this).apply { text = "Assessment Details"; textSize = 21f; setTextColor(dark); setTypeface(null, Typeface.BOLD) })
        detailsPanel.addView(TextView(this).apply { text = "Add the plot name to continue to agronomic inputs."; textSize = 14f; setTextColor(Color.rgb(102, 112, 133)) })
        detailsPanel.addView(TextView(this).apply { text = "Plot name"; textSize = 16f; setTextColor(dark); setPadding(0, dp(12), 0, 0) })
        plotName = EditText(this).apply {
            hint = "e.g., North Field 3"; textSize = 16f; isSingleLine = true
            contentDescription = "Plot name"
            filters = arrayOf(InputFilter.LengthFilter(80))
        }
        detailsPanel.addView(plotName)
        confidenceDetails = TextView(this).apply { text = "Confidence: Manual assessment"; textSize = 15f; setTextColor(dark); setPadding(0, dp(8), 0, dp(8)) }
        detailsPanel.addView(confidenceDetails)
        detailsPanel.addView(Button(this).apply {
            text = "Proceed to Agronomic Input"; textSize = 15f
            backgroundTintList = ColorStateList.valueOf(green); setTextColor(Color.WHITE)
            setOnClickListener {
                if (plotName.text.toString().trim().isEmpty()) {
                    plotName.error = "Enter a plot name to continue"
                    return@setOnClickListener
                }
                agronomicInputs.visibility = android.view.View.VISIBLE
                contentScroll.post { contentScroll.smoothScrollTo(0, agronomicInputs.top) }
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        card.addView(detailsPanel, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        agronomicInputs = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = android.view.View.GONE
        }
        agronomicInputs.addView(TextView(this).apply {
            text = "Assessment parameters"; textSize = 22f; setTextColor(dark); setTypeface(null, Typeface.BOLD)
            setPadding(0, dp(16), 0, dp(4))
        })
        agronomicInputs.addView(TextView(this).apply {
            text = "Use a scan result or enter the variety and maturity yourself. Calculations and guidance run on this phone."
            textSize = 16f; setTextColor(dark)
        })
        variety = choice(agronomicInputs, "Sugarcane variety", OfflineRules.VARIETIES)
        agronomicInputs.addView(TextView(this).apply { text = "Area in hectares"; textSize = 17f; setTextColor(dark) })
        area = EditText(this).apply {
            hint = "e.g. 1.5"
            textSize = 18f
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL
            contentDescription = "Area in hectares"
        }
        agronomicInputs.addView(area)
        val counts = arrayOf("1 time", "2 times", "3 times")
        plowing = choice(agronomicInputs, "Plowing", counts)
        weeding = choice(agronomicInputs, "Weeding", counts)
        fertilizer = choice(agronomicInputs, "Fertilizer applications", counts)
        stage = choice(agronomicInputs, "Crop stage", arrayOf("New plant", "1st ratoon", "2nd ratoon"))
        infection = choice(agronomicInputs, "RSSI infection observed", arrayOf("No", "Yes"))
        maturity = choice(agronomicInputs, "Maturity", arrayOf("Unknown / manual", "Not mature", "Mature", "Over mature"))
        agronomicInputs.addView(Button(this).apply {
            text = "Calculate and save on this phone"; textSize = 16f
            backgroundTintList = ColorStateList.valueOf(green); setTextColor(Color.WHITE)
            setOnClickListener { calculateAssessment() }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
        assessment = TextView(this).apply { textSize = 18f; setTextColor(dark); setPadding(0, dp(10), 0, dp(8)) }
        agronomicInputs.addView(assessment)
        recommendationsView = TextView(this).apply { textSize = 17f; setTextColor(dark) }
        agronomicInputs.addView(recommendationsView)
        card.addView(agronomicInputs, LinearLayout.LayoutParams(-1, -2))
        history = TextView(this).apply { text = "Loading saved results…"; textSize = 16f; setTextColor(dark) }
        card.addView(history)
        }
        contentScroll = ScrollView(this).apply {
            setFillViewport(false)
            isSmoothScrollingEnabled = true
            isNestedScrollingEnabled = false
            isVerticalScrollBarEnabled = true
            overScrollMode = android.view.View.OVER_SCROLL_IF_CONTENT_SCROLLS
            descendantFocusability = android.view.ViewGroup.FOCUS_AFTER_DESCENDANTS
            addView(card, ScrollView.LayoutParams(-1, -2))
        }
        root.addView(contentScroll, LinearLayout.LayoutParams(-1, 0, 1f))
        val navigation = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(6), dp(4), dp(6), dp(4))
        }
        fun nav(label: String, icon: Int, action: () -> Unit) {
            val item = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = android.view.Gravity.CENTER
                isClickable = true
                isFocusable = true
                setPadding(dp(3), dp(8), dp(3), dp(8))
                setOnClickListener { action() }
            }
            item.addView(ImageView(this).apply {
                setImageResource(icon)
                imageTintList = ColorStateList.valueOf(green)
                contentDescription = label
            }, LinearLayout.LayoutParams(dp(22), dp(22)))
            item.addView(TextView(this).apply {
                text = label
                textSize = 11f
                gravity = android.view.Gravity.CENTER
                setTextColor(green)
                setTypeface(null, Typeface.BOLD)
                setPadding(0, dp(3), 0, 0)
            })
            navigation.addView(item, LinearLayout.LayoutParams(0, -2, 1f))
        }
        nav("Home", R.drawable.ic_home) { showHomePage() }
        nav("Recommendations", R.drawable.ic_sparkles) { showRecommendations() }
        nav("Input Logs", R.drawable.ic_document) { showSavedHistory() }
        nav("Profile", R.drawable.ic_person) { showProfile() }
        navigation.background = rounded(Color.WHITE, 20)
        navigation.elevation = dp(3).toFloat()
        root.addView(navigation, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        setContentView(root)
        refreshHistory()
        gallery.setOnClickListener { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }
        camera.setOnClickListener {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                launchCamera()
            } else cameraPermission.launch(Manifest.permission.CAMERA)
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

    private fun launchCamera() {
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

    private fun rounded(color: Int, radiusDp: Int) = GradientDrawable().apply {
        // Keep the deep green header, while tinting card surfaces slightly gray for contrast.
        val greenSurface = Color.green(color) > Color.red(color) * 1.5 &&
            Color.green(color) > Color.blue(color) * 1.25
        val neutral = Color.rgb(235, 238, 235)
        val surfaceColor = if (greenSurface) color else Color.rgb(
            (Color.red(color) * 0.92 + Color.red(neutral) * 0.08).toInt(),
            (Color.green(color) * 0.92 + Color.green(neutral) * 0.08).toInt(),
            (Color.blue(color) * 0.92 + Color.blue(neutral) * 0.08).toInt()
        )
        setColor(surfaceColor)
        cornerRadius = dp(radiusDp).toFloat()
        val border = if (greenSurface) Color.rgb(111, 184, 134) else Color.rgb(164, 174, 167)
        setStroke(dp(2), border)
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
            val plot = plotName.text.toString().trim()
            require(plot.isNotEmpty()) { "Enter a plot name before calculating." }
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
                infected, m, estimate, guides, matchedScan, plot) }
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

    private fun openAssessmentDetails() {
        detailsPanel.visibility = android.view.View.VISIBLE
        if (latestScanLabel != null) {
            val confidenceText = result.text.toString().lineSequence()
                .firstOrNull { it.startsWith("Confidence:") }?.removePrefix("Confidence:")?.trim()
            confidenceDetails.text = "AI result: ${displayVariety(latestScanLabel!!.substringBefore("__"))} · ${latestScanLabel!!.substringAfter("__").replace('_', ' ')}" +
                (confidenceText?.let { " · Confidence: $it" } ?: "")
        } else confidenceDetails.text = "Confidence: Manual assessment"
        contentScroll.post { contentScroll.smoothScrollTo(0, detailsPanel.top) }
    }

    private fun showFarmerMenu() {
        val items = arrayOf("Home", "Scan and assessment", "See Notifications",
            "Profile", "News and announcements", "Feedback", "About VISCANE", "Tutorial",
            "Sign out on this phone")
        AlertDialog.Builder(this).setTitle("Offline farmer menu").setItems(items) { _, selected ->
            when (selected) {
                0, 1 -> showHomePage()
                2 -> showNotificationsPage()
                3 -> showProfile()
                4 -> showAnnouncements("News and announcements")
                5 -> showFeedback()
                6 -> AlertDialog.Builder(this).setTitle("About VISCANE")
                    .setMessage("VISCANE supports sugarcane farmers with on-device variety and maturity recognition, agronomic estimates, and guidance. Saved scans and assessments synchronize with the farmer portal when connected.")
                    .setPositiveButton("OK", null).show()
                7 -> AlertDialog.Builder(this).setTitle("Offline tutorial")
                    .setMessage("1. Sign in online once.\n2. Open Offline Farmer Workspace.\n3. Capture or choose a sugarcane photo.\n4. Check the variety and maturity.\n5. Enter area and agronomic inputs, then calculate.\n6. Read recommendations and Input Logs.\n7. Reconnect using the same account to sync server copies.")
                    .setPositiveButton("OK", null).show()
                8 -> AlertDialog.Builder(this).setTitle("Sign out on this phone")
                    .setMessage("Offline work stays encrypted and linked to your online farmer account. Signing in online again with the same account will unlock it. Continue?")
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

    private fun showHomePage() {
        contentScroll.removeAllViews()
        contentScroll.addView(homeCard, ScrollView.LayoutParams(-1, -2))
        contentScroll.post { contentScroll.scrollTo(0, 0) }
    }

    private fun showNotificationsPage() {
        val green = Color.rgb(36, 112, 61)
        val dark = Color.rgb(31, 41, 51)
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(18), dp(18), dp(22))
            background = rounded(Color.WHITE, 20)
            elevation = dp(3).toFloat()
        }
        page.addView(TextView(this).apply {
            text = "See Notifications"
            textSize = 23f
            setTextColor(dark)
            setTypeface(null, Typeface.BOLD)
        })
        page.addView(TextView(this).apply {
            text = "View announcements saved on this phone."
            textSize = 15f
            setTextColor(Color.rgb(90, 104, 96))
            setPadding(0, dp(5), 0, dp(12))
        })
        page.addView(Button(this).apply {
            text = "Back to Home"
            backgroundTintList = ColorStateList.valueOf(Color.rgb(232, 242, 232))
            setTextColor(green)
            setOnClickListener { showHomePage() }
        }, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(12) })
        val loading = TextView(this).apply {
            text = "Loading saved notifications…"
            textSize = 16f
            setTextColor(dark)
            setPadding(0, dp(8), 0, dp(8))
        }
        page.addView(loading)
        contentScroll.removeAllViews()
        contentScroll.addView(page, ScrollView.LayoutParams(-1, -2))
        contentScroll.post { contentScroll.scrollTo(0, 0) }

        worker.execute {
            val saved = runCatching {
                val cache = OfflineFarmerCache(this)
                Triple(cache.snapshot(farmerId), cache.clearedAnnouncementId(farmerId), cache)
            }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                saved.onSuccess { (snapshot, clearedAnnouncementId, cache) ->
                    page.removeView(loading)
                    val announcements = snapshot?.optJSONArray("announcements")
                    page.addView(TextView(this).apply {
                        text = "Announcements"
                        textSize = 18f
                        setTextColor(green)
                        setTypeface(null, Typeface.BOLD)
                        setPadding(0, dp(8), 0, dp(8))
                    })
                    if (announcements == null) {
                        page.addView(notificationMessage("Connect once while signed in to save announcements for offline viewing."))
                    } else {
                        val visibleAnnouncements = (0 until announcements.length()).mapNotNull { index ->
                            announcements.optJSONObject(index)?.takeIf { it.optInt("id") > clearedAnnouncementId }
                        }
                        if (visibleAnnouncements.isEmpty()) {
                            page.addView(notificationMessage(if (announcements.length() == 0) "No saved announcements yet."
                                else "No new announcements. Previously cleared announcements remain available in News and announcements."))
                        } else {
                            visibleAnnouncements.forEach { item ->
                                page.addView(notificationCard(item.optString("title", "Announcement"),
                                    item.optString("message"), item.optString("created_at")))
                            }
                            page.addView(Button(this).apply {
                                text = "Clear announcements"
                                backgroundTintList = ColorStateList.valueOf(Color.rgb(232, 242, 232))
                                setTextColor(green)
                                setOnClickListener {
                                    val latestId = visibleAnnouncements.maxOfOrNull { it.optInt("id") } ?: 0
                                    isEnabled = false
                                    worker.execute {
                                        val cleared = runCatching { cache.clearAnnouncements(farmerId, latestId) }
                                        runOnUiThread {
                                            if (!isDestroyed) {
                                                if (cleared.isSuccess) showNotificationsPage()
                                                Toast.makeText(this,
                                                    if (cleared.isSuccess) "Announcements cleared on this phone; read status will sync when you reconnect."
                                                    else "Could not clear announcements.", Toast.LENGTH_LONG).show()
                                            }
                                        }
                                    }
                                }
                            }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
                        }
                    }
                }.onFailure { error ->
                    loading.text = "Could not load saved notifications: ${error.localizedMessage}"
                }
            }
        }
    }

    private fun notificationMessage(message: String) = TextView(this).apply {
        text = message
        textSize = 15f
        setTextColor(Color.rgb(82, 98, 87))
        setPadding(dp(4), dp(8), dp(4), dp(12))
    }

    private fun notificationCard(title: String, message: String, date: String) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(14), dp(12), dp(14), dp(12))
        background = rounded(Color.rgb(243, 247, 243), 14)
        addView(TextView(this@OfflineScanActivity).apply {
            text = title
            textSize = 16f
            setTextColor(Color.rgb(31, 41, 51))
            setTypeface(null, Typeface.BOLD)
        })
        addView(TextView(this@OfflineScanActivity).apply {
            text = message
            textSize = 14f
            setTextColor(Color.rgb(49, 65, 55))
            setPadding(0, dp(5), 0, 0)
        })
        if (date.isNotBlank()) addView(TextView(this@OfflineScanActivity).apply {
            text = date
            textSize = 12f
            setTextColor(Color.rgb(105, 119, 108))
            setPadding(0, dp(6), 0, 0)
        })
    }.also { it.layoutParams = LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(9) } }

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
                "\nAssessment · ${it.optString("plot_name", "Plot")} · ${OfflineRules.VARIETIES[it.getInt("variety")]} · ${"%.2f".format(it.getDouble("total_lkg"))} LKG"
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
        result.text = "ANALYSIS COMPLETE\n\nClassification: $variety\nMaturity: $maturity\nConfidence: ${"%.1f".format(confidence * 100)}%"
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
                                assessments.map { it.getLong("created_at") to ("Assessment · ${it.optString("plot_name", "Plot")} · ${OfflineRules.VARIETIES[it.getInt("variety")]} · ${"%.2f".format(it.getDouble("total_lkg"))} LKG · ${if (it.getBoolean("synced")) "Server copy saved" else "Server copy waiting"}" to it) } +
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
                                    plotName.setText(selected.optString("plot_name"))
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
                                    detailsPanel.visibility = android.view.View.VISIBLE
                                    agronomicInputs.visibility = android.view.View.VISIBLE
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
                                            reviewActions.visibility = android.view.View.VISIBLE
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
        reviewActions.visibility = android.view.View.GONE
        detailsPanel.visibility = android.view.View.GONE
        agronomicInputs.visibility = android.view.View.GONE
        latestScanId = null
        latestScanLabel = null
        status.text = "Analyzing photo on this device…"
        worker.execute {
            try {
                val bitmap = decode(uri)
                val predictions = try { classifier!!.classify(bitmap) } catch (error: Throwable) { bitmap.recycle(); throw error }
                val top = predictions.first()
                val accepted = top.confidence >= MIN_ACCEPTED_CONFIDENCE
                val saved = if (accepted) runCatching { OfflineScanStore(this).save(farmerId, top, bitmap) }
                    else Result.failure(IllegalArgumentException("Prediction confidence below threshold"))
                runOnUiThread {
                    if (isDestroyed) { bitmap.recycle(); return@runOnUiThread }
                    preview.setImageBitmap(bitmap)
                    if (!accepted) {
                        latestScanId = null
                        latestScanLabel = null
                        result.text = "Invalid Image or the image can't be read. Please choose a clear sugarcane photo and try again."
                        result.visibility = android.view.View.VISIBLE
                        status.text = "Prediction confidence ${"%.1f".format(top.confidence * 100)}% is below the 50% minimum. No result was saved."
                    } else {
                        latestScanId = saved.getOrNull()?.id
                        latestScanLabel = top.label
                        applyScanLabel(top.label)
                        showResult(top.label, top.confidence,
                            if (saved.isSuccess) "Saved on this phone. You can use this result now. A server copy will sync when connected."
                            else "Result ready, but it could not be saved on this phone: ${saved.exceptionOrNull()?.localizedMessage}",
                            predictions.drop(1).take(2).joinToString("\n") {
                                "${displayVariety(it.variety)} · ${it.maturity}: ${"%.1f".format(it.confidence * 100)}%"
                            })
                    }
                    controls(true)
                    if (accepted) reviewActions.visibility = android.view.View.VISIBLE
                    if (accepted && saved.isSuccess) refreshHistory()
                }
            } catch (error: Exception) {
                runOnUiThread { if (!isDestroyed) { status.text = "Could not analyze photo: ${error.localizedMessage}"; controls(true) } }
            }
        }
    }

    companion object {
        private const val MIN_ACCEPTED_CONFIDENCE = 0.50f
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
