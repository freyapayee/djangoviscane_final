package com.viscane.offline

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import org.json.JSONObject
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Private cached farmer screens and feedback queue. Never a second account database. */
class OfflineFarmerCache(private val context: Context) {
    private val alias = "viscane-offline-farmer-content-v1"
    private val root get() = File(context.filesDir, "offline-farmer-content")

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

    private fun directory(farmerId: Long): File {
        require(farmerId > 0)
        return File(root, farmerId.toString()).apply { mkdirs() }
    }

    private fun write(file: File, record: JSONObject) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val temporary = File(file.parentFile, "${file.name}.tmp")
        DataOutputStream(temporary.outputStream()).use {
            it.writeInt(cipher.iv.size)
            it.write(cipher.iv)
            it.write(cipher.doFinal(record.toString().toByteArray(Charsets.UTF_8)))
        }
        require(temporary.renameTo(file)) { "Could not save offline farmer data." }
    }

    private fun read(file: File): JSONObject = DataInputStream(file.inputStream()).use { input ->
        val ivSize = input.readInt()
        require(ivSize == 12) { "Invalid saved farmer data." }
        val iv = ByteArray(ivSize).also { input.readFully(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
        }
        JSONObject(String(cipher.doFinal(input.readBytes()), Charsets.UTF_8))
    }

    fun saveSnapshot(farmerId: Long, snapshot: JSONObject) {
        require(snapshot.getLong("farmer_id") == farmerId)
        write(File(directory(farmerId), "snapshot.bin"), snapshot)
    }

    fun snapshot(farmerId: Long): JSONObject? {
        val file = File(directory(farmerId), "snapshot.bin")
        if (!file.exists()) return null
        return read(file).also { require(it.getLong("farmer_id") == farmerId) }
    }

    fun saveFeedback(farmerId: Long, message: String): JSONObject {
        val clean = message.trim()
        require(clean.isNotEmpty() && clean.length <= 5000) { "Enter feedback of 1 to 5000 characters." }
        val id = UUID.randomUUID().toString()
        val record = JSONObject().put("id", id).put("farmer_id", farmerId)
            .put("message", clean).put("created_at", System.currentTimeMillis())
        write(File(directory(farmerId), "$id.feedback"), record)
        return record
    }

    fun saveProfileDraft(farmerId: Long, originalEmail: String, originalVersion: String,
                         email: String, phone: String,
                         province: String, municipality: String, barangay: String): JSONObject {
        val cleanEmail = email.trim().lowercase()
        val cleanPhone = phone.trim()
        require(originalVersion.length == 64 && cleanEmail.contains('@') && cleanPhone.length == 11 && cleanPhone.all(Char::isDigit)
            && province.isNotBlank() && municipality.isNotBlank() && barangay.isNotBlank()) {
            "Enter a valid email, 11-digit phone, province, municipality, and barangay."
        }
        val record = JSONObject().put("id", UUID.randomUUID().toString())
            .put("farmer_id", farmerId).put("original_email", originalEmail.trim().lowercase())
            .put("original_version", originalVersion)
            .put("email", cleanEmail).put("phone", cleanPhone)
            .put("province", province.trim()).put("municipality", municipality.trim())
            .put("barangay", barangay.trim()).put("created_at", System.currentTimeMillis())
        write(File(directory(farmerId), "profile.pending"), record)
        return record
    }

    fun profileDraft(farmerId: Long): JSONObject? {
        val file = File(directory(farmerId), "profile.pending")
        if (!file.exists()) return null
        return read(file).also { require(it.getLong("farmer_id") == farmerId) }
    }

    fun setProfileSyncError(farmerId: Long, id: String, message: String) {
        val file = File(directory(farmerId), "profile.pending")
        if (!file.exists()) return
        val record = read(file)
        if (record.getString("id") != id) return
        record.put("sync_error", message.take(300))
        write(file, record)
    }

    fun markProfileSynced(farmerId: Long, id: String) {
        val pending = File(directory(farmerId), "profile.pending")
        if (!pending.exists()) return
        require(read(pending).getString("id") == id)
        require(pending.delete()) { "Server saved profile, but local state could not be updated." }
    }

    fun markAnnouncementsRead(farmerId: Long, announcementId: Int) {
        require(announcementId >= 0)
        write(File(directory(farmerId), "notification-read.pending"),
            JSONObject().put("farmer_id", farmerId).put("announcement_id", announcementId))
    }

    fun pendingReadReceipt(farmerId: Long): JSONObject? {
        val file = File(directory(farmerId), "notification-read.pending")
        if (!file.exists()) return null
        return read(file).also { require(it.getLong("farmer_id") == farmerId) }
    }

    fun markReadSynced(farmerId: Long, announcementId: Int) {
        val file = File(directory(farmerId), "notification-read.pending")
        if (!file.exists()) return
        require(read(file).getInt("announcement_id") == announcementId)
        require(file.delete())
    }

    fun feedback(farmerId: Long, pendingOnly: Boolean = false): List<JSONObject> =
        directory(farmerId).listFiles { file ->
            file.extension == "feedback" || (!pendingOnly && file.extension == "synced")
        }.orEmpty().map { file ->
            read(file).also {
                require(it.getLong("farmer_id") == farmerId && it.getString("id") == file.nameWithoutExtension)
                it.put("synced", file.extension == "synced")
            }
        }.sortedByDescending { it.getLong("created_at") }

    fun markFeedbackSynced(farmerId: Long, id: String) {
        require(UUID.fromString(id).toString() == id)
        val directory = directory(farmerId)
        val pending = File(directory, "$id.feedback")
        val synced = File(directory, "$id.synced")
        if (synced.exists()) {
            require(!pending.exists() || pending.delete())
            return
        }
        require(pending.renameTo(synced)) { "Server saved feedback, but local state could not be updated." }
    }
}
