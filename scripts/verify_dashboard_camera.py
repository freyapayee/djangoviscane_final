"""Verify dashboard camera states and geometry using a disposable database."""
import json
import os
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "viscane.settings")
import django
django.setup()
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.contrib.staticfiles.handlers import StaticFilesHandler
from core.models import User
from PIL import Image
from playwright.sync_api import sync_playwright


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def login(page, base):
    page.goto(base + "/auth")
    page.locator('[name="email"]').fill("camera@example.invalid")
    page.locator('[name="password"]').fill("Camera-test-123!")
    page.locator('form[action^="/auth"] button[type="submit"]').click()
    page.wait_for_url("**/homepage")


def main():
    out = ROOT / ".local" / "camera-verification"
    out.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    with tempfile.TemporaryDirectory(prefix="viscane-camera-") as temp:
        settings.DATABASES["default"].update(ENGINE="django.db.backends.sqlite3", NAME=str(Path(temp) / "test.sqlite3"), CONN_MAX_AGE=0)
        settings.DEBUG = True
        settings.FARMER_ONLY = True
        settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
        settings.SECURE_SSL_REDIRECT = False
        settings.SESSION_COOKIE_SECURE = settings.CSRF_COOKIE_SECURE = False
        settings.PRIVATE_UPLOAD_ROOT = Path(temp) / "uploads"
        call_command("migrate", verbosity=0)
        User.objects.create(fullname="Camera Test Farmer", email="camera@example.invalid", phone="0", password=make_password("Camera-test-123!"))
        server = make_server("127.0.0.1", 0, StaticFilesHandler(get_wsgi_application()), handler_class=QuietHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True, args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
                context = browser.new_context(user_agent="Android ViscaneFarmer/1.0")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.add_init_script("navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Denied', 'NotAllowedError'))")
                login(page, base)
                for width, height in [(1440, 900), (320, 740), (390, 844), (768, 1024), (844, 390)]:
                    page.set_viewport_size({"width": width, "height": height})
                    page.locator("#open-camera-btn").click()
                    page.wait_for_function("document.querySelector('#camera-overlay').dataset.cameraState === 'unavailable'")
                    geometry = page.evaluate("""() => {
                        const shell = document.querySelector('.camera-shell').getBoundingClientRect();
                        const controls = document.querySelector('.camera-controls').getBoundingClientRect();
                        return {left:shell.left, right:shell.right, top:shell.top, bottom:shell.bottom,
                            centerOffset: Math.abs((shell.left + shell.right)/2 - innerWidth/2),
                            controlsBottom: controls.bottom, width: innerWidth, height: innerHeight};
                    }""")
                    assert geometry["left"] >= 0 and geometry["right"] <= width + 1, geometry
                    assert geometry["top"] >= 0 and geometry["bottom"] <= height + 1, geometry
                    assert geometry["centerOffset"] <= 1, geometry
                    assert geometry["controlsBottom"] <= height + 1, geometry
                    assert page.locator("#capture-btn").is_hidden()
                    assert page.locator("#camera-stream").evaluate("e => getComputedStyle(e).visibility === 'hidden'")
                    assert page.locator("#native-camera-btn").is_visible()
                    assert page.locator("#upload-photo-btn").bounding_box()["height"] >= 44
                    page.screenshot(path=str(out / f"camera-{width}x{height}.png"))
                    page.keyboard.press("Shift+Tab")
                    assert page.locator("#native-camera-btn").evaluate("e => e === document.activeElement")
                    page.keyboard.press("Escape")
                    assert page.locator("#camera-overlay").is_hidden()
                    assert page.locator("#open-camera-btn").evaluate("e => e === document.activeElement")
                    checks.append({"size": [width, height], "fallback_layout_focus_escape": "PASS"})

                # A permission response arriving after Close must release its camera track.
                page.evaluate("""() => {
                    window.trackStopped = false;
                    navigator.mediaDevices.getUserMedia = () => new Promise(resolve => window.releaseCamera = () => resolve({getTracks: () => [{stop: () => window.trackStopped = true}]}));
                }""")
                page.locator("#open-camera-btn").click()
                page.locator("#close-camera-btn").click()
                page.evaluate("releaseCamera()")
                page.wait_for_function("window.trackStopped")
                assert page.locator("#camera-overlay").is_hidden()
                checks.append({"close_during_permission_request": "PASS"})

                # Exercise the actual live-video and capture path with a fake camera.
                live = context.new_page()
                live.on("pageerror", lambda error: errors.append(str(error)))
                live.set_viewport_size({"width": 390, "height": 844})
                live.goto(base + "/homepage")
                live.locator("#open-camera-btn").click()
                live.wait_for_function("document.querySelector('#camera-overlay').dataset.cameraState === 'live'")
                assert live.locator("#capture-btn").is_enabled()
                prediction = {"prediction": {"variety": "VMC 84-524", "maturity_status": "MATURE", "confidence": .9}}
                with patch("core.views.request_prediction_service", return_value=((json.dumps(prediction).encode(), 200), None, None)):
                    live.locator("#capture-btn").click()
                    live.locator("#cv-results-panel").wait_for(state="visible")
                    live.wait_for_function("!document.querySelector('#upload-photo-btn').disabled")
                    assert "VMC" in live.locator("#cv-results-variety").inner_text()
                    live.screenshot(path=str(out / "camera-live-result.png"))
                    assert live.locator("#capture-btn").inner_text() == "Retake"
                    live.locator("#capture-btn").click()
                    assert live.locator("#camera-preview-image").is_hidden()
                    assert live.locator("#cv-results-panel").is_hidden()
                    assert live.locator("#capture-btn").inner_text() == "Capture"
                checks.append({"live_capture_mock_prediction": "PASS"})
                # Gallery failures must restore both upload and native-camera controls.
                live.locator("#close-camera-btn").click()
                page.evaluate("() => { navigator.mediaDevices.getUserMedia = () => Promise.reject(new Error('No camera')); }")
                page.locator("#open-camera-btn").click()
                photo = BytesIO()
                Image.new("RGB", (16, 16), "green").save(photo, format="JPEG")
                page.route("**/api/scan/predict?*", lambda route: route.fulfill(status=503, content_type="application/json", body='{"error":"Predictor unavailable"}'))
                page.locator("#upload-photo-input").set_input_files({"name": "test.jpg", "mimeType": "image/jpeg", "buffer": photo.getvalue()})
                page.locator("#camera-upload-status.is-error").wait_for()
                assert page.locator("#native-camera-btn").is_enabled()
                assert page.locator("#upload-photo-btn").is_enabled()
                checks.append({"upload_error_restores_controls": "PASS"})
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            from django.db import connections
            connections.close_all()
            (out / "verification.json").write_text(json.dumps({"checks": checks, "page_errors": errors}, indent=2))
    print(f"PASS: {len(checks)} camera checks; screenshots: {out}")


if __name__ == "__main__":
    main()
