package com.viscane.offline;

import android.content.Context;
import java.lang.reflect.Constructor;

/** Loads the ONNX implementation only in builds that include a validated model. */
final class ImageClassifierFactory {
    private ImageClassifierFactory() {}

    static ImageClassifier create(Context context) throws Exception {
        Class<?> implementation = Class.forName("com.viscane.offline.OfflineImageClassifier");
        Constructor<?> constructor = implementation.getDeclaredConstructor(Context.class);
        constructor.setAccessible(true);
        return (ImageClassifier) constructor.newInstance(context);
    }
}
