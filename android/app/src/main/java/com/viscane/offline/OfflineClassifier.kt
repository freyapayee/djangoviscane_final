package com.viscane.offline

import android.content.Context
import android.graphics.Bitmap
import ai.onnxruntime.*
import org.json.JSONObject
import java.nio.FloatBuffer
import java.security.MessageDigest
import kotlin.math.exp

data class Prediction(val label: String, val confidence: Float) {
    val variety get() = label.substringBefore("__")
    val maturity get() = label.substringAfter("__").replace('_', ' ')
}

class OfflineClassifier(context: Context) : AutoCloseable {
    private val environment = OrtEnvironment.getEnvironment()
    private val assets = context.applicationContext.assets
    private val config = JSONObject(assets.open("model_config.json").bufferedReader().use { it.readText() })
    val labels = assets.open("labels.txt").bufferedReader().use { it.readLines() }.filter { it.isNotBlank() }
    private val sessions = mutableMapOf<String, OrtSession>()

    init {
        require(labels.size == 9 && labels.distinct().size == 9)
        require((0 until config.getJSONArray("classes").length()).map { config.getJSONArray("classes").getString(it) } == labels)
        try {
            for (name in listOf("resnet18", "yolov8")) {
                val spec = config.getJSONObject("models").getJSONObject(name)
                val bytes = assets.open(spec.getString("file")).use { it.readBytes() }
                val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) }
                require(hash == spec.getString("sha256")) { "Model integrity check failed: $name" }
                OrtSession.SessionOptions().use { options ->
                    options.setIntraOpNumThreads(2)
                    sessions[name] = environment.createSession(bytes, options)
                }
                val session = sessions.getValue(name)
                val input = session.inputInfo.getValue("image").info as TensorInfo
                require(input.shape.contentEquals(longArrayOf(1, 3, spec.getLong("image_size"), spec.getLong("image_size"))))
                require((session.outputInfo.getValue("scores").info as TensorInfo).shape.contentEquals(longArrayOf(1, 9)))
            }
        } catch (error: Throwable) {
            close()
            throw error
        }
    }

    fun preprocess(bitmap: Bitmap, name: String): FloatArray {
        val spec = config.getJSONObject("models").getJSONObject(name)
        val size = spec.getInt("image_size")
        return if (name == "resnet18") Preprocessing.resnet(bitmap, size,
            FloatArray(3) { spec.getJSONArray("normalization_mean").getDouble(it).toFloat() },
            FloatArray(3) { spec.getJSONArray("normalization_std").getDouble(it).toFloat() })
        else Preprocessing.yolo(bitmap, size)
    }

    fun probabilities(bitmap: Bitmap): FloatArray {
        val scores = mutableMapOf<String, FloatArray>()
        for (name in listOf("resnet18", "yolov8")) {
            val size = config.getJSONObject("models").getJSONObject(name).getLong("image_size")
            OnnxTensor.createTensor(environment, FloatBuffer.wrap(preprocess(bitmap, name)), longArrayOf(1, 3, size, size)).use { input ->
                sessions.getValue(name).run(mapOf("image" to input)).use { output ->
                    val buffer = (output[0] as OnnxTensor).floatBuffer
                    val result = FloatArray(labels.size)
                    buffer.get(result)
                    require(result.all { it.isFinite() }) { "Invalid model output" }
                    if (name == "resnet18") {
                        val max = result.max()
                        val exps = FloatArray(result.size) { exp((result[it] - max).toDouble()).toFloat() }
                        val sum = exps.sum()
                        scores[name] = FloatArray(result.size) { exps[it] / sum }
                    } else scores[name] = result
                }
            }
        }
        val fusion = config.getJSONObject("fusion")
        return FloatArray(labels.size) {
            scores.getValue("resnet18")[it] * fusion.getDouble("resnet18_weight").toFloat() +
                scores.getValue("yolov8")[it] * fusion.getDouble("yolov8_weight").toFloat()
        }
    }

    fun classify(bitmap: Bitmap) = probabilities(bitmap).mapIndexed { i, score -> Prediction(labels[i], score) }.sortedByDescending { it.confidence }

    override fun close() {
        sessions.values.forEach { it.close() }
        sessions.clear()
    }
}
