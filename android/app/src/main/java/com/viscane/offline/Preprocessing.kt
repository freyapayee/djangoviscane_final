package com.viscane.offline

import android.graphics.Bitmap
import kotlin.math.*

/** RGB, NCHW. Keep float interpolation distinct from PIL's byte interpolation. */
object Preprocessing {
    fun resnet(bitmap: Bitmap, size: Int, mean: FloatArray, std: FloatArray): FloatArray {
        val w = bitmap.width
        val h = bitmap.height
        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)
        val result = FloatArray(3 * size * size)
        for (y in 0 until size) {
            val sy = max(0f, (y + .5f) * (h.toFloat() / size) - .5f)
            val y0 = floor(sy).toInt().coerceAtMost(h - 1)
            val y1 = min(y0 + 1, h - 1)
            val fy = sy - y0
            for (x in 0 until size) {
                val sx = max(0f, (x + .5f) * (w.toFloat() / size) - .5f)
                val x0 = floor(sx).toInt().coerceAtMost(w - 1)
                val x1 = min(x0 + 1, w - 1)
                val fx = sx - x0
                for (c in 0..2) {
                    fun channel(xx: Int, yy: Int) = ((pixels[yy * w + xx] shr (16 - 8 * c)) and 255) / 255f
                    val upper = channel(x0, y0) * (1 - fx) + channel(x1, y0) * fx
                    val lower = channel(x0, y1) * (1 - fx) + channel(x1, y1) * fx
                    result[c * size * size + y * size + x] = (upper * (1 - fy) + lower * fy - mean[c]) / std[c]
                }
            }
        }
        return result
    }

    // Pillow's separable bilinear filter widens its support for downsampling,
    // quantizes coefficients to 22 bits and rounds bytes after each axis.
    private data class Filter(val start: Int, val coefficients: IntArray)
    private fun filters(input: Int, output: Int, offset: Int = 0, count: Int = output): List<Filter> {
        val scale = input.toDouble() / output
        val support = max(1.0, scale)
        return List(count) { i ->
            val center = (i + offset + .5) * scale
            val start = max(0, (center - support + .5).toInt())
            val end = min(input, (center + support + .5).toInt())
            val weights = DoubleArray(end - start) { j -> max(0.0, 1 - abs((j + start - center + .5) / support)) }
            val sum = weights.sum()
            Filter(start, IntArray(weights.size) { j -> floor(weights[j] / sum * (1 shl 22) + .5).toInt() })
        }
    }

    fun yolo(bitmap: Bitmap, size: Int): FloatArray {
        val w = bitmap.width
        val h = bitmap.height
        val rw = if (w <= h) size else (size.toLong() * w / h).toInt()
        val rh = if (h <= w) size else (size.toLong() * h / w).toInt()
        // torchvision CenterCrop uses Python round (ties to even).
        val left = Math.rint((rw - size) / 2.0).toInt()
        val top = Math.rint((rh - size) / 2.0).toInt()
        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)
        val horizontal = filters(w, rw, left, size)
        val vertical = filters(h, rh, top, size)
        // Retain only center-crop columns to bound memory on panoramic images.
        val intermediate = IntArray(h * size * 3)
        for (y in 0 until h) for (x in 0 until size) for (c in 0..2) {
            val f = horizontal[x]
            var value = 1 shl 21
            for (j in f.coefficients.indices) {
                value += ((pixels[y * w + f.start + j] shr (16 - c * 8)) and 255) * f.coefficients[j]
            }
            intermediate[(y * size + x) * 3 + c] = (value shr 22).coerceIn(0, 255)
        }
        val result = FloatArray(3 * size * size)
        for (y in 0 until size) for (x in 0 until size) for (c in 0..2) {
            val f = vertical[y]
            var value = 1 shl 21
            for (j in f.coefficients.indices) value += intermediate[((f.start + j) * size + x) * 3 + c] * f.coefficients[j]
            result[c * size * size + y * size + x] = (value shr 22).coerceIn(0, 255) / 255f
        }
        return result
    }
}
