package com.viscane.app

import java.net.URI

/** Exact origin and decoded-path validation, shared by navigation and permission checks. */
class FarmerNavigation(baseUrl: String) {
    private val base = URI(baseUrl)
    private val paths = setOf("/", "/auth", "/auth/register-success", "/logout", "/homepage", "/service-worker.js",
        "/farmer/recommendations", "/farmer/agronomic-logs", "/farmer/settings",
        "/farmer/news", "/farmer/notifications", "/farmer/feedback", "/about-viscane", "/favicon.ico",
        "/scan/new", "/calculate", "/api/scan/predict", "/api/mobile/session", "/api/mobile/offline-scan", "/i18n/setlang/")

    fun sameOrigin(url: String): Boolean = runCatching {
        val uri = URI(url)
        uri.scheme == base.scheme && uri.host.equals(base.host, ignoreCase = true) &&
            port(uri) == port(base) && uri.rawUserInfo == null
    }.getOrDefault(false)

    fun allows(url: String): Boolean = runCatching {
        val uri = URI(url)
        val path = uri.path.ifEmpty { "/" }
        sameOrigin(url) && uri.rawPath == uri.path && uri.normalize().path == uri.path && !path.contains("\\") &&
            (path in paths || path.matches(Regex("/farmer/cv-upload/[0-9]+/(delete|image)")) ||
                path.matches(Regex("/farmer/profile-photo/[0-9]+")) ||
                path.startsWith("/static/") || path.startsWith("/media/"))
    }.getOrDefault(false)

    private fun port(uri: URI) = if (uri.port != -1) uri.port else if (uri.scheme == "https") 443 else 80

    companion object {
        fun validOrigin(url: String, allowHttp: Boolean): Boolean = runCatching {
            val uri = URI(url)
            (uri.scheme == "https" || (allowHttp && uri.scheme == "http")) &&
                !uri.host.isNullOrBlank() && uri.rawUserInfo == null && uri.query == null &&
                uri.fragment == null && uri.path in setOf("", "/")
        }.getOrDefault(false)
    }
}
