import pytest

from app.drivers.macos import UnsafeAction, WindowBounds, assert_safe, map_click
from PIL import Image

from app.engines.controls import click_missed, click_point, control_allowed, next_control, next_scroll, picture_moved, should_click


def test_click_maps_from_screenshot_pixels_into_the_window():
    bounds = WindowBounds(100, 200, 800, 600)
    screen_x, screen_y = map_click(640, 240, 1280, 960, bounds)
    assert screen_x == 500
    assert screen_y == 350


def test_click_outside_the_window_is_rejected():
    bounds = WindowBounds(0, 0, 100, 100)
    with pytest.raises(UnsafeAction):
        map_click(120, 10, 100, 100, bounds)


def test_destructive_text_is_rejected():
    with pytest.raises(UnsafeAction):
        assert_safe({"action": "type", "text": "delete all files"})


def test_navigation_key_is_allowed():
    assert_safe({"action": "key", "text": "escape"})


def test_normalized_coordinates_land_on_the_control():
    x, y = click_point(23, 865, 137, 1440, 744)
    assert x == int(865 / 1000 * 1439)
    assert y == int(137 / 1000 * 743)
    assert 1200 < x < 1320
    assert 80 < y < 120


def test_viewport_zoom_is_not_mistaken_for_window_zoom():
    assert control_allowed("Zoom In")
    assert control_allowed("Zoom Out")
    assert not control_allowed("Window Zoom")


def test_out_of_range_normalized_points_are_rejected():
    with pytest.raises(UnsafeAction):
        click_point(1, 1200, 500, 1440, 900)


def test_scroll_looks_below_the_fold_and_then_above_it():
    assert next_scroll("none", {"down": 0, "up": 0}, set()) == "down"
    assert next_scroll("up", {"down": 0, "up": 0}, set()) == "up"
    assert next_scroll("down", {"down": 3, "up": 0}, set(), limit=3) == "up"
    assert next_scroll("down", {"down": 1, "up": 0}, {"down"}) == "up"
    assert next_scroll("none", {"down": 3, "up": 3}, set(), limit=3) is None


def test_a_real_scroll_changes_the_picture(tmp_path):
    before = tmp_path / "before.png"
    same = tmp_path / "same.png"
    shifted = tmp_path / "shifted.png"
    Image.new("RGB", (200, 120), (10, 10, 10)).save(before)
    Image.new("RGB", (200, 120), (12, 12, 12)).save(same)
    moved = Image.new("RGB", (200, 120), (10, 10, 10))
    for x in range(200):
        for y in range(40, 80):
            moved.putpixel((x, y), (230, 230, 230))
    moved.save(shifted)
    assert not picture_moved(before, same)
    assert picture_moved(before, shifted)


def test_window_chrome_and_destructive_controls_are_skipped():
    controls = [
        {"label": "关闭", "cell": 1, "x": 10, "y": 10},
        {"label": "控制", "cell": 11, "x": 800, "y": 80},
        {"label": "删除", "cell": 12, "x": 900, "y": 80},
    ]
    chosen = next_control(controls, set())
    assert chosen["label"] == "控制"
    assert next_control(controls, {"控制"}) is None
    assert control_allowed("编辑文稿")
    assert click_missed("没点中，界面没有变化")
    assert not click_missed("打开了控制面板")


def test_detailed_options_are_not_clicked_but_the_opener_is():
    controls = [
        {"label": "Mandarin Chinese", "role": "detail", "documented": False},
        {"label": "Recognition language", "role": "opener", "documented": False},
    ]
    chosen = next_control(controls, set(), covered_docs=True)
    assert chosen["label"] == "Recognition language"
    assert not should_click(controls[0], covered_docs=True)


def test_documented_controls_are_left_to_the_article():
    controls = [
        {"label": "Save", "role": "action", "documented": True},
        {"label": "Script library", "role": "action", "documented": False},
    ]
    assert next_control(controls, set(), covered_docs=True)["label"] == "Script library"
    assert next_control(controls, set(), covered_docs=False)["label"] == "Save"


@pytest.mark.parametrize("role", ["opener", "action"])
def test_open_options_are_closed_before_the_next_top_level_click(tmp_path, monkeypatch, role):
    import asyncio
    from types import SimpleNamespace
    from app.engines import visual

    class Driver:
        menu_open = True
        clicks = 0
        def focus(self, name): return WindowBounds(0, 0, 200, 120)
        def bounds(self, name): return WindowBounds(0, 0, 200, 120)
        def key(self, key): self.menu_open = False
        def capture(self, bounds, path):
            Image.new("RGB", (200, 120), "white").save(path)
            return path, 200, 120
        def click(self, x, y):
            assert not self.menu_open, "A prior menu must not intercept the next click"
            self.clicks += 1
            self.menu_open = True
        def scroll(self, bounds, direction): pass

    driver = Driver()
    class Reasoner:
        model = "test-model"
        async def list_controls(self, **kwargs):
            return [{"label": label, "cell": 1, "x": 200, "y": 200, "role": role, "documented": False} for label in ["Alpha", "Beta"]], "none"
        async def describe_click(self, **kwargs): return "Opened the options menu."
    store = SimpleNamespace(log=lambda *args: None, add_evidence=lambda *args, **kwargs: None)
    monkeypatch.setattr(visual, "_remember", lambda *args: None)
    monkeypatch.setattr(visual.time, "sleep", lambda seconds: None)
    trace = asyncio.run(visual.explore_visually(store, SimpleNamespace(id="test", software_name="Test", learning_objective="learn"), Reasoner(), tmp_path, driver=driver))
    assert driver.clicks == 2
    assert not driver.menu_open
    assert [f["text"] for f in trace if f["action"] == "click"] == ["Alpha", "Beta"]


def test_capture_rejects_a_different_foreground_app(tmp_path, monkeypatch):
    from app.drivers import macos
    monkeypatch.setattr(macos, "_osascript", lambda script: "Google Chrome")
    with pytest.raises(macos.VisualExploreError, match="foreground"):
        macos.MacOSDriver().capture(WindowBounds(0, 0, 200, 120, app_name="Blender"), tmp_path / "wrong.png")


def test_driver_selects_and_raises_largest_application_window(monkeypatch):
    from app.drivers import macos
    scripts = []
    def run(script):
        scripts.append(script)
        return "0,33,1512,949"
    monkeypatch.setattr(macos, "_osascript", run)
    bounds = macos.MacOSDriver().bounds("Blender")
    assert bounds is not None
    assert bounds.width == 1512
    assert "repeat with candidate in windows" in scripts[0]
    assert 'perform action "AXRaise"' in scripts[0]


def test_grid_badges_are_not_application_controls():
    assert not control_allowed("12")
    assert not control_allowed("72")
    assert control_allowed("3D Viewport")


def test_relevant_excerpts_keep_article_paragraphs():
    from app.engines.visual import _relevant_excerpts
    documents = "[source_a] Manual\nIntro\n\nDocumented final control.\n\n[source_b] Other product\nExclude this."
    selected = _relevant_excerpts(documents, [{"id": "source_a", "relevant": True}])
    assert "Documented final control" in selected
    assert "Exclude this" not in selected


def test_a_closing_frame_does_not_repeat_the_same_screenshot():
    from app.engines.visual import _append_new_shot

    trace = [{"image": "step_08.png", "action": "scroll"}]
    _append_new_shot(trace, {"image": "step_08.png", "action": "wait"})
    assert len(trace) == 1
    _append_new_shot(trace, {"image": "step_09.png", "action": "wait"})
    assert [item["image"] for item in trace] == ["step_08.png", "step_09.png"]
