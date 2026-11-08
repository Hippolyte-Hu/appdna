import json
import time
from pathlib import Path

from app.drivers.macos import MacOSDriver, UnsafeAction, WindowBounds, assert_safe, map_click
from app.drivers.browser import BrowserDriver
from app.engines.controls import (
    click_missed,
    click_point,
    control_allowed,
    control_key,
    next_control,
    next_scroll,
    picture_moved,
    should_click,
)
from app.engines.outcome import load_source_relevance
from app.engines.learning import needs_click
from app.models import Capability, Project
from app.providers.base import ProviderError
from app.providers.hcompany import HCompanyProvider
from app.store import Store
from app.util import new_id

MAX_CLICKS = 96
MAX_CONTINUATION_CLICKS = 12
MAX_SCROLLS = 3


def make_driver(project):
    url = getattr(project, "target_url", None)
    return BrowserDriver(url) if url else MacOSDriver()


async def explore_visually(store, project, reasoner, folder, driver=None, documents="", source_ids=None, resume=False):
    owned = driver is None
    driver = driver or make_driver(project)
    try:
        return await _explore_visually(store, project, reasoner, folder, driver=driver,
                                      documents=documents, source_ids=source_ids, resume=resume)
    finally:
        if owned and isinstance(driver, BrowserDriver):
            driver.close()


async def _explore_visually(
    store: Store,
    project: Project,
    reasoner: HCompanyProvider,
    folder: Path,
    driver: MacOSDriver | None = None,
    documents: str = "",
    source_ids: list[str] | None = None,
    resume: bool = False,
) -> list[dict]:
    driver = driver or MacOSDriver()
    folder.mkdir(parents=True, exist_ok=True)
    store.log(project.id, "exploring", f"Opening {project.software_name}.")
    bounds = driver.focus(project.software_name)
    driver.key("escape")  # Dismiss an ordinary menu left open by a previous run.
    time.sleep(0.2)
    trace = json.loads((folder / "trace.json").read_text()) if resume else []
    visited = {control_key(step.get("text", "")) for step in trace if _confirmed_click(step)}
    shot = max([0, *(int(path.stem.split("_")[-1]) for path in folder.glob("step_*.png")
                      if path.stem.split("_")[-1].isdigit()), *(int(step.get("step", 0)) for step in trace)]) + 1
    image_path, width, height = _capture(driver, bounds, folder, shot)
    if resume:
        trace.append(_frame(shot, image_path, width, height, reasoner.model, action="resume",
                            thought="Continuing saved exploration. Prior evidence is retained; controls are located again on the current screen."))
        (folder / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
    try:
        return await _click_through(
            store,
            project,
            reasoner,
            driver,
            folder,
            documents,
            list(source_ids or []),
            bounds,
            trace,
            visited,
            image_path,
            width,
            height,
            shot,
            resume=resume,
        )
    finally:
        _persist_trace(store, project, reasoner, folder, trace, visited)


async def _click_through(
    store: Store,
    project: Project,
    reasoner: HCompanyProvider,
    driver: MacOSDriver,
    folder: Path,
    documents: str,
    source_ids: list[str],
    bounds: WindowBounds,
    trace: list[dict],
    visited: set[str],
    image_path: Path,
    width: int,
    height: int,
    shot: int,
    resume: bool = False,
) -> list[dict]:
    clicks = 0
    looks = 0
    list_failures = 0
    inventory = {}
    if resume and (folder / "control_inventory.json").exists():
        inventory = {control_key(item["label"]): item for item in json.loads((folder / "control_inventory.json").read_text())}
    pending_query: list[str] = []
    rechecked: set[tuple[str, ...]] = set()
    routed: set[str] = set()
    scroll_counts = {"down": 0, "up": 0}
    scroll_stalled: set[str] = set()
    saved_relevance = load_source_relevance(folder / "source_relevance.json") if resume else None
    if saved_relevance is not None:
        covered = _relevant_excerpts(documents, saved_relevance.get("sources", []))
        store.log(project.id, "exploring", "Reusing saved product-identity checks and collected documents.")
    else:
        covered = await _documents_match_screen(
            store, project, reasoner, documents, source_ids, folder, image_path, width, height, trace
        )
    _skip_unneeded(store, project, list(inventory.values()), visited, bool(covered))
    click_limit = min(MAX_CLICKS, MAX_CONTINUATION_CLICKS) if resume else MAX_CLICKS
    while clicks < click_limit and looks < click_limit + MAX_SCROLLS * 2 + 4:
        looks += 1
        try:
            controls, more = await reasoner.list_controls(
                software=project.software_name,
                objective=project.learning_objective,
                image_bytes=image_path.read_bytes(),
                already=sorted(visited - {control_key(label) for label in pending_query}),
                covered=covered,
                **({"pending": pending_query} if pending_query else {}),
            )
            if pending_query:
                requested = {control_key(label) for label in pending_query}
                controls = [item for item in controls if control_key(item["label"]) in requested
                            and item.get("role") == "navigation"]
                # A prior navigation click can be revisited to reach unfinished
                # controls, but only after it is freshly located in this screenshot.
                if resume:
                    for item in controls:
                        visited.discard(control_key(item["label"]))
            pending_query = []
        except ProviderError as exc:
            list_failures += 1
            store.log(
                project.id,
                "exploring",
                f"{exc}. Asking again so controls the documents do not mention still get clicked.",
            )
            if list_failures >= 2:
                _append_new_shot(
                    trace,
                    _frame(shot, image_path, width, height, reasoner.model, thought=f"Stopped asking the model. {exc}"),
                )
                break
            continue
        list_failures = 0
        for item in controls:
            inventory.setdefault(control_key(item["label"]), {**item, "first_seen": shot, "requires_click": should_click(item, covered_docs=bool(covered))})
        (folder / "control_inventory.json").write_text(json.dumps(list(inventory.values())), encoding="utf-8")
        labels = ", ".join(str(item["label"]) for item in controls) or "none"
        store.log(project.id, "exploring", f"H Company ({reasoner.model}) sees: {labels}")
        _skip_unneeded(store, project, controls, visited, bool(covered))
        target = next_control(controls, visited, covered_docs=bool(covered))
        if target is None:
            pending_labels = [item["label"] for key, item in inventory.items()
                              if item["requires_click"] and item.get("role") == "navigation" and key not in visited]
            if resume and not pending_labels:
                confirmed = {control_key(step.get("text", "")) for step in trace if _confirmed_click(step)}
                unfinished = any(item["requires_click"] and key not in confirmed for key, item in inventory.items())
                if unfinished:
                    last_seen = {control_key(step.get("text", "")): int(step.get("step", 0))
                                 for step in trace if step.get("action") == "click"}
                    routes = sorted((item for key, item in inventory.items()
                                     if item.get("role") == "navigation" and key not in routed),
                                    key=lambda item: last_seen.get(control_key(item["label"]), 0))
                    if routes:
                        pending_labels = [routes[0]["label"]]
                        routed.add(control_key(pending_labels[0]))
            signature = tuple(sorted(control_key(label) for label in pending_labels))
            if pending_labels and signature not in rechecked:
                rechecked.add(signature)
                pending_query = pending_labels
                store.log(project.id, "exploring", "Rechecking unhandled navigation tabs against the current screenshot; old coordinates will not be replayed.")
                continue
            direction = next_scroll(more, scroll_counts, scroll_stalled, MAX_SCROLLS)
            if direction is None:
                _append_new_shot(
                    trace,
                    _frame(shot, image_path, width, height, reasoner.model, thought=f"No further unhandled control was located in this view. H Company sees: {labels}"),
                )
                store.log(project.id, "exploring", "No further unhandled control was located in this view. Known coverage gaps remain in the report.")
                break
            shot, image_path, width, height, bounds = _scroll_and_look(
                driver, project, bounds, folder, shot, image_path, direction, scroll_counts, scroll_stalled, trace, store, reasoner.model
            )
            continue
        label = str(target["label"]).strip()
        was_confirmed = any(control_key(step.get("text", "")) == control_key(label) and _confirmed_click(step) for step in trace)
        visited.add(control_key(label))
        if target.get("role") == "navigation":
            routed.add(control_key(label))
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
        learned = await _describe(store, project, reasoner, label, image_path.read_bytes(), after_path.read_bytes())
        if click_missed(learned):
            try:
                fixed = await reasoner.correct_point(
                    software=project.software_name,
                    label=label,
                    image_bytes=image_path.read_bytes(),
                )
            except ProviderError as exc:
                store.log(project.id, "exploring", f"{exc}. Leaving {label} as observed.")
                fixed = None
            if fixed:
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
                    learned = await _describe(store, project, reasoner, label, image_path.read_bytes(), after_path.read_bytes())
        entry["learned"] = learned
        entry["thought"] = f"{reasoner.model} clicked {label}. {learned}"
        trace.append(entry)
        if learned and not click_missed(learned) and not was_confirmed:
            _remember(store, project, entry)
        clicks += 1
        if target.get("role") == "navigation" and not click_missed(learned):
            # A new page has its own scroll frontier and visible pending controls.
            scroll_counts = {"down": 0, "up": 0}
            scroll_stalled.clear()
            rechecked.clear()
        # Observe an opener's result, then dismiss its choices before another click.
        # Otherwise a still-open popup can intercept a different top-level target.
        # Do not rely on the model's role classification to close a popup.
        driver.key("escape")
        time.sleep(0.2)
        bounds = driver.bounds(project.software_name) or bounds
        shot += 1
        image_path, width, height = _capture(driver, bounds, folder, shot)
        store.log(project.id, "exploring", "Dismissed transient options without choosing a detailed value.")
        store.log(project.id, "exploring", entry["thought"][:220])
        (folder / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
    else:
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
    clicked_keys = {control_key(step.get("text", "")) for step in trace if step.get("action") == "click" and step.get("executed")}
    confirmed = {control_key(step.get("text", "")) for step in trace if _confirmed_click(step)}
    pending = [item["label"] for key, item in inventory.items() if item["requires_click"] and key not in confirmed]
    missed = list(dict.fromkeys(step["text"] for step in trace if step.get("action") == "click"
                               and not _confirmed_click(step) and control_key(step.get("text", "")) not in confirmed))
    coverage = {"discovered": len(inventory), "clicked": sorted(clicked_keys), "pending": pending, "missed": missed,
                "scope": "Controls identified in the inspected window, not every control in the application"}
    (folder / "coverage.json").write_text(json.dumps(coverage), encoding="utf-8")
    note = ("Coverage incomplete: " + ", ".join(dict.fromkeys(pending + missed))
            if pending or missed else "No pending control remains in the inspected inventory; this is not proof of complete app coverage.")
    trace.append(_frame(shot, image_path, width, height, reasoner.model, action="coverage", thought=note))
    store.log(project.id, "exploring", note)
    return trace


def _confirmed_click(step: dict) -> bool:
    learned = str(step.get("learned") or "")
    return (step.get("action") == "click" and bool(step.get("executed")) and bool(learned)
            and not click_missed(learned) and "did not describe the result in time" not in learned)


def _skip_unneeded(store: Store, project: Project, controls: list[dict], visited: set[str], covered_docs: bool) -> None:
    for item in controls:
        label = str(item.get("label") or "").strip()
        key = control_key(label)
        if not label or key in visited or not control_allowed(label):
            continue
        if should_click(item, covered_docs=covered_docs):
            continue
        visited.add(key)
        if str(item.get("role") or "") == "detail":
            store.log(project.id, "exploring", f"Left {label} unclicked. It is one option inside a control that was opened.")
        elif item.get("documented"):
            store.log(project.id, "exploring", f"Left {label} unclicked. The relevant documents already explain it.")


async def _describe(
    store: Store,
    project: Project,
    reasoner: HCompanyProvider,
    label: str,
    before: bytes,
    after: bytes,
) -> str:
    try:
        return await reasoner.describe_click(
            software=project.software_name,
            label=label,
            before=before,
            after=after,
        )
    except ProviderError as exc:
        store.log(project.id, "exploring", f"{exc}. Keeping the click on {label}.")
        return f"Clicked {label}. The model did not describe the result in time."


def _persist_trace(
    store: Store,
    project: Project,
    reasoner: HCompanyProvider,
    folder: Path,
    trace: list[dict],
    visited: set[str],
) -> None:
    if not trace:
        return
    clicks = sum(1 for step in trace if step.get("action") == "click" and step.get("executed"))
    matched = clicks == 0 and any("matches the documents" in str(step.get("thought") or "") for step in trace)
    summary = (
        f"Opened {project.software_name}. The screen matches the documents, so nothing was clicked."
        if matched
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


def _write_relevance(folder: Path, sources: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "source_relevance.json").write_text(
        json.dumps({"checked": True, "sources": sources}),
        encoding="utf-8",
    )


async def _documents_match_screen(
    store: Store,
    project: Project,
    reasoner: HCompanyProvider,
    documents: str,
    source_ids: list[str],
    folder: Path,
    image_path: Path,
    width: int,
    height: int,
    trace: list[dict],
) -> str:
    if not documents.strip():
        _write_relevance(folder, [])
        store.log(project.id, "exploring", f"Opened {project.software_name}. There are no documents to compare, so the agent will click.")
        return ""
    try:
        verdict = await reasoner.compare_with_documents(
            software=project.software_name,
            objective=project.learning_objective,
            image_bytes=image_path.read_bytes(),
            documents=documents,
        )
    except ProviderError as exc:
        _write_relevance(folder, [])
        store.log(
            project.id,
            "exploring",
            f"Could not compare the screen with the documents ({exc}). Written sources stay out of the skills and the graph. Clicking instead.",
        )
        return ""
    returned = {str(item.get("id")): item for item in verdict.get("sources") or [] if isinstance(item, dict)}
    judged = []
    for source_id in source_ids:
        item = returned.get(source_id) or {}
        relevant = item.get("relevant") if isinstance(item.get("relevant"), bool) else None
        judged.append(
            {
                "id": source_id,
                "relevant": relevant,
                "summary": str(item.get("summary") or "").strip()[:240] if relevant else "",
            }
        )
    _write_relevance(folder, judged)
    relevant_count = sum(1 for item in judged if item["relevant"] is True)
    matches = bool(verdict.get("matches")) and relevant_count > 0
    complete = bool(verdict.get("complete")) and matches
    note = str(verdict.get("note") or "").strip()
    store.log(
        project.id,
        "exploring",
        f"Kept {relevant_count} of {len(judged)} sources. Rejected or unassessed sources stay out of the skills and the graph.",
    )
    store.log(
        project.id,
        "exploring",
        f"Opened {project.software_name}. Documents match the screen: {matches}. Documents complete: {complete}. {note[:160]}",
    )
    covered = _relevant_excerpts(documents, judged)
    if covered and not needs_click(matches, complete):
        store.log(
            project.id,
            "exploring",
            "The relevant documents cover this screen. The agent will still look for buttons they do not mention, and will not choose individual options.",
        )
    elif covered:
        store.log(
            project.id,
            "exploring",
            "The relevant documents leave something out. Clicking only the controls they do not explain, and not the individual options inside them.",
        )
    else:
        store.log(
            project.id,
            "exploring",
            "The documents do not match this open app. Clicking its buttons, including ones that open options, but not each option inside them.",
        )
    return covered


def _relevant_excerpts(documents: str, judged: list[dict]) -> str:
    relevant = {item["id"] for item in judged if item.get("relevant")}
    if not relevant:
        return ""
    blocks = []
    import re

    for block in re.split(r"\n\n(?=\[source_)", documents):
        if not block.startswith("[") or "]" not in block:
            continue
        source_id = block[1:block.index("]")]
        if source_id in relevant:
            blocks.append(block)
    return "\n\n".join(blocks)


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
