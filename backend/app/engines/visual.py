import json
import time
from pathlib import Path

from app.drivers.macos import MacOSDriver, UnsafeAction, WindowBounds, assert_safe, map_click
from app.engines.controls import (
    click_missed,
    click_point,
    control_key,
    draw_control_grid,
    next_control,
    next_scroll,
    picture_moved,
)
from app.engines.learning import needs_click
from app.models import Capability, Project
from app.providers.base import ProviderError
from app.providers.hcompany import HCompanyProvider
from app.store import Store
from app.util import new_id

MAX_CLICKS = 12
MAX_SCROLLS = 3


async def explore_visually(
    store: Store,
    project: Project,
    reasoner: HCompanyProvider,
    folder: Path,
    driver: MacOSDriver | None = None,
    documents: str = "",
) -> list[dict]:
    driver = driver or MacOSDriver()
    folder.mkdir(parents=True, exist_ok=True)
    bounds = driver.focus(project.software_name)
    trace: list[dict] = []
    visited: set[str] = set()
    clicks = 0
    looks = 0
    shot = 1
    scroll_counts = {"down": 0, "up": 0}
    scroll_stalled: set[str] = set()
    image_path, width, height = _capture(driver, bounds, folder, shot)
    skip_clicks = await _documents_match_screen(store, project, reasoner, documents, image_path, width, height, trace)
    while not skip_clicks and clicks < MAX_CLICKS and looks < MAX_CLICKS + MAX_SCROLLS * 2 + 4:
        looks += 1
        marked = _marked(folder, image_path)
        controls, more = await reasoner.list_controls(
            software=project.software_name,
            objective=project.learning_objective,
            image_bytes=marked.read_bytes(),
            already=sorted(visited),
        )
        labels = ", ".join(str(item["label"]) for item in controls) or "none"
        store.log(project.id, "exploring", f"H Company ({reasoner.model}) sees: {labels}")
        target = next_control(controls, visited)
        if target is None:
            direction = next_scroll(more, scroll_counts, scroll_stalled, MAX_SCROLLS)
            if direction is None:
                _append_new_shot(
                    trace,
                    _frame(shot, image_path, width, height, reasoner.model, thought=f"No untried controls remain. H Company sees: {labels}"),
                )
                store.log(project.id, "exploring", "Every control H Company can see has been tried.")
                break
            shot, image_path, width, height, bounds = _scroll_and_look(
                driver, project, bounds, folder, shot, image_path, direction, scroll_counts, scroll_stalled, trace, store, reasoner.model
            )
            continue
        label = str(target["label"]).strip()
        visited.add(control_key(label))
        seen_w, seen_h = width, height
        px, py = click_point(int(target["cell"]), int(target["x"]), int(target["y"]), seen_w, seen_h)
        entry = _frame(
            shot,
            image_path,
            width,
            height,
            reasoner.model,
            action="click",
            x=px,
            y=py,
            text=label,
        )
        try:
            assert_safe({"action": "click", "text": label})
            _press(driver, bounds, px, py, seen_w, seen_h)
            entry["executed"] = True
        except UnsafeAction as exc:
            entry["thought"] = f"{reasoner.model} chose {label}. Rejected: {exc}"
            trace.append(entry)
            store.log(project.id, "exploring", entry["thought"])
            continue
        time.sleep(0.9)
        bounds = driver.bounds(project.software_name) or bounds
        shot += 1
        after_path, width, height = _capture(driver, bounds, folder, shot)
        learned = await reasoner.describe_click(
            software=project.software_name,
            label=label,
            before=image_path.read_bytes(),
            after=after_path.read_bytes(),
        )
        if click_missed(learned):
            fixed = await reasoner.correct_point(
                software=project.software_name,
                label=label,
                image_bytes=marked.read_bytes(),
            )
            px, py = click_point(int(fixed["cell"]), int(fixed["x"]), int(fixed["y"]), seen_w, seen_h)
            entry["x"], entry["y"] = px, py
            try:
                _press(driver, bounds, px, py, seen_w, seen_h)
            except UnsafeAction as exc:
                learned = f"没点中. {exc}"
            else:
                time.sleep(0.9)
                bounds = driver.bounds(project.software_name) or bounds
                shot += 1
                after_path, width, height = _capture(driver, bounds, folder, shot)
                learned = await reasoner.describe_click(
                    software=project.software_name,
                    label=label,
                    before=image_path.read_bytes(),
                    after=after_path.read_bytes(),
                )
        entry["learned"] = learned
        entry["thought"] = f"{reasoner.model} clicked {label}. {learned}"
        trace.append(entry)
        if learned and not click_missed(learned):
            _remember(store, project, entry)
        clicks += 1
        store.log(project.id, "exploring", entry["thought"][:220])
        image_path = after_path
    else:
        if not skip_clicks:
            _append_new_shot(
                trace,
                _frame(
                    shot,
                    image_path,
                    width,
                    height,
                    reasoner.model,
                    thought=f"Stopped after {clicks} controls so the run stays bounded.",
                ),
            )
    summary = (
        f"Opened {project.software_name}. The screen matches the documents, so nothing was clicked."
        if skip_clicks
        else f"{reasoner.model} looked at {project.software_name} and clicked {clicks} controls"
    )
    (folder / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
    store.add_evidence(
        project.id,
        origin=project.software_name,
        kind="action_trace",
        summary=summary,
        payload={"steps": len(trace), "clicks": clicks, "model": reasoner.model, "controls": sorted(visited)},
        artifact_path=str(folder / "trace.json"),
    )
    return trace


async def _documents_match_screen(
    store: Store,
    project: Project,
    reasoner: HCompanyProvider,
    documents: str,
    image_path: Path,
    width: int,
    height: int,
    trace: list[dict],
) -> bool:
    if not documents.strip():
        store.log(project.id, "exploring", f"Opened {project.software_name}. There are no documents to compare, so the agent will click.")
        return False
    try:
        verdict = await reasoner.compare_with_documents(
            software=project.software_name,
            objective=project.learning_objective,
            image_bytes=image_path.read_bytes(),
            documents=documents,
        )
    except ProviderError as exc:
        store.log(project.id, "exploring", f"Could not compare the screen with the documents ({exc}). Clicking instead.")
        return False
    matches = bool(verdict.get("matches"))
    complete = bool(verdict.get("complete"))
    note = str(verdict.get("note") or "").strip()
    store.log(
        project.id,
        "exploring",
        f"Opened {project.software_name}. Documents match the screen: {matches}. Documents complete: {complete}. {note[:160]}",
    )
    if needs_click(matches, complete):
        store.log(project.id, "exploring", "The documents do not match the live app, or they leave something out. Clicking to learn the rest.")
        return False
    trace.append(
        _frame(
            1,
            image_path,
            width,
            height,
            reasoner.model,
            thought=f"The live app matches the documents, and the documents cover this screen. {note}"[:500],
        )
    )
    return True


def _scroll_and_look(
    driver: MacOSDriver,
    project: Project,
    bounds: WindowBounds,
    folder: Path,
    shot: int,
    image_path: Path,
    direction: str,
    counts: dict[str, int],
    stalled: set[str],
    trace: list[dict],
    store: Store,
    model: str,
) -> tuple[int, Path, int, int, WindowBounds]:
    bounds = driver.bounds(project.software_name) or bounds
    driver.scroll(bounds, direction)
    time.sleep(0.55)
    shot += 1
    after_path, width, height = _capture(driver, bounds, folder, shot)
    counts[direction] = counts.get(direction, 0) + 1
    if picture_moved(image_path, after_path):
        thought = f"Scrolled {direction} to see controls that were off screen."
    else:
        stalled.add(direction)
        thought = f"Scrolled {direction}. This edge of the page does not move any further."
    trace.append(
        _frame(
            shot,
            after_path,
            width,
            height,
            model,
            action="scroll",
            text=direction,
            thought=thought,
        )
    )
    store.log(project.id, "exploring", thought)
    return shot, after_path, width, height, bounds


def _append_new_shot(trace: list[dict], entry: dict) -> None:
    if trace and trace[-1].get("image") == entry["image"]:
        return
    trace.append(entry)


def _capture(driver: MacOSDriver, bounds: WindowBounds, folder: Path, shot: int) -> tuple[Path, int, int]:
    return driver.capture(bounds, folder / f"step_{shot:02d}.png")


def _marked(folder: Path, image_path: Path) -> Path:
    dest = folder / f"{image_path.stem}_grid.png"
    draw_control_grid(image_path, dest)
    return dest


def _press(driver: MacOSDriver, bounds: WindowBounds, x: int, y: int, width: int, height: int) -> None:
    screen_x, screen_y = map_click(x, y, width, height, bounds)
    driver.click(screen_x, screen_y)


def _frame(
    shot: int,
    image_path: Path,
    width: int,
    height: int,
    model: str,
    *,
    action: str = "wait",
    x: int = 0,
    y: int = 0,
    text: str = "",
    thought: str = "",
) -> dict:
    return {
        "step": shot,
        "action": action,
        "x": x,
        "y": y,
        "text": text,
        "thought": thought,
        "learned": "",
        "image": image_path.name,
        "image_width": width,
        "image_height": height,
        "executed": action != "click",
        "model": model,
    }


def _remember(store: Store, project: Project, entry: dict) -> None:
    store.db.add(
        Capability(
            id=new_id("capability"),
            project_id=project.id,
            name=entry["text"][:200] or entry["learned"][:200],
            description=entry["learned"][:2000] or entry["thought"],
            preconditions_json="[]",
            inputs_json=json.dumps([entry["action"]]),
            expected_outputs_json="[]",
            related_claims_json="[]",
            verification_status="experimented",
            confidence=0.55,
        )
    )
    store.db.commit()
