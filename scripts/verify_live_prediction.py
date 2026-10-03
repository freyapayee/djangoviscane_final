"""Send a public repository sample through the real browser/Django/predictor flow."""
import json
from pathlib import Path
import sqlite3
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.local'
credentials = json.loads((OUT/'browser-test-accounts.json').read_text())
result = {'sample':'static/varieties/vmc-84-524.jpg', 'note':'Smoke test only; not a model-accuracy evaluation.'}
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width':1280,'height':900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto('http://127.0.0.1:5000/auth', wait_until='domcontentloaded')
        page.locator('[name="email"]').fill(credentials['farmer_email'])
        page.locator('[name="password"]').fill(credentials['password'])
        page.locator('form[action^="/auth"] button[type="submit"]').click()
        page.wait_for_url('**/homepage')
        with page.expect_response(lambda response: '/api/scan/predict' in response.url, timeout=90000) as response_info:
            page.locator('#upload-photo-input').set_input_files(str(ROOT/result['sample']))
        response = response_info.value
        result['http_status'] = response.status
        result['response'] = response.json()
        assert response.status == 200, str(result['response'])
        page.wait_for_function("document.querySelector('#cv_prediction_applied').value === '1'" if page.locator('#cv_prediction_applied').count() else "document.querySelector('[name=cv_prediction_applied]').value === '1'")
        result['displayed_prediction'] = page.locator('#cv-results-panel').text_content().strip()
        with sqlite3.connect((OUT/'development.sqlite3').as_uri()+'?mode=ro', uri=True) as db:
            row = db.execute('SELECT c.image_path,c.variety,c.maturity_status,c.confidence FROM cv_scan_upload c JOIN user u ON c.user_id=u.id WHERE u.email=? ORDER BY c.id DESC LIMIT 1', (credentials['farmer_email'],)).fetchone()
        assert row is not None
        assert (ROOT/'static'/row[0]).is_file()
        result['persisted'] = {'image_exists':True,'variety':row[1],'maturity':row[2],'confidence':row[3]}
        page.reload(wait_until='domcontentloaded')
        page.screenshot(path=str(OUT/'browser-live-prediction.png'), full_page=True, animations='disabled')
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(OUT/'browser-mobile.png'), full_page=True, animations='disabled')
        result['page_errors'] = errors
        result['status'] = 'PASS'
    except Exception as exc:
        result['status'] = 'FAIL'
        result['error'] = str(exc)
        raise
    finally:
        (OUT/'live-prediction-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
        browser.close()
