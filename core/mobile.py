"""Farmer deployment boundary; client markers only shape presentation."""
import re

from django.conf import settings
from django.http import HttpResponseForbidden


FARMER_PATHS = {
    "/", "/auth", "/auth/register-success", "/logout", "/homepage",
    "/farmer/recommendations", "/farmer/agronomic-logs", "/farmer/settings",
    "/farmer/feedback", "/scan/new", "/calculate", "/api/scan/predict",
    "/i18n/setlang/",
}


def is_farmer_path(path):
    return (path in FARMER_PATHS or
            re.fullmatch(r"/farmer/cv-upload/[0-9]+/(delete|image)", path) is not None or
            path.startswith(("/static/", "/media/")))


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
        if request.path in FARMER_PATHS and not request.path.startswith("/static/"):
            response["Cache-Control"] = "no-store"
        return response
