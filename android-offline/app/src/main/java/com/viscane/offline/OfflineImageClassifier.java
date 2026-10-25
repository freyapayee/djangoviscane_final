package com.viscane.offline;

import android.content.Context;
import android.graphics.Bitmap;
import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.FloatBuffer;
import java.util.Collections;
import java.security.MessageDigest;
import java.util.Locale;

/** CPU inference with bundled weights; no requests or runtime model downloads. */
final class OfflineImageClassifier implements AutoCloseable {
    private final OrtEnvironment environment = OrtEnvironment.getEnvironment();
    private final OrtSession session;
    private final JSONObject metadata;
    private final int size;

    OfflineImageClassifier(Context context) throws Exception {
        metadata = new JSONObject(new String(read(context, "recognition-model.json"), java.nio.charset.StandardCharsets.UTF_8));
        size = metadata.getInt("image_size");
        if (!"logits".equals(metadata.getString("output_type"))
                || !"bilinear_align_corners_false_no_antialias".equals(metadata.getString("resize")))
            throw new IllegalArgumentException("Unsupported model preprocessing or output.");
        byte[] model = read(context, metadata.getString("model_file"));
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(model);
        StringBuilder hash = new StringBuilder();
        for (byte value : digest) hash.append(String.format(Locale.ROOT, "%02x", value & 255));
        if (!hash.toString().equals(metadata.getString("model_sha256")))
            throw new IllegalArgumentException("Model checksum mismatch.");
        try (OrtSession.SessionOptions options = new OrtSession.SessionOptions()) {
            options.setIntraOpNumThreads(2);
            session = environment.createSession(model, options);
        }
    }

    private static byte[] read(Context context, String name) throws Exception {
        try (InputStream stream = context.getAssets().open(name);
             ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16384];
            int count;
            while ((count = stream.read(buffer)) != -1) bytes.write(buffer, 0, count);
            return bytes.toByteArray();
        }
    }

    JSONObject classify(Bitmap bitmap) throws Exception {
        int[] pixels = new int[bitmap.getWidth() * bitmap.getHeight()];
        bitmap.getPixels(pixels, 0, bitmap.getWidth(), 0, 0, bitmap.getWidth(), bitmap.getHeight());
        float[] prepared = ImagePreprocessor.prepare(pixels, bitmap.getWidth(), bitmap.getHeight(), size);
        try (OnnxTensor tensor = OnnxTensor.createTensor(environment, FloatBuffer.wrap(prepared), new long[] {1, 3, size, size});
             OrtSession.Result result = session.run(Collections.singletonMap(metadata.getString("input_name"), tensor))) {
            float[] logits = ((float[][]) result.get(metadata.getString("output_name")).get().getValue())[0];
            JSONArray mapping = metadata.getJSONArray("class_mapping");
            if (logits.length != mapping.length()) throw new IllegalArgumentException("Model labels do not match output.");
            int best = 0;
            for (int i = 0; i < logits.length; i++) {
                if (Float.isNaN(logits[i]) || Float.isInfinite(logits[i]))
                    throw new IllegalArgumentException("Model produced invalid scores.");
                if (logits[i] > logits[best]) best = i;
            }
            double sum = 0;
            for (float logit : logits) sum += Math.exp(logit - logits[best]);
            JSONObject decoded = mapping.getJSONObject(best);
            return new JSONObject().put("class_index", best).put("class_name", decoded.getString("label"))
                    .put("variety_index", decoded.getInt("variety_index"))
                    .put("maturity_index", decoded.getInt("maturity_index"))
                    .put("confidence", 1.0 / sum).put("model_sha256", metadata.getString("model_sha256"))
                    .put("model_type", "resnet18").put("inference", "on_device");
        }
    }

    @Override public void close() throws Exception { session.close(); }
}
