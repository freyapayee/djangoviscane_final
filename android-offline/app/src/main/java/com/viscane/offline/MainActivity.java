package com.viscane.offline;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.text.InputType;
import android.widget.*;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.OutputStream;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.text.DateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Standalone offline farmer assessment screen; no WebView or server session. */
public final class MainActivity extends Activity {
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private AssessmentStore store;
    private LinearLayout form;
    private TextView result, history;
    private EditText area;
    private Spinner variety, plowing, weeding, fertilizer, stage, infection, maturity;
    private Button calculate, scan;
    private TextView recognitionStatus;
    private OfflineImageClassifier classifier;
    private JSONObject recognition;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        store = new AssessmentStore(this);
        ScrollView scroll = new ScrollView(this);
        form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (20 * getResources().getDisplayMetrics().density);
        form.setPadding(padding, padding, padding, padding);
        scroll.addView(form);
        scroll.setOnApplyWindowInsetsListener((view, insets) -> {
            form.setPadding(padding + insets.getSystemWindowInsetLeft(),
                    padding + insets.getSystemWindowInsetTop(),
                    padding + insets.getSystemWindowInsetRight(),
                    padding + insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(scroll);
        text("VISCANE Offline", 26);
        text("Photo or manual assessment · stored on this device", 16);
        text("Choose a saved photo for on-device recognition, or enter variety and maturity manually. "
                + "Review the predicted labels before calculating. Results are estimates.", 14);
        scan = button("Recognize a photo offline", () -> {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("image/*");
            startActivityForResult(intent, 11);
        });
        scan.setEnabled(OfflineRules.IMAGE_RECOGNITION_AVAILABLE);
        recognitionStatus = text(OfflineRules.IMAGE_RECOGNITION_AVAILABLE
                ? "Model bundled. Select a photo saved on this device; no connection is required. "
                  + "This model has no Mauritio NOT_MATURE class."
                : "No recognition model bundled. Manual calculations are available.", 14);
        variety = choices("Sugarcane variety", OfflineRules.VARIETIES);
        text("Area in hectares", 16);
        area = new EditText(this);
        area.setSingleLine(true);
        area.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        area.setHint("e.g. 1.5");
        area.setId(100);
        form.addView(area);
        String[] counts = {"1 time", "2 times", "3 times"};
        plowing = choices("Plowing", counts);
        weeding = choices("Weeding", counts);
        fertilizer = choices("Fertilizer applications", counts);
        stage = choices("Crop stage", new String[] {"New plant", "1st ratoon", "2nd ratoon"});
        infection = choices("RSSI infection observed", new String[] {"No", "Yes"});
        maturity = choices("Manually observed maturity", new String[] {
                "Unknown / not assessed", "Not mature", "Mature", "Over mature"});
        AdapterView.OnItemSelectedListener labelChanges = new AdapterView.OnItemSelectedListener() {
            @Override public void onNothingSelected(AdapterView<?> parent) {}
            @Override public void onItemSelected(AdapterView<?> parent, android.view.View view, int position, long id) {
                if (recognition != null && (variety.getSelectedItemPosition() != recognition.optInt("variety_index")
                        || maturity.getSelectedItemPosition() != recognition.optInt("maturity_index"))) {
                    recognition = null;
                    recognitionStatus.setText("Labels changed manually. This assessment will be saved as manual.");
                }
            }
        };
        variety.setOnItemSelectedListener(labelChanges);
        maturity.setOnItemSelectedListener(labelChanges);
        calculate = button("Calculate and save", this::assess);
        result = text("", 16);
        button("Export saved assessments (JSON)", () -> {
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
            intent.setType("application/json");
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.putExtra(Intent.EXTRA_TITLE, "viscane-assessments.json");
            startActivityForResult(intent, 10);
        });
        text("Recent assessments", 20);
        history = text("Loading…", 14);
        refreshHistory();
    }

    private TextView text(String value, int size) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setPadding(0, 12, 0, 8);
        form.addView(view);
        return view;
    }

    private Spinner choices(String label, String[] options) {
        TextView caption = text(label, 16);
        Spinner spinner = new Spinner(this);
        spinner.setId(101 + form.getChildCount());
        caption.setLabelFor(spinner.getId());
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, options);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        form.addView(spinner);
        return spinner;
    }

    private Button button(String label, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setOnClickListener(view -> action.run());
        form.addView(button);
        return button;
    }

    private void assess() {
        try {
            double hectares = Double.parseDouble(area.getText().toString().trim().replace(',', '.'));
            int v = variety.getSelectedItemPosition();
            int p = plowing.getSelectedItemPosition() + 1;
            int w = weeding.getSelectedItemPosition() + 1;
            int f = fertilizer.getSelectedItemPosition() + 1;
            int s = stage.getSelectedItemPosition() + 1;
            int m = maturity.getSelectedItemPosition();
            boolean infected = infection.getSelectedItemPosition() == 1;
            OfflineCalculator.Result estimate = OfflineCalculator.calculate(v, hectares, p, w, f, s, infected, m);
            JSONObject input = new JSONObject().put("variety", OfflineRules.VARIETIES[v])
                    .put("hectares", hectares).put("plowing", p).put("weeding", w)
                    .put("fertilizer", f).put("ratoon", s).put("rssi", infected ? 1 : 0)
                    .put("maturity", new String[] {"UNKNOWN", "NOT_MATURE", "MATURE", "OVER_MATURE"}[m]);
            JSONObject output = new JSONObject().put("lkg_per_ton", estimate.lkgPerTon)
                    .put("total_tons", estimate.totalTons).put("total_lkg", estimate.totalLkg)
                    .put("multiplier", estimate.multiplier);
            JSONObject record = new JSONObject().put("id", UUID.randomUUID().toString())
                    .put("created_at", System.currentTimeMillis()).put("schema_version", 1)
                    .put("rules_version", OfflineRules.VERSION)
                    .put("assessment_source", recognition == null ? "manual" : "on_device_image")
                    .put("input", input).put("output", output);
            if (recognition != null) record.put("recognition", new JSONObject(recognition.toString()));
            String guide = "\n\nFertilizer: " + OfflineRules.FERTILIZER[v][f - 1]
                    + "\n\nWeeding: " + OfflineRules.WEEDING[v][w - 1]
                    + "\n\nPlowing: " + (v == 1 && s > 1
                    ? "For VMC 84-947 ratoon, avoid plowing. Use stubble shaving and inter-row cultivation (off-barring) to protect ratoon shoots."
                    : OfflineRules.PLOWING[v][p - 1]);
            String display = String.format(Locale.getDefault(),
                    "Estimated LKG/TC: %.2f\nEstimated total cane (tons): %.2f\nEstimated total LKG: %.2f",
                    estimate.lkgPerTon, estimate.totalTons, estimate.totalLkg) + guide;
            calculate.setEnabled(false);
            worker.execute(() -> {
                try {
                    store.save(record);
                    runOnUiThread(() -> {
                        result.setText(display + "\n\nSaved on this device.");
                        calculate.setEnabled(true);
                    });
                    refreshHistoryOnWorker();
                } catch (Exception error) {
                    runOnUiThread(() -> {
                        result.setText(display + "\n\nCould not save: " + error.getMessage());
                        calculate.setEnabled(true);
                    });
                }
            });
        } catch (Exception error) {
            result.setText("Check your inputs: " + error.getMessage());
        }
    }

    private void refreshHistory() { worker.execute(this::refreshHistoryOnWorker); }

    private void refreshHistoryOnWorker() {
        try {
            JSONArray records = store.records(20);
            StringBuilder lines = new StringBuilder();
            for (int i = 0; i < records.length(); i++) {
                JSONObject record = records.getJSONObject(i);
                lines.append(DateFormat.getDateTimeInstance().format(new Date(record.getLong("created_at"))))
                        .append(" · ").append(record.getJSONObject("input").getString("variety"))
                        .append(String.format(Locale.getDefault(), " · %.2f LKG\n\n",
                                record.getJSONObject("output").getDouble("total_lkg")));
            }
            runOnUiThread(() -> history.setText(lines.length() == 0 ? "No saved assessments yet." : lines.toString()));
        } catch (Exception error) {
            runOnUiThread(() -> history.setText("Could not load history: " + error.getMessage()));
        }
    }

    @Override protected void onActivityResult(int request, int status, Intent data) {
        super.onActivityResult(request, status, data);
        if (request == 11 && status == RESULT_OK && data != null && data.getData() != null) {
            recognize(data.getData());
            return;
        }
        if (request != 10 || status != RESULT_OK || data == null || data.getData() == null) return;
        android.net.Uri uri = data.getData();
        worker.execute(() -> {
            try {
                JSONObject document = new JSONObject().put("schema_version", 1)
                        .put("created_at_unit", "unix_milliseconds").put("assessments", store.records(0));
                try (OutputStream stream = getContentResolver().openOutputStream(uri, "wt")) {
                    if (stream == null) throw new java.io.IOException("Cannot open export destination.");
                    stream.write(document.toString(2).getBytes(StandardCharsets.UTF_8));
                }
                runOnUiThread(() -> Toast.makeText(this, "Assessments exported", Toast.LENGTH_LONG).show());
            } catch (Exception error) {
                runOnUiThread(() -> Toast.makeText(this, "Export failed: " + error.getMessage(), Toast.LENGTH_LONG).show());
            }
        });
    }

    private void recognize(android.net.Uri uri) {
        recognition = null;
        recognitionStatus.setText("Recognizing on this device…");
        scan.setEnabled(false);
        calculate.setEnabled(false);
        variety.setEnabled(false);
        maturity.setEnabled(false);
        worker.execute(() -> {
            Bitmap bitmap = null;
            try {
                byte[] contents;
                try (InputStream stream = getContentResolver().openInputStream(uri);
                     ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
                    if (stream == null) throw new java.io.IOException("Cannot open photo.");
                    byte[] buffer = new byte[16384];
                    int count;
                    while ((count = stream.read(buffer)) != -1) {
                        if (bytes.size() + count > 20 * 1024 * 1024)
                            throw new IllegalArgumentException("Photo exceeds 20 MB. Choose a smaller image.");
                        bytes.write(buffer, 0, count);
                    }
                    contents = bytes.toByteArray();
                }
                BitmapFactory.Options bounds = new BitmapFactory.Options();
                bounds.inJustDecodeBounds = true;
                BitmapFactory.decodeByteArray(contents, 0, contents.length, bounds);
                if (bounds.outWidth <= 0 || bounds.outHeight <= 0
                        || (long) bounds.outWidth * bounds.outHeight > 16000000)
                    throw new IllegalArgumentException("Choose a valid photo up to 16 megapixels.");
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inPreferredConfig = Bitmap.Config.ARGB_8888;
                bitmap = BitmapFactory.decodeByteArray(contents, 0, contents.length, options);
                if (bitmap == null) throw new IllegalArgumentException("Cannot decode this photo.");
                if (classifier == null) classifier = new OfflineImageClassifier(this);
                JSONObject prediction = classifier.classify(bitmap);
                runOnUiThread(() -> {
                    if (isDestroyed()) return;
                    int v = prediction.optInt("variety_index"), m = prediction.optInt("maturity_index");
                    variety.setSelection(v);
                    maturity.setSelection(m);
                    recognition = prediction;
                    recognitionStatus.setText(String.format(Locale.getDefault(),
                            "%s · %s\nModel confidence: %.1f%%. Review labels before saving. "
                            + "Confidence does not verify that a photo contains sugarcane.",
                            OfflineRules.VARIETIES[v], prediction.optString("class_name").trim(),
                            prediction.optDouble("confidence") * 100));
                    scan.setEnabled(true);
                    calculate.setEnabled(true);
                    variety.setEnabled(true);
                    maturity.setEnabled(true);
                });
            } catch (Exception | OutOfMemoryError error) {
                runOnUiThread(() -> {
                    if (isDestroyed()) return;
                    recognitionStatus.setText("Recognition failed: " + error.getMessage()
                            + ". You can enter variety and maturity manually.");
                    scan.setEnabled(true);
                    calculate.setEnabled(true);
                    variety.setEnabled(true);
                    maturity.setEnabled(true);
                });
            } finally {
                if (bitmap != null) bitmap.recycle();
            }
        });
    }

    @Override protected void onDestroy() {
        worker.execute(() -> {
            if (classifier != null) {
                try { classifier.close(); } catch (Exception ignored) {}
            }
            store.close();
        });
        worker.shutdown();
        super.onDestroy();
    }
}
