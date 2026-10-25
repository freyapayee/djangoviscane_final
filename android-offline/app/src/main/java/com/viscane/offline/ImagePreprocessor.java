package com.viscane.offline;

/** Match train.py's RGB float, bilinear resize, align_corners=false, no antialias.
 * Plain Java so numeric preprocessing can be tested independently of Android.
 */
public final class ImagePreprocessor {
    private static final float[] MEAN = {0.485f, 0.456f, 0.406f};
    private static final float[] STD = {0.229f, 0.224f, 0.225f};
    private ImagePreprocessor() {}

    public static float[] prepare(int[] argb, int width, int height, int size) {
        if (width <= 0 || height <= 0 || size <= 0 || (long) width * height != argb.length)
            throw new IllegalArgumentException("Invalid image dimensions.");
        float[] output = new float[3 * size * size];
        for (int y = 0; y < size; y++) {
            float sy = Math.max(0, (y + 0.5f) * ((float) height / size) - 0.5f);
            int y0 = Math.min((int) sy, height - 1), y1 = Math.min(y0 + 1, height - 1);
            float fy = sy - y0;
            for (int x = 0; x < size; x++) {
                float sx = Math.max(0, (x + 0.5f) * ((float) width / size) - 0.5f);
                int x0 = Math.min((int) sx, width - 1), x1 = Math.min(x0 + 1, width - 1);
                float fx = sx - x0;
                int a = argb[y0 * width + x0], b = argb[y0 * width + x1];
                int c = argb[y1 * width + x0], d = argb[y1 * width + x1];
                for (int channel = 0; channel < 3; channel++) {
                    int shift = 16 - 8 * channel;
                    float top = (1 - fx) * (((a >> shift) & 255) / 255f)
                            + fx * (((b >> shift) & 255) / 255f);
                    float bottom = (1 - fx) * (((c >> shift) & 255) / 255f)
                            + fx * (((d >> shift) & 255) / 255f);
                    float value = (1 - fy) * top + fy * bottom;
                    output[channel * size * size + y * size + x] = (value - MEAN[channel]) / STD[channel];
                }
            }
        }
        return output;
    }
}
