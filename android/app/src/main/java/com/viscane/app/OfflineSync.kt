package com.viscane.app

import android.content.Context
import android.webkit.CookieManager
import com.viscane.offline.OfflineScanStore
import com.viscane.offline.OfflineAssessmentStore
import com.viscane.offline.OfflineFarmerCache
import com.viscane.offline.PendingScan
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.UUID

/** Uses only the existing production WebView farmer session; failures retain local records. */
object OfflineSync {
    private const val RESNET_HASH = "37be5dd4ccf618a94d86d0e3a26e040e0617c6827cdb00ec74548aa426f66823"
    private const val YOLO_HASH = "cdf5b713b21bf9fa83924857b10ff3c923d91c1e5457a3f68221700b99b7ca48"

    fun authenticatedFarmerId(baseUrl: String): Long? {
        if (!baseUrl.startsWith("https://")) return null
        val connection = connection(baseUrl, "api/mobile/session", "GET")
        return try {
            if (connection.responseCode != 200) null
            else {
                connection.headerFields.entries.firstOrNull {
                    it.key?.equals("Set-Cookie", ignoreCase = true) == true
                }?.value.orEmpty().forEach {
                    CookieManager.getInstance().setCookie(baseUrl, it)
                }
                CookieManager.getInstance().flush()
                JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                    .getLong("farmer_id").takeIf { it > 0 }
            }
        } finally {
            connection.disconnect()
        }
    }

    fun sync(context: Context, baseUrl: String, farmerId: Long): Int {
        if (!baseUrl.startsWith("https://") || farmerId <= 0) return 0
        val queue = OfflineScanStore(context)
        var count = 0
        var scansReady = true
        while (true) {
            val batch = queue.pending(farmerId)
            if (batch.isEmpty()) break
            for (scan in batch) {
                if (!send(baseUrl, scan)) { scansReady = false; break }
                queue.markSynced(scan)
                count++
            }
            if (!scansReady) break
        }
        if (scansReady) {
            val assessments = OfflineAssessmentStore(context)
            for (record in assessments.records(farmerId, pendingOnly = true)) {
                if (!sendAssessment(baseUrl, farmerId, record)) break
                assessments.markSynced(farmerId, record.getString("id"))
                count++
            }
        }
        val cache = OfflineFarmerCache(context)
        cache.profileDraft(farmerId)?.let { draft ->
            val profileResult = sendProfile(baseUrl, farmerId, draft)
            if (profileResult.first) {
                cache.markProfileSynced(farmerId, draft.getString("id"))
                count++
            } else profileResult.second?.let { cache.setProfileSyncError(farmerId, draft.getString("id"), it) }
        }
        for (record in cache.feedback(farmerId, pendingOnly = true)) {
            if (!sendFeedback(baseUrl, farmerId, record)) break
            cache.markFeedbackSynced(farmerId, record.getString("id"))
            count++
        }
        cache.pendingReadReceipt(farmerId)?.let { receipt ->
            val id = receipt.getInt("announcement_id")
            if (sendReadReceipt(baseUrl, id)) cache.markReadSynced(farmerId, id)
        }
        return count
    }

    fun refreshContent(context: Context, baseUrl: String, farmerId: Long): Boolean {
        if (!baseUrl.startsWith("https://") || farmerId <= 0) return false
        val connection = connection(baseUrl, "api/mobile/offline-content", "GET")
        return try {
            if (connection.responseCode != 200) false else {
                val snapshot = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                if (snapshot.getLong("farmer_id") != farmerId) false
                else { OfflineFarmerCache(context).saveSnapshot(farmerId, snapshot); true }
            }
        } finally { connection.disconnect() }
    }

    private fun connection(baseUrl: String, path: String, method: String): HttpURLConnection {
        val url = URL(URL(baseUrl), path)
        require(url.protocol == "https" && url.host == URL(baseUrl).host)
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            instanceFollowRedirects = false
            connectTimeout = 15_000
            readTimeout = 30_000
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "Android ViscaneFarmer/1.0")
        }
        CookieManager.getInstance().getCookie(baseUrl)?.let { connection.setRequestProperty("Cookie", it) }
        return connection
    }

    private fun send(baseUrl: String, scan: PendingScan): Boolean {
        val cookies = CookieManager.getInstance().getCookie(baseUrl).orEmpty()
        val csrf = cookies.split(';').map { it.trim() }
            .firstOrNull { it.startsWith("csrftoken=") }?.substringAfter('=') ?: return false
        val boundary = "viscane-${UUID.randomUUID()}"
        val body = ByteArrayOutputStream()
        fun field(name: String, value: String) {
            body.write("--$boundary\r\nContent-Disposition: form-data; name=\"$name\"\r\n\r\n$value\r\n".toByteArray())
        }
        field("record_id", scan.id)
        field("farmer_id", scan.farmerId.toString())
        field("label", scan.label)
        field("confidence", scan.confidence.toString())
        field("resnet18_sha256", RESNET_HASH)
        field("yolov8_sha256", YOLO_HASH)
        body.write("--$boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"offline-scan.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".toByteArray())
        body.write(scan.jpeg)
        body.write("\r\n--$boundary--\r\n".toByteArray())
        val connection = connection(baseUrl, "api/mobile/offline-scan", "POST")
        return try {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            connection.setRequestProperty("X-CSRFToken", csrf)
            connection.setRequestProperty("Referer", baseUrl)
            connection.outputStream.use { it.write(body.toByteArray()) }
            if (connection.responseCode !in listOf(200, 201)) false
            else {
                val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                response.optBoolean("synced") && response.optString("record_id") == scan.id && response.optLong("log_id") > 0
            }
        } finally {
            connection.disconnect()
        }
    }

    private fun sendAssessment(baseUrl: String, farmerId: Long, record: JSONObject): Boolean {
        val cookies = CookieManager.getInstance().getCookie(baseUrl).orEmpty()
        val csrf = cookies.split(';').map { it.trim() }
            .firstOrNull { it.startsWith("csrftoken=") }?.substringAfter('=') ?: return false
        val fields = mapOf(
            "record_id" to record.getString("id"), "farmer_id" to farmerId.toString(),
            "variety" to record.getInt("variety").toString(),
            "hectares" to record.getDouble("hectares").toString(),
            "plowing" to record.getInt("plowing").toString(),
            "weeding" to record.getInt("weeding").toString(),
            "fertilizer" to record.getInt("fertilizer").toString(),
            "stage" to record.getInt("stage").toString(),
            "infected" to record.getBoolean("infected").toString(),
            "maturity" to record.getInt("maturity").toString(),
            "scan_id" to record.optString("scan_id"),
            "plot_name" to record.optString("plot_name"),
        )
        val body = formBody(fields)
        val connection = connection(baseUrl, "api/mobile/offline-assessment", "POST")
        return try {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
            connection.setRequestProperty("X-CSRFToken", csrf)
            connection.setRequestProperty("Referer", baseUrl)
            connection.outputStream.use { it.write(body) }
            if (connection.responseCode !in listOf(200, 201)) false
            else {
                val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                response.optBoolean("synced") && response.optString("record_id") == record.getString("id") && response.optLong("log_id") > 0
            }
        } finally {
            connection.disconnect()
        }
    }

    private fun sendFeedback(baseUrl: String, farmerId: Long, record: JSONObject): Boolean {
        val cookies = CookieManager.getInstance().getCookie(baseUrl).orEmpty()
        val csrf = cookies.split(';').map { it.trim() }
            .firstOrNull { it.startsWith("csrftoken=") }?.substringAfter('=') ?: return false
        val connection = connection(baseUrl, "api/mobile/offline-feedback", "POST")
        return try {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
            connection.setRequestProperty("X-CSRFToken", csrf)
            connection.setRequestProperty("Referer", baseUrl)
            connection.outputStream.use { it.write(formBody(mapOf(
                "record_id" to record.getString("id"), "farmer_id" to farmerId.toString(),
                "message" to record.getString("message")))) }
            if (connection.responseCode !in listOf(200, 201)) false else {
                val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                response.optBoolean("synced") && response.optString("record_id") == record.getString("id") && response.optLong("feedback_id") > 0
            }
        } finally { connection.disconnect() }
    }

    private fun sendProfile(baseUrl: String, farmerId: Long, record: JSONObject): Pair<Boolean, String?> {
        val cookies = CookieManager.getInstance().getCookie(baseUrl).orEmpty()
        val csrf = cookies.split(';').map { it.trim() }
            .firstOrNull { it.startsWith("csrftoken=") }?.substringAfter('=') ?: return (false to null)
        val connection = connection(baseUrl, "api/mobile/offline-profile", "POST")
        return try {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
            connection.setRequestProperty("X-CSRFToken", csrf)
            connection.setRequestProperty("Referer", baseUrl)
            connection.outputStream.use { it.write(formBody(mapOf(
                "record_id" to record.getString("id"), "farmer_id" to farmerId.toString(),
                "original_email" to record.getString("original_email"),
                "original_version" to record.getString("original_version"),
                "email" to record.getString("email"), "phone" to record.getString("phone"),
                "province" to record.getString("province"),
                "municipality" to record.getString("municipality"),
                "barangay" to record.getString("barangay")))) }
            if (connection.responseCode !in listOf(200, 201)) {
                val message = runCatching { JSONObject(connection.errorStream.bufferedReader().use { it.readText() })
                    .optString("error") }.getOrNull()
                false to message
            } else {
                val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                (response.optBoolean("synced") && response.optString("record_id") == record.getString("id")) to null
            }
        } finally { connection.disconnect() }
    }

    private fun sendReadReceipt(baseUrl: String, announcementId: Int): Boolean {
        val cookies = CookieManager.getInstance().getCookie(baseUrl).orEmpty()
        val csrf = cookies.split(';').map { it.trim() }
            .firstOrNull { it.startsWith("csrftoken=") }?.substringAfter('=') ?: return false
        val connection = connection(baseUrl, "farmer/notifications", "POST")
        return try {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
            connection.setRequestProperty("X-CSRFToken", csrf)
            connection.setRequestProperty("Referer", baseUrl)
            connection.outputStream.use { it.write(formBody(mapOf(
                "announcement_id" to announcementId.toString(), "suggestion_id" to "0"))) }
            connection.responseCode == 200
        } finally { connection.disconnect() }
    }

    private fun formBody(fields: Map<String, String>) = fields.entries.joinToString("&") {
        URLEncoder.encode(it.key, "UTF-8") + "=" + URLEncoder.encode(it.value, "UTF-8")
    }.toByteArray(Charsets.UTF_8)
}
