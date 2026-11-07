import pytest

from app.drivers.macos import UnsafeAction, WindowBounds, assert_safe, map_click
from PIL import Image

from app.engines.controls import click_missed, click_point, control_allowed, next_control, next_scroll, picture_moved


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


def test_a_closing_frame_does_not_repeat_the_same_screenshot():
    from app.engines.visual import _append_new_shot

    trace = [{"image": "step_08.png", "action": "scroll"}]
    _append_new_shot(trace, {"image": "step_08.png", "action": "wait"})
    assert len(trace) == 1
    _append_new_shot(trace, {"image": "step_09.png", "action": "wait"})
    assert [item["image"] for item in trace] == ["step_08.png", "step_09.png"]
