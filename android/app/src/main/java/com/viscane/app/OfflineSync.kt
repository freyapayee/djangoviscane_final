package com.viscane.app

import android.content.Context
import android.webkit.CookieManager
import com.viscane.offline.OfflineScanStore
import com.viscane.offline.PendingScan
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
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
        while (true) {
            val batch = queue.pending(farmerId)
            if (batch.isEmpty()) break
            for (scan in batch) {
                if (!send(baseUrl, scan)) return count
                queue.markSynced(scan)
                count++
            }
        }
        return count
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
}
