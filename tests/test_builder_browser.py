"""Real C workspace workflows; the root verifier runs these after integration.

Set BINCOVERING_BROWSER=1. BINCOVERING_BUILDER_URL can point the browser at a
separately running host server so Chromium in a test container does not need the
container engine socket. Credentials are an ephemeral test account, provided as
BINCOVERING_BUILDER_USERNAME and BINCOVERING_BUILDER_PASSWORD.
"""

import os
import re
import threading
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BINCOVERING_BROWSER") != "1", reason="opt-in real browser workflow"
)


@pytest.fixture
def builder_page(tmp_path):
    from playwright.sync_api import expect, sync_playwright

    external = os.environ.get("BINCOVERING_BUILDER_URL")
    username = os.environ.get("BINCOVERING_BUILDER_USERNAME", "builder_browser")
    password = os.environ.get(
        "BINCOVERING_BUILDER_PASSWORD", "browser-workflow-password"
    )
    server = None
    if not external:
        from werkzeug.serving import make_server

        from bincovering.web.app import create_app

        app = create_app(tmp_path / "outputs")
        app.extensions["bincovering_store"].create_user(username, password)
        server = make_server("127.0.0.1", 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        external = f"http://127.0.0.1:{server.server_port}"
    screenshots = Path(os.environ.get("BINCOVERING_SCREENSHOTS", str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, base_url=external
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(external.rstrip("/") + "/builder")
            page.get_by_label("Account name", exact=True).fill(username)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#draft-status")).not_to_have_text("Loading…")
            yield page, screenshots
            assert errors == []
            browser.close()
    finally:
        if server:
            server.shutdown()


def test_builder_removal_notations_connections_recovery_and_mobile(builder_page):
    from playwright.sync_api import expect

    page, screenshots = builder_page
    page.locator("#builder-starter").select_option("online")
    expect(page.locator(".graph-node[data-type=component]")).to_have_count(1)
    page.get_by_role("button", name="Open graph", exact=True).click()
    custom = page.locator(".graph-node[data-type=custom]")
    expect(custom.get_by_role("button", name="Remove", exact=True)).to_be_visible()
    custom.get_by_role("button", name="Remove", exact=True).click()
    expect(custom).to_have_count(0)
    expect(page.locator("#builder-feedback")).to_contain_text("affected connection")
    page.get_by_role("button", name="Undo", exact=True).click()
    expect(custom).to_have_count(1)
    expect(page.locator(".graph-edge")).to_have_count(1)
    custom.get_by_role("button", name="Inspect Close the covered bin").click()
    original = page.locator("#custom-source").input_value()
    page.get_by_label("Notation", exact=True).select_option("pseudocode")
    expect(page.locator("#custom-source")).to_have_value("COVER active_bin")
    page.get_by_label("Notation", exact=True).select_option("python")
    expect(page.locator("#custom-source")).to_have_value(original)
    page.locator("#custom-source").fill("if ???")
    page.locator("#inspector-title").click()
    page.get_by_label("Notation", exact=True).select_option("pseudocode")
    expect(page.locator("#builder-feedback")).to_contain_text(
        "original draft is preserved"
    )
    expect(page.locator("#custom-source")).to_have_value("if ???")
    expect(page.get_by_label("Notation", exact=True)).to_have_value("python")
    page.get_by_role("button", name="Undo", exact=True).click()
    expect(page.locator("#custom-source")).to_have_value(original)
    page.reload()
    expect(
        page.get_by_role("button", name="Return to parent graph", exact=True)
    ).to_be_visible()
    expect(page.locator("#custom-source")).to_have_value(original)
    page.get_by_role("button", name="Return to parent graph", exact=True).click()
    expect(page.locator("#preview-items")).to_have_value(
        "0.35, 0.75, 0.40, 0.65, 0.20, 0.30"
    )
    # Keyboard removal/addition use the real graph and recover wiring with Undo.
    page.locator(".palette-component[data-type=custom]").get_by_role(
        "button", name="Add", exact=True
    ).click()
    added = page.locator(".graph-node[data-type=custom]")
    expect(added).to_have_count(1)
    added.locator(".node-title").click()
    page.locator("#canvas-viewport").focus()
    page.keyboard.press("Delete")
    expect(added).to_have_count(0)
    page.get_by_role("button", name="Undo", exact=True).click()
    expect(added).to_have_count(1)
    page.get_by_role("button", name="Redo", exact=True).click()
    expect(added).to_have_count(0)
    page.locator("#builder-name").fill("Browser draft recovery")
    page.locator("#inspector-title").click()
    page.reload()
    expect(page.locator("#builder-name")).to_have_value("Browser draft recovery")
    expect(page.locator("#builder-feedback")).to_contain_text(
        "Recovered your unsaved draft"
    )
    page.screenshot(path=str(screenshots / "builder-c-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Fit", exact=True).click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(screenshots / "builder-c-390.png"), full_page=True)
    page.get_by_role("button", name="Save draft", exact=True).click()
    expect(page.locator("#draft-status")).to_have_text("Saved draft")
    page.get_by_role("button", name="Saved library", exact=True).click()
    card = page.locator(".library-card").filter(has_text="Browser draft recovery").first
    expect(card).to_be_visible()
    card.get_by_role("button", name="Archive", exact=True).click()
    expect(page.locator("#library-feedback")).to_contain_text("Definition archived")
    page.get_by_role("button", name="Undo archive", exact=True).click()
    expect(
        page.locator(".library-card").filter(has_text="Browser draft recovery").first
    ).to_be_visible()
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Log out", exact=True).click()
    expect(page).to_have_url(re.compile(r"/login(?:\?.*)?$"))
    assert (
        page.evaluate(
            "Object.keys(localStorage).filter(k=>k.startsWith('bincovering:builder:')).length"
        )
        == 0
    )


@pytest.mark.skipif(
    os.environ.get("BINCOVERING_BUILDER_ISOLATION") != "1",
    reason="requires isolated previews",
)
def test_real_palette_drag_node_move_typed_wiring_and_component_execution(builder_page):
    from playwright.sync_api import expect

    page, screenshots = builder_page
    page.locator("#builder-starter").select_option("component")
    viewport = page.locator("#canvas-viewport")
    page.locator('.palette-component[data-type="assign"]').drag_to(
        viewport, target_position={"x": 290, "y": 260}
    )
    assign = page.locator('.graph-node[data-type="assign"]')
    expect(assign).to_have_count(1)
    initial = assign.evaluate(
        "n => [parseFloat(n.style.left), parseFloat(n.style.top)]"
    )
    title = assign.locator(".node-title")
    title.scroll_into_view_if_needed()
    box = title.bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 15)
    page.mouse.down()
    page.mouse.move(box["x"] + 100, box["y"] + 60, steps=8)
    page.mouse.up()
    moved = assign.evaluate("n => [parseFloat(n.style.left), parseFloat(n.style.top)]")
    assert moved[0] > initial[0] + 40 and moved[1] > initial[1] + 30
    title.click()
    page.get_by_label("State variable", exact=True).fill("produced")
    page.locator("#inspector-title").click()
    page.get_by_label("Expression", exact=True).fill("incoming * 2")
    page.locator("#inspector-title").click()
    page.get_by_text("Typed data ports", exact=True).click()
    page.get_by_label("Outputs (JSON)", exact=True).fill('{"value":{"type":"number"}}')
    page.locator("#inspector-title").click()
    page.locator('.graph-node[data-id="scale"] .node-title').click()
    page.locator("#custom-source").fill("value = transferred * factor")
    page.locator("#inspector-title").click()
    page.get_by_text("Typed data ports", exact=True).click()
    page.get_by_label("Inputs (JSON)", exact=True).fill(
        '{"transferred":{"type":"number"}}'
    )
    page.locator("#inspector-title").click()

    # Choose labelled sockets with the same interactions available to a keyboard.
    def socket(label):
        control = page.get_by_role("button", name=label, exact=True)
        control.scroll_into_view_if_needed()
        control.click()

    socket("Component input output control socket next")
    socket("Set state input control socket in")
    socket("Set state output control socket next")
    socket("Scale value input control socket in")
    page.get_by_role("button", name="Value connections", exact=True).click()
    socket("Set state output data socket value type number")
    socket("Scale value input data socket transferred type number")
    expect(page.locator(".graph-edge.data")).to_have_count(1)
    # Arrow movement and its Undo retain the selected node and labelled focus.
    title.click()
    before_key = assign.evaluate("n => parseFloat(n.style.left)")
    page.keyboard.press("ArrowRight")
    assert assign.evaluate("n => parseFloat(n.style.left)") == before_key + 10
    expect(assign.locator(".node-title")).to_be_focused()
    page.keyboard.press("Control+z")
    assert assign.evaluate("n => parseFloat(n.style.left)") == before_key
    page.locator("#preview-component-values").fill('{"incoming":0.25}')
    page.get_by_role("button", name="Run preview", exact=True).click()
    expect(page.locator("#preview-status")).to_contain_text(
        "Preview completed", timeout=120000
    )
    expect(page.locator("#preview-trace .trace-output")).to_contain_text('"value": 0.5')
    page.screenshot(
        path=str(screenshots / "builder-typed-component.png"), full_page=True
    )


@pytest.mark.skipif(
    os.environ.get("BINCOVERING_BUILDER_ISOLATION") != "1",
    reason="requires the actual rootless Podman builder image",
)
def test_builder_isolated_preview_publish_paired_run_and_frozen_trace(builder_page):
    from playwright.sync_api import expect

    page, screenshots = builder_page
    page.locator("#builder-starter").select_option("online")
    algorithm_name = "Browser traced algorithm " + uuid.uuid4().hex[:8]
    generator_name = "Browser seeded generator " + uuid.uuid4().hex[:8]
    run_name = "Browser frozen paired study " + uuid.uuid4().hex[:8]
    page.locator("#builder-name").fill(algorithm_name)
    page.locator("#inspector-title").click()
    page.get_by_role("button", name="Run preview", exact=True).click()
    expect(page.locator("#preview-status")).to_contain_text(
        "Preview completed", timeout=120000
    )
    expect(page.locator("#preview-trace .trace-events li")).not_to_have_count(0)
    expect(page.locator("#available")).to_be_enabled()
    page.get_by_role("button", name="Step operation", exact=True).click()
    expect(page.locator("#preview-trace .trace-position")).to_contain_text("Event 2")
    page.get_by_role("button", name="Previous", exact=True).click()
    expect(page.locator("#preview-trace .trace-position")).to_contain_text("Event 1")
    page.get_by_role("button", name="Make available", exact=True).click()
    expect(page.locator("#draft-status")).to_contain_text("Available revision")
    algorithm = page.request.get("/api/builder/available").json()["algorithms"]
    algorithm = next(x for x in algorithm if x["name"] == algorithm_name)
    page.screenshot(path=str(screenshots / "builder-real-preview.png"), full_page=True)
    page.get_by_role("tab", name="Item generators", exact=True).click()
    page.locator("#builder-starter").select_option("generator")
    page.locator("#builder-name").fill(generator_name)
    page.locator("#inspector-title").click()
    page.get_by_role("button", name="Run preview", exact=True).click()
    expect(page.locator("#preview-status")).to_contain_text(
        "Preview completed", timeout=120000
    )
    page.get_by_role("button", name="Make available", exact=True).click()
    expect(page.locator("#draft-status")).to_contain_text("Available revision")
    generator = page.request.get("/api/builder/available").json()["generators"]
    generator = next(x for x in generator if x["name"] == generator_name)
    page.get_by_role("link", name="Dashboard", exact=True).click()
    page.get_by_label("Items", exact=True).fill("6")
    page.get_by_label("Trials", exact=True).fill("1")
    page.get_by_label("Name", exact=True).fill(run_name)
    page.locator('input[name=algorithm][value="dual_harmonic"]').uncheck()
    page.locator(
        f'input[name=algorithm][value="{algorithm["id"]}@{algorithm["revision"]}"]'
    ).check()
    page.locator("select[name=generator]").select_option(
        generator["id"] + "@" + generator["revision"]
    )
    page.locator("select[name=ordering]").select_option("original")
    page.get_by_text("Record execution traces", exact=True).click()
    page.locator("input[name=capture_trace]").check()
    page.locator("input[name=trace_trials]").fill("0")
    page.get_by_role("button", name="Run experiment", exact=True).click()
    recent = page.locator(".recent-run").filter(has_text=run_name).first
    expect(recent).to_contain_text("completed", timeout=120000)
    recent.get_by_role("button", name="Inspect", exact=True).click()
    page.get_by_role("tab", name="Trace", exact=True).click()
    expect(page.locator("#trace-algorithm option")).to_have_count(3)
    page.locator("#trace-algorithm").select_option(
        label=f"{algorithm_name} · revision {algorithm['revision']}"
    )
    expect(page.locator("#saved-trace-view .trace-events li")).not_to_have_count(0)
    expect(page.locator("#saved-trace-status")).to_contain_text("exact frozen graph")
    page.screenshot(path=str(screenshots / "saved-builder-trace.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(
        path=str(screenshots / "saved-builder-trace-390.png"), full_page=True
    )
    page.keyboard.press("Escape")
    page.goto(page.url.split("?", 1)[0].rstrip("/") + "/builder?id=" + algorithm["id"])
    page.get_by_role("button", name="Open graph", exact=True).click()
    page.locator(".graph-node[data-type=custom] .node-title").click()
    page.locator("#custom-source").fill("cover(active_bin)\nchanged = 1")
    page.locator("#inspector-title").click()
    page.get_by_role("button", name="Return to parent graph", exact=True).click()
    page.get_by_role("button", name="Save draft", exact=True).click()
    frozen = page.request.get(
        f"/api/builder/library/{algorithm['id']}?revision={algorithm['revision']}"
    ).json()["frozen"]
    assert "changed = 1" not in str(frozen["graph"])
    # Editing a real decision changes measured results and recorded branch paths.
    page.locator('.graph-node[data-id="check"] .node-title').click()
    page.get_by_label("Expression", exact=True).fill("False")
    page.locator("#inspector-title").click()
    expect(page.locator("#available")).to_be_disabled()
    page.get_by_role("button", name="Run preview", exact=True).click()
    expect(page.locator("#preview-status")).to_contain_text(
        "Preview completed", timeout=120000
    )
    expect(page.locator("#preview-trace .trace-output")).to_contain_text(
        '"covered_bins": 0'
    )
    expect(
        page.locator("#preview-trace .trace-event").filter(has_text="Bin covered? → no")
    ).to_have_count(6)
    assert (
        page.request.get(
            f"/api/builder/library/{algorithm['id']}?revision={algorithm['revision']}"
        ).json()["frozen"]
        == frozen
    )


def test_c_layout_mode_drafts_pan_and_drag_connections(builder_page):
    """Exercise the corrected C canvas using real pointer and keyboard events."""
    from playwright.sync_api import expect

    page, screenshots = builder_page
    canvas = page.locator("#canvas-viewport")
    stage = page.locator("#canvas-world > .builder-world")
    expect(page.locator("#builder-domain, #builder-threshold")).to_have_count(0)
    expect(page.get_by_role("tab", name="Algorithms", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator(".palette-component[data-type=emit]")).to_have_count(0)
    expect(page.locator(".palette-component[data-type=place]")).to_be_visible()
    assert page.locator("#builder-starter option").evaluate_all(
        "nodes => nodes.map(n => n.value)"
    ) == ["", "online", "offline", "component"]
    assert canvas.evaluate("n => getComputedStyle(n).overflow") == "hidden"
    assert canvas.evaluate("n => n.clientHeight") > 450
    assert canvas.evaluate(
        "n => Math.abs(n.getBoundingClientRect().bottom - document.querySelector('.canvas-footer').getBoundingClientRect().top) < 2"
    )
    expect(page.locator(".node-data-ports")).to_have_count(0)
    page.screenshot(
        path=str(screenshots / "builder-c-corrected-desktop.png"), full_page=True
    )
    # The entire background, including the lower part, is pannable. No native scroll.
    canvas.scroll_into_view_if_needed()
    area = canvas.bounding_box()
    before = stage.evaluate("n => new DOMMatrix(getComputedStyle(n).transform).m42")
    page.mouse.move(area["x"] + 12, area["y"] + area["height"] - 16)
    page.mouse.down()
    page.mouse.move(area["x"] + 42, area["y"] + area["height"] - 96, steps=8)
    page.mouse.up()
    assert (
        abs(
            stage.evaluate("n => new DOMMatrix(getComputedStyle(n).transform).m42")
            - before
            + 80
        )
        < 1
    )
    assert canvas.evaluate("n => [n.scrollLeft, n.scrollTop]") == [0, 0]
    page.mouse.move(area["x"] + 12, area["y"] + area["height"] - 16)
    before = stage.evaluate("n => new DOMMatrix(getComputedStyle(n).transform).m42")
    page.mouse.wheel(0, 90)
    page.wait_for_function(
        "before => new DOMMatrix(getComputedStyle(document.querySelector('#canvas-world > .builder-world')).transform).m42 < before - 50",
        arg=before,
    )
    assert canvas.evaluate("n => [n.scrollLeft, n.scrollTop]") == [0, 0]
    page.get_by_role("button", name="Fit", exact=True).click()
    source = page.get_by_role(
        "button", name="Place current item output control socket next", exact=True
    )
    target = page.get_by_role(
        "button", name="Bin covered? input control socket in", exact=True
    )
    a, b = source.bounding_box(), target.bounding_box()
    source_circle = source.evaluate(
        "n => [getComputedStyle(n, '::before').width, getComputedStyle(n, '::before').borderRadius]"
    )
    assert source_circle == ["18px", "50%"]
    page.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
    page.mouse.down()
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=10)
    expect(page.locator(".connection-preview")).to_have_count(1)
    expect(target).to_have_class(re.compile(r"connect-target"))
    page.mouse.up()
    expect(page.locator(".connection-preview")).to_have_count(0)
    expect(page.locator("#builder-feedback")).to_contain_text("Connection added")
    expect(page.locator(".graph-edge")).to_have_count(5)
    # Lines attach to circle centres after zoom and pan, irrespective of offset parents.
    assert page.evaluate("""() => {
      const source = document.querySelector('.graph-node[data-id=place] [data-kind=control][data-direction=output]');
      const target = document.querySelector('.graph-node[data-id=check] [data-kind=control][data-direction=input]');
      const edge = [...document.querySelectorAll('.graph-edge')].find(e => e.getAttribute('aria-label').includes('from Place current item to Bin covered?'));
      const matrix = edge.getScreenCTM();
      const first = edge.getPointAtLength(0).matrixTransform(matrix), last = edge.getPointAtLength(edge.getTotalLength()).matrixTransform(matrix);
      return [[first, source], [last, target]].every(([point, element]) => {
        const r = element.getBoundingClientRect();
        return Math.abs(point.x - r.left - r.width / 2) < 1 && Math.abs(point.y - r.top - r.height / 2) < 1;
      });
    }""")
    page.locator("#builder-name").fill("Algorithm tab draft")
    page.get_by_role("tab", name="Item generators", exact=True).click()
    expect(page.locator("#builder-page-title")).to_have_text("Build your generator.")
    assert page.locator("#builder-starter option").evaluate_all(
        "nodes => nodes.map(n => n.value)"
    ) == ["", "generator", "component"]
    expect(page.locator(".palette-component[data-type=place]")).to_have_count(0)
    expect(page.locator(".palette-component[data-type=emit]")).to_be_visible()
    page.locator("#builder-name").fill("Generator tab draft")
    page.get_by_role("tab", name="Algorithms", exact=True).click()
    expect(page.locator("#builder-name")).to_have_value("Algorithm tab draft")
    page.reload()
    expect(page.locator("#builder-name")).to_have_value("Algorithm tab draft")
    page.get_by_role("tab", name="Algorithms", exact=True).focus()
    page.keyboard.press("ArrowRight")
    expect(page.get_by_role("tab", name="Item generators", exact=True)).to_be_focused()
    expect(page.locator("#builder-name")).to_have_value("Generator tab draft")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#builder-name")).to_have_value("Algorithm tab draft")
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Fit", exact=True).click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert canvas.evaluate("n => n.clientHeight") == 520
    assert canvas.evaluate("n => getComputedStyle(n).overflow") == "hidden"
    page.screenshot(
        path=str(screenshots / "builder-c-corrected-390.png"), full_page=True
    )


@pytest.mark.skipif(
    os.environ.get("BINCOVERING_BUILDER_ISOLATION") != "1",
    reason="requires actual isolated verification",
)
def test_verify_workspace_mandatory_trace_and_stable_playback(builder_page):
    from playwright.sync_api import expect

    page, screenshots = builder_page
    expect(page.locator("#preview-limit")).to_have_count(0)
    assert page.locator(".builder-preview").evaluate(
        "n => n.parentElement === document.querySelector('main') && !document.querySelector('#builder-workspace').contains(n)"
    )
    assert page.locator("#run-preview").evaluate(
        "n => getComputedStyle(n).backgroundColor === 'rgb(180, 60, 0)' && getComputedStyle(n).color === 'rgb(255, 255, 255)'"
    )
    for selector in ("#save-draft", "#available"):
        assert page.locator(selector).evaluate(
            "n => getComputedStyle(n).borderTopColor === 'rgb(180, 60, 0)'"
        )
    page.locator("#builder-name").fill(
        "Browser stable verification " + uuid.uuid4().hex[:8]
    )
    page.locator("#inspector-title").click()
    with page.expect_response(
        re.compile(r"/api/builder/library/[^/]+/preview$")
    ) as submitted:
        page.get_by_role("button", name="Run preview", exact=True).click()
    job_id = submitted.value.json()["id"]
    expect(page.locator("#preview-status")).to_contain_text(
        "Preview completed", timeout=120000
    )
    trace = page.request.get("/api/builder/jobs/" + job_id).json()["result"]["trace"]
    events = trace["events"]
    assert trace["event_limit"] == 10000
    assert trace["byte_limit"] == 4 * 1024 * 1024
    assert not trace["truncated"] and len(events) == trace["total_events"]
    canvas = page.locator("#preview-trace .trace-graph-mini")
    assert canvas.evaluate("n => n.clientHeight") == 600
    assert canvas.evaluate("n => getComputedStyle(n).overflow") == "hidden"
    expect(page.locator("#phase-tabs [data-phase=next]")).to_have_attribute(
        "aria-selected", "true"
    )
    page.evaluate(
        "window._verifyEditor = document.querySelector('#canvas-world .graph-node')"
    )
    editor_transform = page.locator("#canvas-world > .builder-world").evaluate(
        "n => n.style.transform"
    )
    controls = page.locator("#preview-trace .trace-playback")
    controls.evaluate("n => n.scrollIntoView({block:'start'})")
    scroll = page.evaluate("scrollY")
    for _ in range(16):
        page.get_by_role("button", name="Step operation", exact=True).click()
        assert abs(page.evaluate("scrollY") - scroll) <= 1
        assert page.locator("#preview-trace .trace-graph-mini .graph-node").count() > 0
        assert canvas.evaluate("n => n.clientHeight") == 600
    assert page.evaluate(
        "window._verifyEditor === document.querySelector('#canvas-world .graph-node')"
    )
    assert (
        page.locator("#canvas-world > .builder-world").evaluate(
            "n => n.style.transform"
        )
        == editor_transform
    )
    expect(page.locator("#phase-tabs [data-phase=next]")).to_have_attribute(
        "aria-selected", "true"
    )

    def recorded_step(index):
        page.locator(f'#preview-trace .trace-event[data-event="{index}"]').click()

    place = next(
        i
        for i, e in enumerate(events)
        if e.get("node_id") == "place" and not e.get("call_path")
    )
    check = next(
        i
        for i, e in enumerate(events)
        if i > place and e.get("node_id") == "check" and not e.get("call_path")
    )
    recorded_step(place)
    page.evaluate(
        "window._verifyGraph = document.querySelector('#preview-trace .trace-graph-world')"
    )
    stage = page.locator("#preview-trace .trace-graph-world")
    before = stage.evaluate("n => n.style.transform")
    recorded_step(check)
    assert page.evaluate(
        "window._verifyGraph === document.querySelector('#preview-trace .trace-graph-world')"
    )
    assert stage.evaluate("n => n.style.transform") == before
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    page.mouse.move(box["x"] + box["width"] - 12, box["y"] + box["height"] - 16)
    page.mouse.down()
    page.mouse.move(
        box["x"] + box["width"] - 42, box["y"] + box["height"] - 66, steps=8
    )
    page.mouse.up()
    panned = stage.evaluate("n => n.style.transform")
    assert panned != before
    recorded_step(place)
    assert stage.evaluate("n => n.style.transform") == panned
    assert canvas.evaluate("n => [n.scrollLeft, n.scrollTop]") == [0, 0]
    page.get_by_role("button", name="Fit trace graph", exact=True).click()
    fitted = stage.evaluate("n => n.style.transform")
    nested = next(
        i
        for i, e in enumerate(events)
        if e.get("node_id") == "close" and e.get("call_path")
    )
    recorded_step(nested)
    expect(page.locator("#preview-trace .trace-graph-context")).to_contain_text(
        "Close covered bin"
    )
    expect(
        page.locator("#preview-trace .trace-graph-mini .graph-node[data-type=custom]")
    ).to_have_count(1)
    expect(page.locator("#preview-trace .trace-graph-mini .executing")).to_have_count(1)
    back = next(
        i
        for i, e in enumerate(events)
        if i > nested and e.get("node_id") == "done" and not e.get("call_path")
    )
    recorded_step(back)
    assert stage.evaluate("n => n.style.transform") == fitted
    page.locator(".builder-preview").screenshot(
        path=str(screenshots / "builder-verify-stable-desktop.png")
    )
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Fit trace graph", exact=True).click()
    assert canvas.evaluate("n => n.clientHeight") == 520
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator(".builder-preview").screenshot(
        path=str(screenshots / "builder-verify-stable-390.png")
    )
