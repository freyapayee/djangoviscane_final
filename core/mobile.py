"""Farmer deployment boundary; client markers only shape presentation."""
import re

from django.conf import settings
from django.http import HttpResponseForbidden


FARMER_PATHS = {
    "/", "/auth", "/auth/register-success", "/logout", "/homepage",
    "/farmer/recommendations", "/farmer/agronomic-logs", "/farmer/settings",
    "/farmer/news", "/about-viscane", "/farmer/notifications", "/farmer/feedback", "/scan/new", "/calculate", "/api/scan/predict",
    "/i18n/setlang", "/favicon.ico",
}


def is_farmer_path(path):
    normalized_path = path.rstrip("/") or "/"
    return (normalized_path in FARMER_PATHS or
            re.fullmatch(r"/farmer/cv-upload/[0-9]+/(delete|image)", normalized_path) is not None or
            re.fullmatch(r"/farmer/profile-photo/[0-9]+", normalized_path) is not None or
            normalized_path.startswith(("/static/", "/media/")))


class FarmerPortalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/static/uploads/cv_scans/"):
            return HttpResponseForbidden("Use the authenticated image endpoint.")
        request.farmer_only = settings.FARMER_ONLY or "ViscaneFarmer/" in request.headers.get("User-Agent", "")
        if request.farmer_only and not is_farmer_path(request.path):
            return HttpResponseForbidden("This portal is available to farmers only.")
        response = self.get_response(request)
        if request.farmer_only:
            from django.utils.cache import patch_vary_headers
            patch_vary_headers(response, ("User-Agent",))
        if is_farmer_path(request.path) and not request.path.startswith("/static/"):
            response["Cache-Control"] = "no-store"
        return response
