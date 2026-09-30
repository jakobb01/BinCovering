"""Opt-in real registration and account-management browser workflow."""

import os
import re
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BINCOVERING_BROWSER") != "1", reason="opt-in browser validation"
)


def test_registration_accounts_actions_and_mobile(tmp_path):
    from playwright.sync_api import expect, sync_playwright
    from werkzeug.serving import make_server

    from bincovering.web.app import create_app

    # This workflow exercises sessions, database writes and the real UI; it never
    # launches an experiment or preview, so no execution queue is needed.
    app = create_app(tmp_path / "outputs", execution_queue=object())
    store = app.extensions["bincovering_store"]
    administrator = store.create_user("browser_admin", "browser-admin-password", "admin")
    disabled = store.create_user("disabled_researcher", "disabled-account-password")
    store.change_user(disabled["id"], active=False)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    screenshots = Path(os.environ.get("BINCOVERING_SCREENSHOTS", str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000},
                base_url=f"http://127.0.0.1:{server.server_port}",
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("/login?next=/builder")
            sign_in = page.get_by_role("button", name="Sign in", exact=True)
            assert sign_in.evaluate("node => getComputedStyle(node).backgroundColor") == "rgb(180, 60, 0)"
            assert sign_in.bounding_box()["height"] >= 44
            page.screenshot(path=str(screenshots / "login-updated-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(screenshots / "login-updated-390.png"), full_page=True)
            page.get_by_role("link", name="Create account", exact=True).click()
            expect(page).to_have_url(re.compile(r"/register\?next=/builder$"))
            expect(page.get_by_role("combobox")).to_have_count(0)
            username = "browser_researcher_with_a_long_account_name"
            password = "registered-researcher-password"
            page.get_by_label("Account name", exact=True).fill(username)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_label("Confirm password", exact=True).fill("different-password")
            page.get_by_role("button", name="Create account", exact=True).click()
            expect(page.locator("#register-error")).to_contain_text("must match")
            expect(page.get_by_label("Account name", exact=True)).to_have_value(username)
            expect(page.get_by_label("Password", exact=True)).to_have_value("")
            expect(page.get_by_label("Confirm password", exact=True)).to_have_value("")
            assert not any(user["username"] == username for user in store.users())
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(screenshots / "registration-error-390.png"), full_page=True)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_label("Confirm password", exact=True).fill(password)
            page.screenshot(path=str(screenshots / "registration-updated-390.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.screenshot(path=str(screenshots / "registration-updated-desktop.png"), full_page=True)
            page.get_by_role("button", name="Create account", exact=True).click()
            expect(page).to_have_url(re.compile(r"/builder$"))
            expect(page.locator("#draft-status")).not_to_have_text("Loading…")
            registered = page.request.get("/api/session").json()["user"]
            assert registered["role"] == "user" and registered["active"]
            assert "password_hash" not in registered
            assert page.request.get("/api/admin/users").status == 403
            expect(page.get_by_role("link", name="Accounts", exact=True)).to_have_count(0)
            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.locator("#account-name")).to_have_attribute("title", username)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            name_box = page.locator("#account-name").bounding_box()
            logout_box = page.locator("#logout").bounding_box()
            assert abs(name_box["y"] + name_box["height"] / 2 - logout_box["y"] - logout_box["height"] / 2) <= 1
            page.screenshot(path=str(screenshots / "shared-header-researcher-390.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.get_by_role("button", name="Save draft", exact=True).click()
            expect(page.locator("#draft-status")).to_have_text("Saved draft")
            assert len(page.request.get("/api/builder/library").json()["items"]) == 1
            page.get_by_role("button", name="Log out", exact=True).click()
            expect(page).to_have_url(re.compile(r"/login$"))

            page.goto("/login?next=/admin")
            page.get_by_label("Account name", exact=True).fill("browser_admin")
            page.get_by_label("Password", exact=True).fill("browser-admin-password")
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#account-count")).to_have_text("3 accounts")
            # Follow every real menu link and compare the visible header geometry
            # across pages on desktop and phone viewports.
            pages = [("Dashboard", "home"), ("Saved experiments", "experiments"), ("Builder", "builder"), ("Accounts", "admin")]
            for width, height in [(1440, 1000), (390, 844)]:
                page.set_viewport_size({"width": width, "height": height})
                headers = []
                heading_sizes = []
                for label, slug in pages:
                    menu = page.get_by_role("navigation", name="Main navigation", exact=True)
                    menu.get_by_role("link", name=label, exact=True).click()
                    expect(menu.locator('[aria-current="page"]')).to_have_text(label)
                    expect(menu.get_by_role("link", name="Accounts", exact=True)).to_have_count(1)
                    expect(page.locator(".workspace-label a")).to_have_count(0)
                    expect(page.locator(".brand")).to_have_text("BinCovering")
                    expect(page.locator(".brand svg, .brand .accent-mark")).to_have_count(0)
                    if slug == "builder":
                        expect(page.locator("#draft-status")).not_to_have_text("Loading…")
                        expect(page.locator("#builder-page-title")).to_have_text("Build your algorithm.")
                        page.get_by_role("tab", name="Item generators", exact=True).click()
                        expect(page.locator("#builder-page-title")).to_have_text("Build your generator.")
                        expect(page.locator("#builder-page-title .accent-mark")).to_have_text(".")
                        page.get_by_role("tab", name="Algorithms", exact=True).click()
                    if slug == "admin":
                        expect(page.locator("#account-count")).to_have_text("3 accounts")
                    geometry = page.locator(".site-bar").evaluate("""node => {
                        const brand = node.querySelector('.brand'), nav = node.querySelector('nav');
                        const b = brand.getBoundingClientRect(), n = nav.getBoundingClientRect();
                        return {brandX:b.x, brandY:b.y, brandSize:getComputedStyle(brand).fontSize,
                          navX:n.x, navY:n.y, navWidth:n.width, height:node.getBoundingClientRect().height};
                    }""")
                    assert abs(geometry["navX"] + geometry["navWidth"] / 2 - width / 2) <= 1
                    headers.append(geometry)
                    if slug != "home":
                        heading_sizes.append(page.locator("main h1").evaluate("node => getComputedStyle(node).fontSize"))
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    page.screenshot(path=str(screenshots / f"shared-header-{slug}-{width}.png"), full_page=True)
                assert all(header == headers[0] for header in headers)
                assert heading_sizes == ["36px" if width > 600 else "30px"] * 3
            page.set_viewport_size({"width": 1440, "height": 1000})
            expect(page.locator(".account-row")).to_have_count(3)
            row = page.locator(".account-row").filter(has=page.get_by_role("heading", name=username, exact=True))
            expect(row.locator(".account-role")).to_have_text("Researcher")
            expect(row.locator(".account-status")).to_have_text("Active")
            expect(row.locator(".account-created")).to_contain_text("Joined")
            disabled_row = page.locator(".account-row").filter(has=page.get_by_role("heading", name="disabled_researcher", exact=True))
            expect(disabled_row.locator(".account-status")).to_have_text("Disabled")
            expect(page.get_by_role("button", name="Reassign experiment", exact=True)).to_be_disabled()
            for button in page.locator(".account-actions button").all():
                assert button.bounding_box()["height"] >= 44
                assert button.evaluate("node => getComputedStyle(node).borderRadius") == "8px"
            page.screenshot(path=str(screenshots / "accounts-updated-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(screenshots / "accounts-updated-390.png"), full_page=True)
            row.get_by_role("button", name=f"Disable {username}", exact=True).click()
            expect(row.locator(".account-status")).to_have_text("Disabled")
            expect(row.get_by_role("button", name=f"Enable {username}", exact=True)).to_be_focused()
            row.get_by_role("button", name=f"Enable {username}", exact=True).click()
            expect(row.locator(".account-status")).to_have_text("Active")
            reset = row.get_by_role("button", name=f"Reset password for {username}", exact=True)
            reset.click()
            expect(row.get_by_label(f"New password for {username}", exact=True)).to_be_focused()
            expect(row.get_by_role("button", name="Save password", exact=True)).to_have_class("button button-accent")
            row.get_by_role("button", name="Cancel", exact=True).click()
            expect(reset).to_be_focused()
            expect(reset).to_have_attribute("aria-expanded", "false")
            reset.click()
            new_password = "researcher-reset-password"
            row.get_by_label(f"New password for {username}", exact=True).fill(new_password)
            row.get_by_role("button", name="Save password", exact=True).click()
            expect(page.locator("#account-feedback")).to_have_text(f"Password changed for {username}.")
            expect(reset).to_be_focused()
            assert store.authenticate(username, password) is None
            assert store.authenticate(username, new_password)["id"] == registered["id"]
            create = page.locator("#create-account")
            create.get_by_label("Account name", exact=True).fill("admin_created_researcher")
            create.get_by_label("Initial password", exact=True).fill("admin-created-password")
            create.get_by_role("button", name="Create account", exact=True).click()
            expect(page.locator("#account-count")).to_have_text("4 accounts")
            expect(page.locator(".account-row")).to_have_count(4)
            admin_rows = page.request.get("/api/admin/users").json()["users"]
            assert {user["id"] for user in admin_rows} == {user["id"] for user in store.users()}
            assert all("password_hash" not in user for user in admin_rows)
            page.evaluate("id => localStorage.setItem(`bincovering:builder:${id}:algorithm`, 'private draft')", administrator["id"])
            page.get_by_role("button", name="Log out", exact=True).click()
            expect(page).to_have_url(re.compile(r"/login$"))
            assert page.evaluate("id => localStorage.getItem(`bincovering:builder:${id}:algorithm`)", administrator["id"]) is None
            page.get_by_label("Account name", exact=True).fill(username)
            page.get_by_label("Password", exact=True).fill(new_password)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page).to_have_url(re.compile(r"/$"))
            assert page.request.get("/api/admin/users").status == 403
            assert len(page.request.get("/api/builder/library").json()["items"]) == 1
            assert errors == []
            browser.close()
    finally:
        server.shutdown()
