package com.viscane.offline

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import org.json.JSONArray
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

/** Farmer-owned encrypted assessments. Local results remain after server sync. */
class OfflineAssessmentStore(private val context: Context) {
    private val alias = "viscane-offline-assessments-v1"
    private val root get() = File(context.filesDir, "offline-assessments")

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

    fun save(farmerId: Long, variety: Int, hectares: Double, plowing: Int, weeding: Int,
             fertilizer: Int, stage: Int, infected: Boolean, maturity: Int,
             estimate: OfflineCalculator.Result, recommendations: List<OfflineRecommendation>,
             scanId: String?): JSONObject {
        require(farmerId > 0)
        val id = UUID.randomUUID().toString()
        val record = JSONObject()
            .put("id", id).put("farmer_id", farmerId).put("created_at", System.currentTimeMillis())
            .put("rules_version", OfflineRules.VERSION).put("variety", variety)
            .put("hectares", hectares).put("plowing", plowing).put("weeding", weeding)
            .put("fertilizer", fertilizer).put("stage", stage).put("infected", infected)
            .put("maturity", maturity).put("scan_id", scanId ?: "")
            .put("lkg_per_ton", estimate.lkgPerTon).put("total_tons", estimate.totalTons)
            .put("total_lkg", estimate.totalLkg)
            .put("recommendations", JSONArray().apply {
                recommendations.forEach {
                    put(JSONObject().put("category", it.category).put("title", it.title).put("meta", it.detail))
                }
            })
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val directory = File(root, farmerId.toString()).apply { mkdirs() }
        val temporary = File(directory, "$id.tmp")
        val target = File(directory, "$id.bin")
        DataOutputStream(temporary.outputStream()).use {
            it.writeInt(cipher.iv.size)
            it.write(cipher.iv)
            it.write(cipher.doFinal(record.toString().toByteArray(Charsets.UTF_8)))
        }
        require(temporary.renameTo(target)) { "Could not save assessment on this device." }
        return record
    }

    fun records(farmerId: Long, pendingOnly: Boolean = false): List<JSONObject> {
        if (farmerId <= 0) return emptyList()
        return File(root, farmerId.toString()).listFiles { file ->
            file.extension == "bin" || (!pendingOnly && file.extension == "synced")
        }
            .orEmpty().map { file ->
                DataInputStream(file.inputStream()).use { input ->
                    val ivSize = input.readInt()
                    require(ivSize == 12) { "Invalid local assessment." }
                    val iv = ByteArray(ivSize).also { input.readFully(it) }
                    val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
                        init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
                    }
                    val record = JSONObject(String(cipher.doFinal(input.readBytes()), Charsets.UTF_8))
                    require(record.getLong("farmer_id") == farmerId && record.getString("id") == file.nameWithoutExtension)
                    record.put("synced", file.extension == "synced")
                }
            }.sortedByDescending { it.getLong("created_at") }
    }

    fun markSynced(farmerId: Long, id: String) {
        require(farmerId > 0 && UUID.fromString(id).toString() == id)
        val directory = File(root, farmerId.toString())
        val pending = File(directory, "$id.bin")
        val synced = File(directory, "$id.synced")
        if (synced.exists()) {
            require(!pending.exists() || pending.delete())
            return
        }
        require(pending.renameTo(synced)) { "Server saved assessment, but local status could not be updated." }
    }
}
