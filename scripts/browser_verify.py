"""Exercise the local Django UI in headless Edge, saving evidence under .local."""
import json
from pathlib import Path
import secrets
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.local'
OUT.mkdir(exist_ok=True)
BASE = 'http://127.0.0.1:5000'
credentials_path = OUT / 'browser-test-accounts.json'
fresh = not credentials_path.exists()
if fresh:
    tag = secrets.token_hex(4)
    credentials = {'farmer_email': f'qa-{tag}@example.invalid', 'admin_username': f'qa-{tag}',
                   'admin_email': f'qa-admin-{tag}@example.invalid', 'password': secrets.token_urlsafe(24)}
    credentials_path.write_text(json.dumps(credentials, indent=2), encoding='utf-8')
else:
    credentials = json.loads(credentials_path.read_text(encoding='utf-8'))
evidence = {'checks': [], 'console_errors': [], 'page_errors': [], 'failed_requests': []}
def passed(name, detail):
    evidence['checks'].append({'name':name, 'status':'PASS', 'detail':detail})

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context(viewport={'width':1280, 'height':900})
    page = context.new_page()
    page.on('pageerror', lambda error: evidence['page_errors'].append(str(error)))
    page.on('console', lambda message: evidence['console_errors'].append(message.text) if message.type == 'error' else None)
    page.on('requestfailed', lambda request: evidence['failed_requests'].append({'url':request.url, 'error':request.failure}))
    try:
        response = page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
        assert response.status == 200
        assert 'VISCANE' in page.locator('body').inner_text().upper()
        page.screenshot(path=str(OUT/'browser-portal.png'), full_page=True)
        passed('Portal renders', page.title())
        if fresh:
            page.goto(BASE+'/auth?mode=register', wait_until='domcontentloaded')
            for name,value in {'fullname':'Browser QA Farmer','email':credentials['farmer_email'],
                               'phone':'09123456789','password':credentials['password'],
                               'confirm_password':credentials['password']}.items():
                page.locator(f'[name="{name}"]').fill(value)
            for name,value in {'province':'Negros Occidental','municipality':'Isabela','barangay':'Amin'}.items():
                page.locator(f'[name="{name}"]').select_option(value)
            page.locator('form[action^="/auth"] button[type="submit"]').click()
            page.wait_for_url('**/auth/register-success')
            passed('Farmer registration', 'Success page reached through form submission')
            page.goto(BASE+'/logout', wait_until='domcontentloaded')
        page.goto(BASE+'/auth', wait_until='domcontentloaded')
        page.locator('[name="email"]').fill(credentials['farmer_email'])
        page.locator('[name="password"]').fill(credentials['password'])
        page.locator('form[action^="/auth"] button[type="submit"]').click()
        page.wait_for_url('**/homepage')
        passed('Farmer login', 'Homepage reached')
        page.screenshot(path=str(OUT/'browser-homepage.png'), full_page=True)
        assert page.locator('link[href*="style.css"]').count() > 0
        passed('Stylesheets', page.evaluate('document.styleSheets.length'))
        for route in ['/farmer/recommendations','/farmer/agronomic-logs','/farmer/settings','/scan/new']:
            response = page.goto(BASE+route, wait_until='domcontentloaded')
            assert response.status == 200
            passed('Farmer route '+route, response.status)
        page.set_viewport_size({'width':390,'height':844})
        page.goto(BASE+'/homepage', wait_until='domcontentloaded')
        page.screenshot(path=str(OUT/'browser-mobile.png'), full_page=True, animations='disabled')
        passed('Mobile homepage renders', '390x844 viewport screenshot')
        page.goto(BASE+'/logout', wait_until='domcontentloaded')
        page.goto(BASE+'/homepage', wait_until='domcontentloaded')
        assert '/auth' in page.url
        passed('Logout', 'Protected homepage redirects to login')
        page.set_viewport_size({'width':1280,'height':900})
        if fresh:
            page.goto(BASE+'/admin-setup', wait_until='domcontentloaded')
            for name,value in {'username':credentials['admin_username'],'email':credentials['admin_email'],
                               'password':credentials['password'],'confirm_password':credentials['password']}.items():
                page.locator(f'[name="{name}"]').fill(value)
            page.locator('form[action="/admin-setup"] button[type="submit"]').click()
            page.wait_for_url('**/admin')
            passed('First administrator setup', 'Admin dashboard reached')
        else:
            page.goto(BASE+'/superadmin-login', wait_until='domcontentloaded')
            page.locator('[name="identifier"]').fill(credentials['admin_username'])
            page.locator('[name="password"]').fill(credentials['password'])
            page.locator('form[action="/superadmin-login"] button[type="submit"]').click()
            page.wait_for_url('**/superadmin')
        page.goto(BASE+'/admin/farmers', wait_until='domcontentloaded')
        form = page.locator('form.create-farmer-panel')
        for name,value in {'fullname':'Browser Managed Farmer', 'email':f'managed-{secrets.token_hex(4)}@example.invalid',
                           'phone':'09123456789', 'password':credentials['password']}.items():
            form.locator(f'[name="{name}"]').fill(value)
        form.locator('button[type="submit"]').click()
        page.wait_for_url('**/admin/farmers?message=*')
        assert 'Browser Managed Farmer' in page.locator('body').inner_text()
        passed('Admin creates farmer with browser CSRF', 'New farmer visible in list')
        page.goto(BASE+'/superadmin', wait_until='domcontentloaded')
        page.screenshot(path=str(OUT/'browser-superadmin.png'), full_page=True)
        passed('Superadmin dashboard', page.title())
    except Exception as exc:
        evidence['checks'].append({'name':'Browser flow', 'status':'FAIL', 'detail':str(exc)})
        page.screenshot(path=str(OUT/'browser-failure.png'), full_page=True)
        raise
    finally:
        (OUT/'browser-results.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps(evidence, indent=2))
        browser.close()
