package com.viscane.offline

import android.content.Context
import android.graphics.Bitmap
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class PendingScan(
    val id: String,
    val farmerId: Long,
    val label: String,
    val confidence: Float,
    val createdAt: Long,
    val jpeg: ByteArray,
)

data class PendingScanSummary(
    val id: String,
    val label: String,
    val confidence: Float,
    val createdAt: Long,
    val synced: Boolean,
)

/** Encrypted on-device results. Sync changes the state; it does not remove a result. */
class OfflineScanStore(private val context: Context) {
    private val alias = "viscane-offline-scans-v1"
    private val root get() = File(context.filesDir, "offline-pending")

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(alias,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).build())
        return generator.generateKey()
    }

    private fun recordFile(farmerId: Long, id: String): File {
        require(farmerId > 0 && UUID.fromString(id).toString() == id)
        return File(File(root, farmerId.toString()), "$id.bin")
    }

    fun save(farmerId: Long, prediction: Prediction, bitmap: Bitmap): PendingScan {
        val photo = ByteArrayOutputStream().use { output ->
            require(bitmap.compress(Bitmap.CompressFormat.JPEG, 88, output))
            output.toByteArray()
        }
        require(photo.size <= 10_000_000) { "Photo is too large to sync; choose a smaller photo." }
        val scan = PendingScan(UUID.randomUUID().toString(), farmerId,
            prediction.label, prediction.confidence, System.currentTimeMillis(), photo)
        val metadata = JSONObject()
            .put("id", scan.id).put("farmer_id", farmerId)
            .put("label", scan.label).put("confidence", scan.confidence.toDouble())
            .put("created_at", scan.createdAt).toString().toByteArray(Charsets.UTF_8)
        val plain = ByteArrayOutputStream().also { bytes ->
            DataOutputStream(bytes).use { stream ->
                stream.writeInt(metadata.size)
                stream.write(metadata)
                stream.write(photo)
            }
        }.toByteArray()
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val target = recordFile(farmerId, scan.id)
        target.parentFile?.mkdirs()
        val temporary = File(target.parentFile, "${scan.id}.tmp")
        DataOutputStream(temporary.outputStream()).use { stream ->
            stream.writeInt(cipher.iv.size)
            stream.write(cipher.iv)
            stream.write(cipher.doFinal(plain))
        }
        require(temporary.renameTo(target)) { "Could not save pending scan." }
        return scan
    }

    fun pendingCount(farmerId: Long): Int = pendingFiles(farmerId).size

    fun totalCount(farmerId: Long): Int = files(farmerId).size

    private fun pendingFiles(farmerId: Long): List<File> =
        files(farmerId).filter { it.extension == "bin" }

    private fun files(farmerId: Long): List<File> = if (farmerId <= 0) emptyList() else
        File(root, farmerId.toString()).listFiles { file -> file.extension in setOf("bin", "synced") }
            .orEmpty().sortedByDescending { it.lastModified() }

    fun summaries(farmerId: Long): List<PendingScanSummary> = files(farmerId).mapNotNull { file ->
        try {
            val scan = readFile(farmerId, file)
            PendingScanSummary(scan.id, scan.label, scan.confidence, scan.createdAt, file.extension == "synced")
        } catch (_: java.io.FileNotFoundException) {
            // A successful sync can rename this file while the list is being read.
            null
        }
    }

    fun read(farmerId: Long, id: String): PendingScan {
        val pending = recordFile(farmerId, id)
        val file = if (pending.exists()) pending else File(pending.parentFile, "$id.synced")
        return readFile(farmerId, file)
    }

    fun pending(farmerId: Long, limit: Int = 5): List<PendingScan> =
        pendingFiles(farmerId).take(limit).map { readFile(farmerId, it) }

    private fun readFile(farmerId: Long, file: File): PendingScan {
        require(farmerId > 0)
        return DataInputStream(file.inputStream()).use { stream ->
                    val ivSize = stream.readInt()
                    require(ivSize == 12) { "Invalid pending scan." }
                    val iv = ByteArray(ivSize).also { stream.readFully(it) }
                    val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
                        init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
                    }
                    val plain = DataInputStream(cipher.doFinal(stream.readBytes()).inputStream())
                    val metaSize = plain.readInt()
                    require(metaSize in 1..4096) { "Invalid pending scan metadata." }
                    val metaBytes = ByteArray(metaSize).also { plain.readFully(it) }
                    val meta = JSONObject(String(metaBytes, Charsets.UTF_8))
                    val id = meta.getString("id")
                    require(id == file.nameWithoutExtension && meta.getLong("farmer_id") == farmerId)
                    PendingScan(id, farmerId, meta.getString("label"),
                        meta.getDouble("confidence").toFloat(), meta.getLong("created_at"), plain.readBytes())
                }
    }

    fun markSynced(scan: PendingScan) {
        val pending = recordFile(scan.farmerId, scan.id)
        val synced = File(pending.parentFile, "${scan.id}.synced")
        if (synced.exists()) {
            require(!pending.exists() || pending.delete()) { "Server saved scan, but local status could not be updated." }
            return
        }
        require(pending.renameTo(synced)) { "Server saved scan, but local status could not be updated." }
    }
}
