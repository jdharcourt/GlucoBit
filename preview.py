#!/usr/bin/env python3
"""Desktop screenshot preview generator for CircuitPython glucose UIs."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 280
HEIGHT = 240
DEFAULT_BG_HEX = "#070B18"

COLOR_STOPS = [
    (3.0, (255, 50, 0)),
    (4.0, (255, 180, 0)),
    (5.0, (0, 180, 0)),
    (7.0, (0, 100, 255)),
    (10.0, (120, 0, 255)),
    (13.0, (80, 0, 120)),
    (15.0, (200, 0, 150)),
]

TREND_ARROWS = {
    "DoubleUp": "icons/up.bmp",
    "FortyFiveUp": "icons/up-right.bmp",
    "SingleUp": "icons/up.bmp",
    "Flat": "icons/level.bmp",
    "FortyFiveDown": "icons/down-right.bmp",
    "SingleDown": "icons/down.bmp",
    "DoubleDown": "icons/down.bmp",
    "NonComputable": "icons/alert.bmp",
}

ARROW_CACHE: dict[str, Image.Image] = {}


def hex_to_color_int(hex_str: str, default: int = 0x070B18) -> int:
    if not isinstance(hex_str, str):
        return default
    value = hex_str.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return default
    try:
        return int(value, 16)
    except ValueError:
        return default


def int_to_rgb(color: int) -> tuple[int, int, int]:
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


def rgb_to_hex(rgb_tuple: tuple[int, int, int]) -> int:
    r, g, b = rgb_tuple
    return (r << 16) | (g << 8) | b


def lighten_hex(hex_str: str, factor: float = 0.3) -> str:
    value = hex_str.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def glucose_to_rgb(glucose_mmol: float) -> tuple[int, int, int]:
    if glucose_mmol <= COLOR_STOPS[0][0]:
        return COLOR_STOPS[0][1]
    if glucose_mmol >= COLOR_STOPS[-1][0]:
        return COLOR_STOPS[-1][1]
    for idx in range(len(COLOR_STOPS) - 1):
        g1, c1 = COLOR_STOPS[idx]
        g2, c2 = COLOR_STOPS[idx + 1]
        if g1 <= glucose_mmol <= g2:
            t = (glucose_mmol - g1) / (g2 - g1)
            return (
                int(lerp(c1[0], c2[0], t)),
                int(lerp(c1[1], c2[1], t)),
                int(lerp(c1[2], c2[2], t)),
            )
    return COLOR_STOPS[-1][1]


def load_fonts() -> dict[str, ImageFont.ImageFont]:
    candidates = [
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return {
                "tiny": ImageFont.truetype(path, 12),
                "small": ImageFont.truetype(path, 18),
                "medium": ImageFont.truetype(path, 30),
                "large": ImageFont.truetype(path, 74),
            }
        except OSError:
            continue
    fallback = ImageFont.load_default()
    return {"tiny": fallback, "small": fallback, "medium": fallback, "large": fallback}


def draw_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[float, float],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    anchor: str = "lt",
) -> None:
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None = None,
    width: int = 1,
) -> None:
    r = max(0, min(radius, w // 2, h // 2))
    if r == 0:
        draw.rectangle((x, y, x + w, y + h), fill=fill, outline=outline, width=width)
        return
    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=r,
        fill=fill,
        outline=outline,
        width=width,
    )


def get_trend_arrow(path: str) -> Image.Image | None:
    if path in ARROW_CACHE:
        return ARROW_CACHE[path]
    full_path = Path(path)
    if not full_path.exists():
        return None
    img = Image.open(full_path).convert("RGBA")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if (r == 0 and g == 0 and b == 0) or (r < 16 and g < 16 and b < 16):
                px[x, y] = (r, g, b, 0)
            else:
                px[x, y] = (r, g, b, a)
    ARROW_CACHE[path] = img
    return img


def draw_trend_arrow(img: Image.Image, trend: str | None, center_x: int, center_y: int) -> None:
    path = TREND_ARROWS.get(trend)
    if not path:
        return
    arrow = get_trend_arrow(path)
    if arrow is None:
        return
    x = int(center_x - arrow.width / 2)
    y = int(center_y - arrow.height / 2)
    img.alpha_composite(arrow, (x, y))


def build_preview_model(
    value: float | None,
    trend: str | None,
    previous_glucose: float | None,
    mmol: bool,
    display_name: str,
    bg_hex: str,
) -> dict[str, object]:
    if value is not None:
        display_value = round(value / 18, 1) if mmol else int(round(value))
    else:
        display_value = None

    if display_value is None:
        status = "NO DATA"
    elif mmol:
        if display_value < 3.9:
            status = "LOW"
        elif display_value > 13.0:
            status = "VERY HIGH"
        elif display_value > 10.0:
            status = "HIGH"
        else:
            status = "IN RANGE"
    else:
        if display_value < 70:
            status = "LOW"
        elif display_value > 250:
            status = "VERY HIGH"
        elif display_value > 180:
            status = "HIGH"
        else:
            status = "IN RANGE"

    value_mmol = value / 18.0 if value is not None else 6.0
    rgb_value = glucose_to_rgb(value_mmol)
    accent_color = rgb_to_hex(rgb_value)

    bg_color_hex = bg_hex
    try:
        light_bg_hex = lighten_hex(bg_color_hex)
    except Exception:
        bg_color_hex = DEFAULT_BG_HEX
        light_bg_hex = lighten_hex(bg_color_hex)

    bg_color = hex_to_color_int(bg_color_hex, default=0x070B18)
    light_bg = hex_to_color_int(light_bg_hex, default=0x070B18)

    if value is not None and previous_glucose is not None:
        delta = value - previous_glucose
        if mmol:
            delta = round(delta / 18, 1)
            delta_text = f"{delta:+.1f}"
        else:
            delta_text = f"{int(round(delta)):+d}"
        delta_color = 0x4DFF88 if delta < 0 else (0xFFD34D if delta > 0 else 0xB9C9EA)
    else:
        delta_text = "--"
        delta_color = 0x9AA7C2

    status_color = {
        "LOW": 0xFF4D67,
        "IN RANGE": 0x4DFF88,
        "HIGH": 0xFFD34D,
        "VERY HIGH": 0xFF8C42,
        "NO DATA": 0x9AA7C2,
    }.get(status, 0x9AA7C2)

    trend_text = trend if trend else "Unknown"
    trend_glyph = {
        "DoubleUp": "UPUP",
        "SingleUp": "UP",
        "FortyFiveUp": "UP/",
        "Flat": "FLAT",
        "FortyFiveDown": "DN/",
        "SingleDown": "DN",
        "DoubleDown": "DNDN",
        "NonComputable": "ALERT",
    }.get(trend, "UNK")

    name_text = display_name.strip() if display_name else "Dexcom"
    if len(name_text) > 18:
        name_text = name_text[:17] + "."

    return {
        "display_value": display_value,
        "value_text": str(display_value) if display_value is not None else "--",
        "unit": "mmol/L" if mmol else "mg/dL",
        "status": status,
        "status_color": status_color,
        "delta_text": delta_text,
        "delta_color": delta_color,
        "trend_text": trend_text[:14],
        "trend_glyph": trend_glyph,
        "trend_key": trend,
        "name_text": name_text,
        "rgb_value": rgb_value,
        "accent_color": accent_color,
        "bg_color_hex": bg_color_hex,
        "bg_color": bg_color,
        "light_bg": light_bg,
    }


def render_theme_1(img: Image.Image, model: dict[str, object], fonts: dict[str, ImageFont.ImageFont]) -> None:
    draw = ImageDraw.Draw(img)
    rounded_rect(draw, 0, 0, 280, 240, 15, int_to_rgb(model["light_bg"]))
    draw.rectangle((0, 0, 280, 34), fill=int_to_rgb(model["bg_color"]))
    rounded_rect(draw, 0, 34, 280, 4, 15, int_to_rgb(model["accent_color"]))
    rounded_rect(draw, 8, 46, 264, 122, 15, int_to_rgb(model["bg_color"]))
    rounded_rect(draw, 8, 176, 126, 56, 15, int_to_rgb(model["bg_color"]))
    rounded_rect(draw, 146, 176, 126, 56, 15, int_to_rgb(model["bg_color"]))

    draw_text(draw, str(model["name_text"]), (10, 9), fonts["tiny"], (221, 231, 255), anchor="lt")
    draw_text(draw, "12:34:56", (270, 9), fonts["tiny"], (234, 241, 255), anchor="rt")
    draw_text(draw, str(model["status"]), (140, 56), fonts["tiny"], int_to_rgb(model["status_color"]), anchor="mt")
    draw_text(draw, str(model["value_text"]), (140, 106), fonts["large"], int_to_rgb(model["accent_color"]), anchor="mm")
    draw_text(draw, str(model["unit"]), (140, 146), fonts["tiny"], (175, 193, 232), anchor="mt")
    draw_text(draw, "TREND", (16, 184), fonts["tiny"], (175, 193, 232), anchor="lt")
    draw_text(draw, str(model["trend_text"]), (71, 228), fonts["tiny"], (221, 231, 255), anchor="ms")
    draw_text(draw, "DELTA", (154, 184), fonts["tiny"], (175, 193, 232), anchor="lt")
    draw_text(draw, str(model["delta_text"]), (209, 209), fonts["medium"], int_to_rgb(model["delta_color"]), anchor="mm")
    draw_trend_arrow(img, model["trend_key"], 71, 204)


def render_theme_2(img: Image.Image, model: dict[str, object], fonts: dict[str, ImageFont.ImageFont]) -> None:
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 280, 240), fill=int_to_rgb(model["light_bg"]))
    rounded_rect(draw, 0, 0, 280, 50, 15, int_to_rgb(model["accent_color"]))
    rounded_rect(draw, 15, 60, 250, 120, 15, int_to_rgb(model["bg_color"]))
    rounded_rect(draw, 0, 190, 280, 60, 15, int_to_rgb(model["bg_color"]))
    rounded_rect(draw, 138, 190, 4, 50, 15, int_to_rgb(model["accent_color"]))

    draw_text(draw, str(model["name_text"]), (10, 14), fonts["tiny"], (16, 20, 24), anchor="lt")
    draw_text(draw, "12:34:56", (270, 14), fonts["tiny"], (16, 20, 24), anchor="rt")
    draw_text(draw, str(model["status"]), (140, 32), fonts["tiny"], (16, 20, 24), anchor="mt")
    draw_text(draw, str(model["value_text"]), (140, 110), fonts["large"], int_to_rgb(model["accent_color"]), anchor="mm")
    draw_text(draw, str(model["unit"]), (140, 155), fonts["medium"], (185, 201, 234), anchor="mt")
    draw_text(draw, "TREND", (14, 198), fonts["tiny"], (143, 162, 201), anchor="lt")
    draw_text(draw, str(model["trend_glyph"]), (14, 216), fonts["tiny"], (221, 231, 255), anchor="lt")
    draw_trend_arrow(img, model["trend_key"], 106, 216)
    draw_text(draw, "DELTA", (154, 198), fonts["tiny"], (143, 162, 201), anchor="lt")
    draw_text(draw, str(model["delta_text"]), (154, 212), fonts["medium"], int_to_rgb(model["delta_color"]), anchor="lt")


def render_theme_3(img: Image.Image, model: dict[str, object], fonts: dict[str, ImageFont.ImageFont]) -> None:
    draw = ImageDraw.Draw(img)
    rounded_rect(
        draw,
        0,
        0,
        280,
        240,
        50,
        int_to_rgb(model["bg_color"]),
        outline=int_to_rgb(model["accent_color"]),
        width=8,
    )
    draw_text(draw, "12:34:56", (30, 16), fonts["tiny"], (198, 202, 212), anchor="lt")
    draw_text(draw, str(model["name_text"]), (2, 16), fonts["tiny"], (158, 164, 181), anchor="rt")
    draw_text(draw, str(model["status"]), (140, 44), fonts["tiny"], int_to_rgb(model["status_color"]), anchor="mt")
    draw_text(draw, str(model["value_text"]), (140, 110), fonts["large"], (243, 245, 250), anchor="mm")
    draw_text(draw, str(model["unit"]), (140, 148), fonts["tiny"], (164, 170, 188), anchor="mt")
    draw_text(draw, str(model["delta_text"]), (25, 224), fonts["medium"], int_to_rgb(model["delta_color"]), anchor="ls")
    draw_trend_arrow(img, model["trend_key"], 140, 190)


def slug(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", "/"):
            out.append("-")
    compact = "".join(out).strip("-")
    while "--" in compact:
        compact = compact.replace("--", "-")
    return compact or "sample"


def build_scenarios() -> list[dict[str, object]]:
    return [
        {"name": "in-range-flat", "value": 110.0, "prev": 108.0, "trend": "Flat", "mmol": False},
        {"name": "low-singledown", "value": 63.0, "prev": 72.0, "trend": "SingleDown", "mmol": False},
        {"name": "high-doubleup", "value": 245.0, "prev": 210.0, "trend": "DoubleUp", "mmol": False},
        {"name": "mmol-in-range", "value": 126.0, "prev": 117.0, "trend": "FortyFiveUp", "mmol": True},
        {"name": "alert-noncomputable", "value": 95.0, "prev": 95.0, "trend": "NonComputable", "mmol": False},
        {"name": "no-data", "value": None, "prev": None, "trend": None, "mmol": False},
    ]


def parse_theme_arg(theme_arg: str) -> list[int]:
    if theme_arg == "all":
        return [1, 2, 3]
    return [int(theme_arg)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate desktop screenshots of glucose UI themes.")
    parser.add_argument("--theme", choices=["1", "2", "3", "all"], default="all")
    parser.add_argument("--out", default="previews", help="Output directory for generated screenshots")
    parser.add_argument("--bg-color", default=DEFAULT_BG_HEX, help="Background color (hex), e.g. #070B18")
    parser.add_argument("--name", default="DexcomFollowerName", help="Display name used in previews")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts()
    themes = parse_theme_arg(args.theme)
    scenarios = build_scenarios()

    generated: list[Path] = []
    for scenario in scenarios:
        model = build_preview_model(
            value=scenario["value"],
            trend=scenario["trend"],
            previous_glucose=scenario["prev"],
            mmol=scenario["mmol"],
            display_name=args.name,
            bg_hex=args.bg_color,
        )
        for theme in themes:
            img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
            if theme == 1:
                render_theme_1(img, model, fonts)
            elif theme == 2:
                render_theme_2(img, model, fonts)
            else:
                render_theme_3(img, model, fonts)
            file_name = f"theme{theme}_{slug(scenario['name'])}.png"
            output_path = out_dir / file_name
            img.convert("RGB").save(output_path, "PNG")
            generated.append(output_path)

    for path in generated:
        print(path.as_posix())
    print(f"Generated {len(generated)} preview image(s) in {out_dir.as_posix()}")


if __name__ == "__main__":
    main()
