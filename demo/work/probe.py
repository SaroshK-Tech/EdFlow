"""Verify the demo pages render real content for the recording session."""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8020"
urls = [
    "/", "/students/", "/students/1/", "/timetable/", "/attendance/", "/fees/",
    "/finance/", "/finance/expenses/", "/payroll/", "/staff/", "/staff/1/",
    "/parents/", "/hardware/", "/hardware/maintenance/", "/communication/",
    "/notifications/my/", "/reports/",
]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto(BASE + "/accounts/login/?next=/", wait_until="networkidle")
    pg.fill("#id_username", "admin")
    pg.fill("#id_password", "admin123")
    pg.click('button[type="submit"]')
    pg.wait_for_load_state("networkidle")
    bad_words = ["page not found", "login", "traceback", "permission denied"]
    for u in urls:
        pg.goto(BASE + u, wait_until="networkidle")
        t = pg.title()
        body = pg.locator("body").inner_text().lower()
        hits = [k for k in bad_words if k in body]
        summary = body[:100].replace("\n", " | ")
        print(f"{u:30} title={t[:30]!r:34} bad={hits if hits else 'none'}")
        print(f"   body: {summary}")
    b.close()
print("PROBE DONE")