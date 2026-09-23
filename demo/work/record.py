"""Record per-scene screencasts of the EdFlow demo using Playwright.

Produces one .webm per scene under demo/work/clips/<key>.webm at 1280x720,
headless, with gentle scroll/hover motion so the final video feels alive.

Pre-requisite: demo server running on http://127.0.0.1:8020 with
project.settings.demo and demo.sqlite3 (see demo_seed + runserver).
"""

import json
import math
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8020"
ROOT = Path(__file__).resolve().parent.parent
CLIPS = ROOT / "work" / "clips"
CLIPS.mkdir(parents=True, exist_ok=True)

VIEWPORT = {"width": 1280, "height": 720}

MOTION = [(520, 2000), (340, 2000), (-240, 1500), (200, 1400), (-160, 900)]

SCENES = [
    {"key": "dashboard", "url": "/", "wait": 1000, "scrolls": [(420, 1800), (260, 1700), (-200, 1300), (160, 1200), (-120, 900)]},
    {"key": "students", "url": "/students/", "wait": 500, "scrolls": MOTION},
    {"key": "student_detail", "url": "/students/1/", "wait": 700, "scrolls": MOTION},
    {"key": "timetable", "url": "/timetable/", "wait": 1000, "scrolls": MOTION},
    {"key": "attendance", "url": "/attendance/", "wait": 500, "scrolls": [(380, 1700), (240, 1600), (-180, 1200), (160, 1100), (-140, 900)]},
    {"key": "fees", "url": "/fees/", "wait": 500, "scrolls": MOTION},
    {"key": "finance", "url": "/finance/", "wait": 800, "scrolls": MOTION},
    {"key": "payroll", "url": "/payroll/", "wait": 500, "scrolls": [(360, 1600), (260, 1500), (-180, 1100), (140, 1000), (-140, 800)]},
    {"key": "payroll_run", "url": None, "wait": 900, "scrolls": MOTION, "from_nav": True, "hover": ["table a[href*='payslip']"]},
    {"key": "staff", "url": "/staff/", "wait": 500, "scrolls": MOTION},
    {"key": "staff_detail", "url": "/staff/1/", "wait": 600, "scrolls": MOTION, "hover": ["a[href*='id-card']"]},
    {"key": "parents", "url": "/parents/", "wait": 500, "scrolls": MOTION},
    {"key": "hardware", "url": "/hardware/", "wait": 700, "scrolls": MOTION},
    {"key": "maintenance", "url": "/hardware/maintenance/", "wait": 500, "scrolls": MOTION},
    {"key": "communication", "url": "/communication/", "wait": 800, "scrolls": MOTION},
    {"key": "notifications", "url": "/notifications/my/", "wait": 500, "scrolls": [(300, 1400), (240, 1300), (-180, 1000), (160, 900), (-140, 800)]},
    {"key": "reports", "url": "/reports/", "wait": 800, "scrolls": MOTION, "hover": ["a[href*='export']"]},
]


def smooth_scroll(page, delta, duration_ms):
    steps = 30
    per = delta / steps
    pause = duration_ms / steps
    for _ in range(steps):
        page.mouse.wheel(0, per)
        page.wait_for_timeout(pause)


def login_once(browser):
    """Log in once and return the cookie/session state to reuse for every scene."""
    ctx = browser.new_context(viewport=VIEWPORT)
    page = ctx.new_page()
    page.goto(f"{BASE}/accounts/login/?next=/", wait_until="networkidle")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "admin123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    state = ctx.storage_state()
    page.close()
    ctx.close()
    return state


def run_scene(browser, scene, base, storage_state):
    key = scene["key"]
    ctx = browser.new_context(
        viewport=VIEWPORT,
        record_video_dir=str(CLIPS),
        record_video_size=VIEWPORT,
        storage_state=storage_state,
    )
    page = ctx.new_page()
    errors = []
    try:
        if scene.get("from_nav"):
            # navigate via sidebar to payroll run detail
            page.goto(f"{base}/payroll/", wait_until="networkidle")
            first = page.locator("table a[href*='/payroll/']").first
            if first.count():
                first.click()
                page.wait_for_load_state("networkidle")
        else:
            page.goto(f"{base}{scene['url']}", wait_until="networkidle")

        page.wait_for_timeout(scene["wait"])
        for sel in scene.get("hover", []):
            try:
                loc = page.locator(sel)
                if loc.count():
                    loc.first.scroll_into_view_if_needed()
                    loc.first.hover()
                    page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001
                pass
        for delta, dur in scene["scrolls"]:
            smooth_scroll(page, delta, dur)
        page.wait_for_timeout(900)

        # hold the final frame a moment longer for a natural tail
        page.wait_for_timeout(700)

        vpath = page.video.path() if page.video else None
        page.close()
        ctx.close()
        target = None
        if vpath and Path(vpath).exists():
            target = CLIPS / f"{key}.webm"
            if target.exists():
                target.unlink()
            Path(vpath).rename(target)
        return {"key": key, "ok": not errors, "errors": errors, "video": str(target) if target else None}
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
        try:
            page.close()
            ctx.close()
        except Exception:
            pass
        return {"key": key, "ok": False, "errors": errors, "video": None}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        print("logging in once...")
        storage_state = login_once(browser)
        report = []
        for scene in SCENES:
            started = time.time()
            res = run_scene(browser, scene, BASE, storage_state)
            took = round(time.time() - started, 1)
            res["seconds"] = took
            report.append(res)
            print(f"{res['key']}: ok={res['ok']} video={res['video']} ({took}s)")
        browser.close()
    (ROOT / "work" / "record_report.json").write_text(json.dumps(report, indent=2))
    print("DONE")


if __name__ == "__main__":
    main()