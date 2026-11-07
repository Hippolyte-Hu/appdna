from pathlib import Path

GRID_COLUMNS = 12
GRID_ROWS = 6

_SKIP = (
    "关闭",
    "最小化",
    "全屏幕",
    "全屏",
    "close",
    "minimize",
    "zoom",
    "quit",
    "退出",
    "删除",
    "delete",
)


def norm_to_image(x: int, y: int, width: int, height: int) -> tuple[int, int]:
    x = max(0, min(1000, int(x)))
    y = max(0, min(1000, int(y)))
    return int(x / 1000 * (width - 1)), int(y / 1000 * (height - 1))


def cell_box(cell: int, width: int, height: int) -> tuple[int, int, int, int]:
    total = GRID_COLUMNS * GRID_ROWS
    index = max(1, min(total, int(cell))) - 1
    column = index % GRID_COLUMNS
    row = index // GRID_COLUMNS
    x0 = int(column * width / GRID_COLUMNS)
    y0 = int(row * height / GRID_ROWS)
    x1 = int((column + 1) * width / GRID_COLUMNS)
    y1 = int((row + 1) * height / GRID_ROWS)
    return x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)


def click_point(cell: int, x: int, y: int, width: int, height: int) -> tuple[int, int]:
    """H Company returns x and y on a 0–1000 grid. The cell id is only a hint."""
    del cell
    if int(x) > 1000 or int(y) > 1000:
        return min(max(int(x), 0), width - 1), min(max(int(y), 0), height - 1)
    return norm_to_image(x, y, width, height)


def control_key(label: str) -> str:
    return " ".join(label.lower().split())


def control_allowed(label: str) -> bool:
    text = label.strip()
    if not text:
        return False
    lowered = text.lower()
    return not any(token in text or token in lowered for token in _SKIP)


def next_control(controls: list[dict], visited: set[str]) -> dict | None:
    for item in controls:
        label = str(item.get("label") or "").strip()
        if not control_allowed(label):
            continue
        if control_key(label) in visited:
            continue
        return item
    return None


def next_scroll(hint: str, counts: dict[str, int], stalled: set[str], limit: int = 3) -> str | None:
    """After the visible controls are tried, look below the fold and then above it."""
    order: list[str] = []
    if hint in {"up", "down"}:
        order.append(hint)
    for direction in ("down", "up"):
        if direction not in order:
            order.append(direction)
    for direction in order:
        if direction in stalled or counts.get(direction, 0) >= limit:
            continue
        return direction
    return None


def picture_moved(before: Path, after: Path) -> bool:
    from PIL import Image, ImageChops, ImageStat

    left = Image.open(before).convert("L").resize((80, 48))
    right = Image.open(after).convert("L").resize((80, 48))
    change = ImageStat.Stat(ImageChops.difference(left, right)).mean[0]
    return change >= 8


def click_missed(learned: str) -> bool:
    text = learned.strip()
    lowered = text.lower()
    return (
        lowered.startswith("missed")
        or text.startswith("没点中")
        or "没有变化" in text
        or "did not change" in lowered
        or "no change" in lowered
    )


def draw_control_grid(source: Path, dest: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.open(source).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    font = _font(18)
    for index in range(1, GRID_COLUMNS * GRID_ROWS + 1):
        x0, y0, x1, y1 = cell_box(index, width, height)
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(80, 255, 190, 90), width=1)
        badge = f"{index}"
        draw.rectangle([x0 + 2, y0 + 2, x0 + 8 + 10 * len(badge), y0 + 20], fill=(0, 0, 0, 180))
        draw.text((x0 + 5, y0 + 2), badge, fill=(190, 255, 220, 255), font=font)
    composed = Image.alpha_composite(image, overlay).convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    composed.save(dest)


def _font(size: int):
    from PIL import ImageFont

    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
