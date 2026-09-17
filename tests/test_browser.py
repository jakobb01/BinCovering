"""Opt-in real browser check: BINCOVERING_BROWSER=1 pytest tests/test_browser.py."""

import os
import re
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BINCOVERING_BROWSER") != "1", reason="opt-in browser validation"
)


def test_browser_experiment_compare_export_and_mobile(tmp_path):
    from playwright.sync_api import expect, sync_playwright
    from werkzeug.serving import make_server

    from bincovering.web.app import create_app

    app = create_app(tmp_path / "outputs")
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    screenshots = Path(os.environ.get("BINCOVERING_SCREENSHOTS", str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.get_by_label("Items", exact=True).fill("40")
            page.get_by_label("Trials", exact=True).fill("2")
            page.get_by_label("Workers", exact=True).fill("2")
            page.get_by_role("button", name="Run experiment", exact=True).click()
            expect(page.locator("#runs tr")).to_have_count(1, timeout=15000)
            expect(page.locator("#runs tr").first).to_contain_text(
                "completed", timeout=15000
            )
            page.get_by_role("button", name="Run experiment", exact=True).click()
            expect(page.locator("#runs tr")).to_have_count(2, timeout=15000)
            expect(page.locator("#runs tr").first).to_contain_text(
                "completed", timeout=15000
            )
            for checkbox in page.locator("#runs input[type=checkbox]").all():
                checkbox.check()
            page.get_by_role("button", name="Compare selected").click()
            expect(page.locator("#comparison-note")).to_contain_text(
                "matching trial inputs"
            )
            page.get_by_role("button", name="Plot", exact=True).first.click()
            expect(page.locator("#figure")).to_be_visible()
            page.wait_for_function(
                'document.querySelector("#figure").complete && document.querySelector("#figure").naturalWidth>0'
            )
            page.get_by_role("button", name="Pin", exact=True).first.click()
            expect(page.get_by_role("button", name="Unpin", exact=True)).to_have_count(
                1
            )
            with page.expect_download() as download:
                page.get_by_role("link", name="Export", exact=True).first.click()
            download.value.save_as(str(tmp_path / "export.zip"))
            expect(page.locator(".run-group")).to_have_count(1)
            page.get_by_label("Search experiments").fill("basline")
            expect(page.locator("#runs tr")).to_have_count(2)
            page.get_by_label("Search experiments").fill("nothingmatches")
            expect(page.locator("#runs tr")).to_have_count(0)
            page.get_by_label("Search experiments").fill("")
            expect(page.locator("#runs input:checked")).to_have_count(2)
            page.get_by_role("button", name="Remove", exact=True).click()
            expect(page.locator("#runs tr")).to_have_count(1)
            page.get_by_role("button", name="Undo", exact=True).click()
            expect(page.locator("#runs tr")).to_have_count(2)
            page.get_by_label("Name", exact=True).fill("ordering-study")
            page.get_by_label("Item order", exact=True).select_option("descending")
            page.get_by_role("button", name="Run experiment", exact=True).click()
            expect(page.locator(".run-group")).to_have_count(2, timeout=15000)
            new_group = page.locator(".run-group").filter(
                has=page.locator("summary", has_text="ordering-study")
            )
            new_group.locator("summary").click()
            expect(new_group).to_contain_text("completed", timeout=15000)
            for checkbox in page.locator("#runs input[type=checkbox]").all():
                checkbox.check()
            page.get_by_role("button", name="DNF / ordering plots", exact=True).click()
            expect(page.locator("#figure")).to_have_attribute(
                "src", re.compile("/api/comparison-figure/"), timeout=15000
            )
            expect(page.locator("#figure")).to_be_visible()
            page.wait_for_function(
                'document.querySelector("#figure").complete && document.querySelector("#figure").naturalWidth>0'
            )
            assert page.locator("#runs").bounding_box()["height"] <= 421
            page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )
            expect(
                page.get_by_role("button", name="Inspect", exact=True).first
            ).to_be_visible()
            page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
            assert errors == []
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        for process in app.extensions["bincovering_jobs"].values():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
