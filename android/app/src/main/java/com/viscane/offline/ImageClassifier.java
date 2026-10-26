package com.viscane.offline;

import android.graphics.Bitmap;
import org.json.JSONObject;

/** Optional on-device recognition interface; manual offline use needs no model runtime. */
interface ImageClassifier extends AutoCloseable {
    JSONObject classify(Bitmap bitmap) throws Exception;

    @Override
    void close() throws Exception;
}
