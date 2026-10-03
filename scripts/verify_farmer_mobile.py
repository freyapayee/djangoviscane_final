"""Browser acceptance checks against a disposable Django database, never live accounts."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from io import BytesIO
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "viscane.settings")
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.contrib.auth.hashers import make_password
from core.models import User
from playwright.sync_api import sync_playwright


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def saved_upload_id():
    from core.models import CvScanUpload
    from django.db import connections
    try:
        return CvScanUpload.objects.get().pk
    finally:
        connections.close_all()


def main():
    out = ROOT / ".local" / "android-readiness"
    out.mkdir(parents=True, exist_ok=True)
    evidence = {"checks": [], "page_errors": []}
    with tempfile.TemporaryDirectory(prefix="viscane-mobile-") as temp:
        settings.DATABASES["default"].update(ENGINE="django.db.backends.sqlite3", NAME=str(Path(temp) / "test.sqlite3"), CONN_MAX_AGE=0)
        settings.DEBUG = True
        settings.FARMER_ONLY = True
        settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
        settings.SECURE_SSL_REDIRECT = False
        settings.SESSION_COOKIE_SECURE = False
        settings.CSRF_COOKIE_SECURE = False
        call_command("migrate", verbosity=0)
        User.objects.create(fullname="Mobile Acceptance Farmer", email="mobile@example.invalid",
            phone="09123456789", password=make_password("Disposable-test-123!"),
            province="Negros Occidental", municipality="Isabela", barangay="Amin")
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        server = make_server("127.0.0.1", 0, StaticFilesHandler(get_wsgi_application()), handler_class=QuietHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(user_agent="Android ViscaneFarmer/1.0", viewport={"width":390,"height":844})
                # Keep local acceptance independent of external font/icon CDN availability.
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base + '/') else route.abort())
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
                page.goto(base + "/auth")
                page.locator('[name="email"]').fill("mobile@example.invalid")
                page.locator('[name="password"]').fill("Disposable-test-123!")
                page.locator('form[action^="/auth"] button[type="submit"]').click()
                page.wait_for_url("**/homepage")
                evidence["checks"].append({"login_with_csrf": "PASS"})
                routes = ["/", "/auth", "/auth?mode=register", "/auth/register-success", "/homepage",
                    "/farmer/recommendations", "/farmer/agronomic-logs", "/farmer/settings", "/scan/new"]
                for width, height in [(320,740),(360,800),(390,844),(412,915),(768,1024),(844,390)]:
                    page.set_viewport_size({"width":width,"height":height})
                    for route in routes:
                        response = page.goto(base + route, wait_until="networkidle")
                        assert response.status == 200, (route, response.status)
                        overflow = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth")
                        assert overflow <= 1, (route, width, "horizontal overflow", overflow)
                        assert page.locator('a[href^="/admin"],a[href^="/superadmin"]').count() == 0, route
                        evidence["checks"].append({"route":route,"width":width,"height":height,"overflow":overflow,"status":"PASS"})
                        if width == 390:
                            name = (route.split('?')[0].strip('/').replace('/','-') or "portal") + ".png"
                            page.screenshot(path=str(out / name), full_page=True)
                        if route == '/scan/new':
                            assert page.locator('.scanner-viewport').get_attribute('data-camera-state') == 'upload'
                            assert page.locator('#viewfinder').is_hidden()
                            assert page.locator('.ar-overlay').is_hidden()
                            assert page.locator('#capture-btn').is_hidden()
                            assert page.locator('.scanner-placeholder').is_visible()
                            photo_button = page.locator('#take-photo-btn').bounding_box()
                            upload_button = page.locator('#upload-image-btn').bounding_box()
                            viewport = page.locator('.scanner-viewport').bounding_box()
                            assert min(photo_button['height'], upload_button['height']) >= 48
                            assert abs(photo_button['y'] - upload_button['y']) <= 1
                            assert photo_button['y'] >= viewport['y'] + viewport['height']
                            with page.expect_file_chooser() as chooser:
                                page.locator('#take-photo-btn').click()
                            assert chooser.value.element.get_attribute('capture') == 'environment'
                            with page.expect_file_chooser() as chooser:
                                page.locator('#upload-image-btn').click()
                            assert chooser.value.element.get_attribute('id') == 'scan-upload'
                            evidence['checks'].append({'scanner_fallback_and_photo_controls': 'PASS', 'width': width})
                for route in ["/admin-access", "/admin-login", "/superadmin-login", "/admin-setup", "/admin", "/superadmin"]:
                    assert context.request.get(base + route).status == 403, route
                page.goto(base + "/farmer/settings")
                page.locator('[name="phone"]').fill("09987654321")
                with page.expect_navigation(wait_until="networkidle"):
                    page.locator('form').filter(has=page.locator('[name="phone"]')).locator('button[type="submit"]').click()
                assert "Profile updated successfully" in page.locator("body").inner_text()
                evidence["checks"].append({"profile_post_with_csrf":"PASS", "administrator_routes":"BLOCKED"})
                page.goto(base + "/scan/new", wait_until="networkidle")
                photo = BytesIO()
                Image.new("RGB", (16,16), "green").save(photo, format="JPEG")
                prediction = {"prediction":{"variety":"VMC 84-524", "maturity_status":"MATURE", "confidence":0.9}}
                with patch("core.views.request_prediction_service", return_value=((json.dumps(prediction).encode(),200),None,None)), \
                        patch.object(settings, "PRIVATE_UPLOAD_ROOT", Path(temp) / "uploads"):
                    with page.expect_response(lambda response: "/api/scan/predict" in response.url) as submitted:
                        page.locator("#scan-upload").set_input_files({"name":"test.jpg", "mimeType":"image/jpeg", "buffer":photo.getvalue()})
                    assert submitted.value.status == 200
                    page.locator("#scan-result").wait_for(state="visible")
                    assert "VMC 84-524" in page.locator("#result-variety").inner_text()
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        upload_id = executor.submit(saved_upload_id).result()
                    assert context.request.get(base + f"/farmer/cv-upload/{upload_id}/image").status == 200
                evidence["checks"].append({"gallery_upload_csrf_mock_prediction_private_image":"PASS"})
                # A browser opens its preview only after an explicit camera choice.
                page.add_init_script("Object.defineProperty(navigator, 'userAgent', {value: 'Browser acceptance test'});")
                page.set_viewport_size({'width': 1267, 'height': 960})
                page.goto(base + '/scan/new', wait_until='networkidle')
                page.screenshot(path=str(out / 'scan-upload-desktop.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                page.evaluate("""() => {
                    window.cameraRequests = 0;
                    navigator.mediaDevices.getUserMedia = async () => {
                        window.cameraRequests += 1;
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        const stream = canvas.captureStream(5);
                        window.setInterval(() => ctx.fillRect(0, 0, canvas.width, canvas.height), 100);
                        return stream;
                    };
                }""")
                assert page.evaluate('window.cameraRequests') == 0
                assert page.locator('#capture-btn').is_hidden()
                page.locator('#take-photo-btn').click()
                page.wait_for_function("document.querySelector('.scanner-viewport').dataset.cameraState === 'live'")
                assert page.locator('#viewfinder').is_visible()
                assert page.locator('.ar-overlay').is_visible()
                assert page.locator('.scanner-placeholder').is_hidden()
                assert page.locator('#capture-btn').is_enabled()
                assert page.locator('#take-photo-btn').is_hidden()
                assert page.locator('#upload-image-btn').is_visible()
                page.screenshot(path=str(out / 'scan-live-preview.png'), full_page=True)
                evidence['checks'].append({'scanner_live_preview': 'PASS'})
                page.locator('#close-camera-btn').click()
                assert page.locator('#capture-btn').is_hidden()
                assert page.locator('#take-photo-btn').is_visible()
                assert page.evaluate("document.querySelector('#viewfinder').srcObject === null")
                page.evaluate("() => {navigator.mediaDevices.getUserMedia = async () => {throw new Error('Permission denied')};}")
                page.locator('#take-photo-btn').click()
                page.wait_for_function("document.querySelector('.scanner-viewport').dataset.cameraState === 'unavailable'")
                assert page.locator('#capture-btn').is_hidden()
                with page.expect_file_chooser() as chooser:
                    page.locator('#upload-image-btn').click()
                assert chooser.value.element.get_attribute('id') == 'scan-upload'
                evidence['checks'].append({'explicit_camera_close_and_denial': 'PASS'})
                assert not evidence["page_errors"], evidence["page_errors"]
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            from django.db import connections
            connections.close_all()
            (out / "verification.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"PASS: {len(evidence['checks'])} browser checks; evidence: {out}")


if __name__ == "__main__":
    main()
