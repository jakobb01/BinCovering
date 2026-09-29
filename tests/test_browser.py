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
            expect(page.locator("#runs .recent-run")).to_have_count(1, timeout=15000)
            expect(page.locator("#runs .recent-run").first).to_contain_text(
                "completed", timeout=15000
            )
            page.get_by_role("button", name="Run experiment", exact=True).click()
            expect(page.locator("#runs .recent-run")).to_have_count(2, timeout=15000)
            expect(page.locator("#runs .recent-run").first).to_contain_text(
                "completed", timeout=15000
            )
            page.screenshot(path=str(screenshots / "home.png"), full_page=True)
            expect(page.locator("#run-search")).to_have_count(0)
            page.get_by_role("link", name="Saved experiments", exact=True).click()
            expect(page).to_have_url(re.compile("/experiments$"))
            expect(page.locator("#experiment")).to_have_count(0)
            expect(page.locator("#runs tbody tr")).to_have_count(2, timeout=15000)
            for checkbox in page.locator("#runs input[type=checkbox]").all():
                checkbox.check()
            page.get_by_role("button", name="Compare selected").click()
            expect(page.locator("#comparison-note")).to_contain_text(
                "matching trial inputs"
            )
            expect(page.locator("#results")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.get_by_role("button", name="Compare selected")).to_be_focused()
            plot_button = page.get_by_role("button", name="Plot", exact=True).first
            plot_button.scroll_into_view_if_needed()
            page_scroll = page.evaluate("window.scrollY")
            history_scroll = page.locator("#runs").evaluate("node => node.scrollTop")
            plot_button.click()
            expect(page.locator("#figure")).to_be_visible()
            page.wait_for_function(
                'document.querySelector("#figure").complete && document.querySelector("#figure").naturalWidth>0'
            )
            expect(page.locator("#plot-kind")).to_have_value("overview")
            expect(page.locator("#plot-algorithm option").nth(1)).to_contain_text("k=5")
            expect(page.locator("#figure-svg")).to_have_attribute(
                "href", re.compile("format=svg")
            )
            page.get_by_role("button", name="Zoom to full size").click()
            expect(page.locator("#figure-stage")).to_have_class(
                "figure-stage is-zoomed"
            )
            page.get_by_role("button", name="Fit to view").click()
            page.locator("#plot-panel").select_option("outcomes")
            expect(page.locator("#figure")).to_be_visible(timeout=15000)
            # A slow older response must not overwrite the newer chosen plot.
            deferred = []

            def delay_mass(route):
                if route.request.post_data_json.get("kind") == "mass":
                    deferred.append(route)
                else:
                    route.continue_()

            page.route("**/api/plot/**", delay_mass)
            with page.expect_request(
                lambda request: (
                    "/api/plot/" in request.url
                    and request.post_data_json.get("kind") == "mass"
                )
            ):
                page.locator("#plot-kind").select_option("mass")
            expect(page.locator("#viewer-status")).to_have_text("Generating plot…")
            expect(page.locator("#algorithm-control")).to_be_hidden()
            page.locator("#plot-kind").select_option("overview")
            expect(page.locator("#figure")).to_be_visible(timeout=15000)
            newest_src = page.locator("#figure").get_attribute("src")
            assert len(deferred) == 1
            deferred[0].fulfill(
                status=400,
                content_type="application/json",
                body='{"error":"This stale response must be ignored"}',
            )
            expect(page.locator("#viewer-status")).to_have_text("")
            expect(page.locator("#figure")).to_have_attribute("src", newest_src)
            page.unroute("**/api/plot/**", delay_mass)
            page.get_by_role("tab", name="Summary", exact=True).focus()
            page.keyboard.press("ArrowRight")
            expect(
                page.get_by_role("tab", name="Settings and provenance")
            ).to_be_focused()
            expect(page.locator("#panel-provenance")).to_be_visible()
            page.keyboard.press("Home")
            expect(page.get_by_role("tab", name="Plot", exact=True)).to_be_focused()
            page.locator("#plot-kind").select_option("reliability")
            expect(page.locator("#target-results")).to_contain_text(
                "70%", timeout=15000
            )
            expect(page.locator("#figure")).to_be_visible(timeout=15000)
            page.screenshot(path=str(screenshots / "coverage-target.png"))
            page.locator("#target-results > summary").click()
            expect(page.locator("#target-results table")).to_be_visible()
            page.screenshot(path=str(screenshots / "coverage-target-table.png"))
            page.locator("#coverage-target").fill("100")
            page.locator("#coverage-target").press("Tab")
            expect(page.locator("#target-results")).to_contain_text(
                "100%", timeout=15000
            )
            expect(page.locator("#target-control")).to_be_visible()
            expect(page.locator("#target-results")).to_have_attribute("open", "")
            page.locator("#plot-kind").select_option("paired")
            expect(page.locator("#figure")).to_be_visible(timeout=15000)
            expect(page.locator("#target-control")).to_be_hidden()
            expect(page.locator("#figure")).to_have_attribute("alt", re.compile("DNF"))
            page.screenshot(path=str(screenshots / "paired.png"))
            page.keyboard.press("Escape")
            expect(plot_button).to_be_focused()
            assert abs(page.evaluate("window.scrollY") - page_scroll) <= 1
            assert (
                page.locator("#runs").evaluate("node => node.scrollTop")
                == history_scroll
            )
            page.locator(".row-menu > summary").first.click()
            page.get_by_role("button", name="Pin", exact=True).first.click()
            expect(page.get_by_role("button", name="Unpin", exact=True)).to_have_count(
                1
            )
            expect(page.get_by_role("button", name="Unpin", exact=True)).to_be_focused()
            menu_title = page.locator(".row-menu > summary").first
            menu_title.focus()
            page.keyboard.press("Escape")
            expect(page.locator(".row-menu").first).not_to_have_attribute("open", "")
            expect(menu_title).to_be_focused()
            page.keyboard.press("Enter")
            expect(page.get_by_role("button", name="Unpin", exact=True)).to_be_visible()
            with page.expect_response(
                lambda response: response.url.endswith("/api/runs")
            ):
                menu_title.focus()
            expect(menu_title).to_be_focused()
            with page.expect_download() as download:
                page.get_by_role("link", name="Export", exact=True).first.click()
            download.value.save_as(str(tmp_path / "export.zip"))
            expect(page.locator(".run-group")).to_have_count(1)
            expect(page.locator("#history-count")).to_contain_text(
                "2 of 2 experiments · 1 groups"
            )
            expect(page.locator("#figure-link")).to_have_attribute("target", "_blank")
            page.get_by_label("Search experiments").fill("basline")
            expect(page.locator("#runs tbody tr")).to_have_count(2)
            page.get_by_label("Search experiments").fill("shuffle 40")
            expect(page.locator("#runs tbody tr")).to_have_count(2)
            page.get_by_label("Search experiments").fill("swaps 100")
            expect(page.locator("#runs tbody tr")).to_have_count(0)
            page.get_by_label("Search experiments").fill("n>=40 trials:2")
            expect(page.locator("#runs tbody tr")).to_have_count(2)
            page.get_by_label("Search experiments").fill("nothingmatches")
            expect(page.locator("#runs tbody tr")).to_have_count(0)
            page.get_by_label("Search experiments").fill("")
            expect(page.locator("#runs input:checked")).to_have_count(2)
            page.locator(".row-menu > summary").nth(1).click()
            page.get_by_role("button", name="Remove", exact=True).click()
            expect(page.locator("#runs tbody tr")).to_have_count(1)
            page.get_by_role("button", name="Undo", exact=True).click()
            expect(page.locator("#runs tbody tr")).to_have_count(2)
            page.get_by_role("link", name="Dashboard", exact=True).click()
            expect(page.locator("#experiment")).to_be_visible()
            page.get_by_label("Name", exact=True).fill("ordering-study")
            page.get_by_label("Items", exact=True).fill("40")
            page.get_by_label("Trials", exact=True).fill("2")
            page.get_by_label("Workers", exact=True).fill("2")
            page.get_by_label("Item order", exact=True).select_option("descending")
            page.get_by_role("button", name="Run experiment", exact=True).click()
            expect(page.locator("#runs .recent-run")).to_have_count(3, timeout=15000)
            page.get_by_role("link", name="Saved experiments", exact=True).click()
            expect(page.locator(".run-group")).to_have_count(2, timeout=15000)
            new_group = page.locator(".run-group").filter(
                has=page.locator("summary", has_text="ordering-study")
            )
            new_group.locator(":scope > summary").click()
            expect(new_group).to_contain_text("completed", timeout=15000)
            for group in page.locator(".run-group").all():
                if group.get_attribute("open") is None:
                    group.locator(":scope > summary").click()
            for checkbox in page.locator("#runs input[type=checkbox]").all():
                checkbox.check()
            page.get_by_role("button", name="Study plots", exact=True).click()
            expect(page.locator("#figure")).to_have_attribute(
                "src", re.compile("/api/comparison-figure/"), timeout=15000
            )
            expect(page.locator("#figure")).to_be_visible()
            page.wait_for_function(
                'document.querySelector("#figure").complete && document.querySelector("#figure").naturalWidth>0'
            )
            assert page.locator("#runs").evaluate(
                "node => getComputedStyle(node).maxHeight === 'none' && getComputedStyle(node).overflowY === 'visible'"
            )
            page.screenshot(
                path=str(screenshots / "desktop-viewer.png"), full_page=True
            )
            page.keyboard.press("Escape")
            # Exercise a real crowded study, entirely inside the temporary test root.
            from bincovering.experiments.runner import run_experiment

            for seed in range(6):
                run_experiment(
                    {
                        "name": "baseline",
                        "n": 8,
                        "trials": 1,
                        "seed": seed,
                        "output_root": str(tmp_path / "outputs"),
                        "algorithms": [{"id": "dual_next_fit"}],
                    }
                )
            expect(page.locator("#runs tbody tr")).to_have_count(9, timeout=15000)
            crowded_group = page.locator(".run-group").filter(
                has=page.locator("summary .group-name", has_text="baseline")
            )
            expect(crowded_group.locator("tbody tr")).to_have_count(8)
            assert page.locator("#runs").bounding_box()["height"] > 420
            page.evaluate("window.scrollTo(0, 0)")
            assert page.locator("#runs tbody tr").first.bounding_box()["y"] < 500
            for width in (320, 390, 600, 768, 1024, 1280, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                )
                assert (
                    page.get_by_role(
                        "button", name="Plot", exact=True
                    ).first.bounding_box()["height"]
                    >= 40
                )
                actions = page.locator(".row-actions").first
                assert actions.evaluate(
                    "node => [...node.children].every(child => Math.abs(child.getBoundingClientRect().top - node.firstElementChild.getBoundingClientRect().top) <= 1)"
                )
            page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
            last_menu = page.locator(".row-menu > summary").last
            history_height = page.locator("#runs").bounding_box()["height"]
            last_menu.click()
            assert page.locator("#runs").bounding_box()["height"] == history_height
            expect(
                page.locator(".row-menu").last.locator(".action-list")
            ).to_be_visible()
            page.screenshot(path=str(screenshots / "history-menu.png"), full_page=True)
            page.keyboard.press("Escape")
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )
            expect(
                page.get_by_role("button", name="Inspect", exact=True).first
            ).to_be_visible()
            page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
            page.get_by_role("button", name="Plot", exact=True).first.click()
            expect(page.locator("#figure")).to_be_visible(timeout=15000)
            assert page.locator("#results").evaluate(
                "node => node.scrollWidth <= node.clientWidth"
            )
            page.screenshot(path=str(screenshots / "mobile-viewer.png"))
            page.locator("#plot-kind").select_option("reliability")
            expect(page.locator("#figure")).to_be_visible(timeout=15000)
            if page.locator("#target-results").get_attribute("open") is not None:
                page.locator("#target-results > summary").click()
            page.screenshot(path=str(screenshots / "mobile-target.png"))
            page.keyboard.press("Escape")
            assert errors == []
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        for process in app.extensions["bincovering_jobs"].values():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
