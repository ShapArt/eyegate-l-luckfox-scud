from __future__ import annotations

import math
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Box:
    id: str
    label: str
    x: int
    y: int
    w: int
    h: int
    fill: str = "#FFFFFF"
    stroke: str = "#111111"
    shape: str = "rect"  # rect | rounded | diamond


@dataclass(frozen=True)
class Arrow:
    src: str
    dst: str
    label: str = ""


def _font(
    size: int, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Pick a font that supports Cyrillic.

    Diagrams are generated in both Windows and WSL/Linux environments, so we search common font
    locations (including Windows fonts mounted under /mnt/c) to avoid broken Cyrillic glyphs and
    text layout issues.
    """

    def win_font(name: str) -> Path:
        windir = os.environ.get("WINDIR") or r"C:\Windows"
        return Path(windir) / "Fonts" / name

    candidates: list[Path] = []

    # Native Windows.
    candidates.extend(
        [
            win_font("timesbd.ttf" if bold else "times.ttf"),
            win_font("timesi.ttf"),  # fallback
            win_font("arialbd.ttf" if bold else "arial.ttf"),
        ]
    )

    # WSL: Windows fonts are typically available under /mnt/c.
    candidates.extend(
        [
            Path("/mnt/c/Windows/Fonts") / ("timesbd.ttf" if bold else "times.ttf"),
            Path("/mnt/c/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
        ]
    )

    # Common Linux fonts with Cyrillic support.
    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/dejavu")
            / ("DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf"),
            Path("/usr/share/fonts/truetype/dejavu")
            / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation")
            / ("LiberationSerif-Bold.ttf" if bold else "LiberationSerif-Regular.ttf"),
            Path("/usr/share/fonts/truetype/freefont")
            / ("FreeSerifBold.ttf" if bold else "FreeSerif.ttf"),
        ]
    )

    for cand in candidates:
        try:
            if cand.exists():
                return ImageFont.truetype(str(cand), size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_width(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont
) -> float:
    try:
        return float(draw.textlength(text, font=font))
    except Exception:
        try:
            box = draw.textbbox((0, 0), text, font=font)
            return float(box[2] - box[0])
        except Exception:
            return float(len(text) * 7)


def _fix_text(text: str) -> str:
    """
    Recover cp1251-mojibake strings that accidentally became Latin-1-like text.

    Example:
      'Èíòåðôåéñ' -> 'Интерфейс'
    """
    if not text:
        return text
    # If normal Cyrillic already present, keep as-is.
    if any("\u0400" <= ch <= "\u04FF" for ch in text):
        return text
    # Heuristic: mojibake usually contains many bytes from Latin-1 upper range.
    if not any(0xC0 <= ord(ch) <= 0xFF for ch in text):
        return text
    for enc in ("latin1", "cp1252"):
        try:
            fixed = text.encode(enc).decode("cp1251")
            if any("\u0400" <= ch <= "\u04FF" for ch in fixed):
                return fixed
        except Exception:
            continue
    return text


def _wrap_lines(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int
) -> list[str]:
    # Simple word wrap that works for Cyrillic and ASCII.
    lines: list[str] = []
    for part in (text or "").split("\n"):
        cur = ""
        for word in part.split():
            test = (cur + " " + word).strip()
            if _text_width(draw, test, font) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def _draw_box(draw: ImageDraw.ImageDraw, box: Box) -> None:
    if box.shape == "diamond":
        cx = box.x + box.w // 2
        cy = box.y + box.h // 2
        pts = [(cx, box.y), (box.x + box.w, cy), (cx, box.y + box.h), (box.x, cy)]
        draw.polygon(pts, fill=box.fill, outline=box.stroke)
        draw.line([pts[0], pts[1]], fill=box.stroke, width=2)
        draw.line([pts[1], pts[2]], fill=box.stroke, width=2)
        draw.line([pts[2], pts[3]], fill=box.stroke, width=2)
        draw.line([pts[3], pts[0]], fill=box.stroke, width=2)
    elif box.shape == "rounded" and hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(
            [box.x, box.y, box.x + box.w, box.y + box.h],
            radius=18,
            fill=box.fill,
            outline=box.stroke,
            width=2,
        )
    else:
        draw.rectangle(
            [box.x, box.y, box.x + box.w, box.y + box.h],
            fill=box.fill,
            outline=box.stroke,
            width=2,
        )
    text = _fix_text(box.label or "")
    max_w = max(40, box.w - 16)
    max_h = max(20, box.h - 16)

    chosen_font: ImageFont.ImageFont = _font(18, bold=True)
    chosen_lines: list[str] = []
    line_h = 22

    for size in (18, 17, 16, 15, 14, 13, 12, 11, 10):
        f = _font(size, bold=True)
        lines = _wrap_lines(draw, text, f, max_w=max_w)
        lh = int(size * 1.25)
        if lh <= 0:
            lh = 18
        total_h = len(lines) * lh
        if total_h <= max_h or size == 10:
            chosen_font = f
            chosen_lines = lines
            line_h = lh
            break

    if not chosen_lines:
        return

    total_h = len(chosen_lines) * line_h
    ty = box.y + (box.h - total_h) // 2
    for ln in chosen_lines:
        tw = _text_width(draw, ln, chosen_font)
        tx = box.x + (box.w - int(tw)) // 2
        draw.text((tx, ty), ln, fill="#111111", font=chosen_font)
        ty += line_h


def _arrow_points(a: Box, b: Box) -> tuple[tuple[int, int], tuple[int, int]]:
    # Connect centers; then clip to box borders.
    ax, ay = a.x + a.w // 2, a.y + a.h // 2
    bx, by = b.x + b.w // 2, b.y + b.h // 2
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return (ax, ay), (bx, by)
    # clip start
    t_candidates = []
    if dx != 0:
        t_candidates.extend([(a.x - ax) / dx, (a.x + a.w - ax) / dx])
    if dy != 0:
        t_candidates.extend([(a.y - ay) / dy, (a.y + a.h - ay) / dy])
    t_start = min([t for t in t_candidates if t > 0], default=0.0)
    sx, sy = int(ax + dx * t_start), int(ay + dy * t_start)
    # clip end (from b backwards)
    dx2, dy2 = -dx, -dy
    t_candidates2 = []
    if dx2 != 0:
        t_candidates2.extend([(b.x - bx) / dx2, (b.x + b.w - bx) / dx2])
    if dy2 != 0:
        t_candidates2.extend([(b.y - by) / dy2, (b.y + b.h - by) / dy2])
    t_end = min([t for t in t_candidates2 if t > 0], default=0.0)
    ex, ey = int(bx + dx2 * t_end), int(by + dy2 * t_end)
    return (sx, sy), (ex, ey)


def _rects_intersect(
    r1: tuple[int, int, int, int], r2: tuple[int, int, int, int]
) -> bool:
    a0, b0, a1, b1 = r1
    c0, d0, c1, d1 = r2
    return not (a1 < c0 or c1 < a0 or b1 < d0 or d1 < b0)


def _point_in_rect(p: tuple[float, float], r: tuple[int, int, int, int]) -> bool:
    x, y = p
    x0, y0, x1, y1 = r
    return x0 <= x <= x1 and y0 <= y <= y1


def _seg_intersects_seg(
    p1: tuple[float, float],
    p2: tuple[float, float],
    q1: tuple[float, float],
    q2: tuple[float, float],
) -> bool:
    def orient(
        a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
    ) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_seg(
        a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
    ) -> bool:
        return (
            min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
            and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9
        )

    o1 = orient(p1, p2, q1)
    o2 = orient(p1, p2, q2)
    o3 = orient(q1, q2, p1)
    o4 = orient(q1, q2, p2)

    if (o1 * o2 < 0) and (o3 * o4 < 0):
        return True
    if abs(o1) < 1e-9 and on_seg(p1, p2, q1):
        return True
    if abs(o2) < 1e-9 and on_seg(p1, p2, q2):
        return True
    if abs(o3) < 1e-9 and on_seg(q1, q2, p1):
        return True
    if abs(o4) < 1e-9 and on_seg(q1, q2, p2):
        return True
    return False


def _line_intersects_rect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    rect: tuple[int, int, int, int],
) -> bool:
    if _point_in_rect(p1, rect) or _point_in_rect(p2, rect):
        return True
    x0, y0, x1, y1 = rect
    edges = [
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    ]
    return any(_seg_intersects_seg(p1, p2, e0, e1) for e0, e1 in edges)


def _label_lines_for_arrow(label: str, max_chars: int = 24) -> list[str]:
    text = _fix_text((label or "").strip())
    if not text:
        return []
    if "\n" in text:
        return [x.strip() for x in text.split("\n") if x.strip()]
    if "/" in text:
        parts = [p.strip() for p in text.split("/") if p.strip()]
        if len(parts) >= 2:
            return [f"{parts[0]}/", " / ".join(parts[1:])]
    if len(text) > max_chars:
        cut = text.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        return [text[:cut].strip(), text[cut:].strip()]
    return [text]


def _measure_multiline(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
    line_spacing: int = 2,
) -> tuple[int, int]:
    if not lines:
        return (0, 0)
    boxes = [draw.textbbox((0, 0), ln, font=font) for ln in lines]
    widths = [max(0, b[2] - b[0]) for b in boxes]
    heights = [max(0, b[3] - b[1]) for b in boxes]
    total_h = sum(heights) + line_spacing * max(0, len(lines) - 1)
    return (max(widths) if widths else 0, total_h)


def _measure_multiline_svg(
    lines: list[str], font_size: int = 14, line_spacing: int = 2
) -> tuple[int, int]:
    """
    Approximate text box for SVG label placement (same collision logic as PNG path).
    """
    if not lines:
        return (0, 0)
    avg_char_w = int(round(font_size * 0.56))
    widths = [max(1, len(ln) * avg_char_w) for ln in lines]
    line_h = int(round(font_size * 1.22))
    total_h = line_h * len(lines) + line_spacing * max(0, len(lines) - 1)
    return (max(widths), total_h)


def _choose_label_rect(
    sx: int,
    sy: int,
    ex: int,
    ey: int,
    rect_w: int,
    rect_h: int,
    occupied_label_rects: list[tuple[int, int, int, int]],
    all_boxes: list[Box],
    all_segments: list[tuple[tuple[int, int], tuple[int, int]]],
    current_segment_idx: int,
) -> tuple[int, int, int, int]:
    mx, my = (sx + ex) / 2.0, (sy + ey) / 2.0
    dx, dy = (ex - sx), (ey - sy)
    d = math.hypot(dx, dy) or 1.0
    nx, ny = (-dy / d), (dx / d)
    tx, ty = (dx / d), (dy / d)

    k_values = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6]
    base_values = [16, 20, 24]
    along_values = [0, 20, -20, 40, -40, 60, -60]

    def rect_bad(rect: tuple[int, int, int, int]) -> bool:
        for bx in all_boxes:
            bxr = (bx.x - 6, bx.y - 6, bx.x + bx.w + 6, bx.y + bx.h + 6)
            if _rects_intersect(rect, bxr):
                return True
        for occ in occupied_label_rects:
            if _rects_intersect(rect, occ):
                return True
        for idx, seg in enumerate(all_segments):
            if idx == current_segment_idx:
                continue
            if _line_intersects_rect(seg[0], seg[1], rect):
                return True
        # Keep label clear of own arrow body.
        if _line_intersects_rect((sx, sy), (ex, ey), rect):
            return True
        return False

    for along in along_values:
        for base in base_values:
            for k in k_values:
                perp = base + 16 * k
                cx = mx + nx * perp + tx * along
                cy = my + ny * perp + ty * along
                x0 = int(round(cx - rect_w / 2))
                y0 = int(round(cy - rect_h / 2))
                rect = (x0, y0, x0 + rect_w, y0 + rect_h)
                if not rect_bad(rect):
                    return rect

    # Last-resort fallback near midpoint.
    x0 = int(round(mx - rect_w / 2))
    y0 = int(round(my - rect_h / 2 - 26))
    return (x0, y0, x0 + rect_w, y0 + rect_h)


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    a: Box,
    b: Box,
    label: str = "",
    occupied_label_rects: Optional[list[tuple[int, int, int, int]]] = None,
    all_boxes: Optional[list[Box]] = None,
    all_segments: Optional[list[tuple[tuple[int, int], tuple[int, int]]]] = None,
    current_segment_idx: int = -1,
) -> None:
    (sx, sy), (ex, ey) = _arrow_points(a, b)
    draw.line([sx, sy, ex, ey], fill="#111111", width=2)
    # arrowhead
    angle = math.atan2(ey - sy, ex - sx)
    ah = 10
    a1 = angle + math.pi * 0.85
    a2 = angle - math.pi * 0.85
    p1 = (int(ex + ah * math.cos(a1)), int(ey + ah * math.sin(a1)))
    p2 = (int(ex + ah * math.cos(a2)), int(ey + ah * math.sin(a2)))
    draw.polygon([(ex, ey), p1, p2], fill="#111111")

    if label:
        if occupied_label_rects is None:
            occupied_label_rects = []
        if all_boxes is None:
            all_boxes = [a, b]
        if all_segments is None:
            all_segments = [((sx, sy), (ex, ey))]

        lines = _label_lines_for_arrow(label, max_chars=24)
        f = _font(15, bold=False)
        pad_x, pad_y = 8, 5
        line_spacing = 2
        text_w, text_h = _measure_multiline(draw, lines, f, line_spacing=line_spacing)
        rect_w = text_w + pad_x * 2
        rect_h = text_h + pad_y * 2
        chosen = _choose_label_rect(
            sx=sx,
            sy=sy,
            ex=ex,
            ey=ey,
            rect_w=rect_w,
            rect_h=rect_h,
            occupied_label_rects=occupied_label_rects,
            all_boxes=all_boxes,
            all_segments=all_segments,
            current_segment_idx=current_segment_idx,
        )

        occupied_label_rects.append(chosen)
        x0, y0, x1, y1 = chosen
        draw.rectangle([x0, y0, x1, y1], fill="#FFFFFF", outline="#111111", width=1)
        ty0 = y0 + pad_y
        for ln in lines:
            lw, lh = _measure_multiline(draw, [ln], f, line_spacing=0)
            tx0 = x0 + (rect_w - lw) // 2
            draw.text((tx0, ty0), ln, fill="#111111", font=f)
            ty0 += lh + line_spacing


def save_block_diagram_png(
    path: Path, title: str, boxes: list[Box], arrows: list[Arrow], size: tuple[int, int]
) -> None:
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    title_font = _font(24, bold=True)
    draw.text((20, 15), _fix_text(title), fill="#111111", font=title_font)

    box_by_id = {b.id: b for b in boxes}
    for b in boxes:
        _draw_box(draw, b)
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for a in arrows:
        src = box_by_id[a.src]
        dst = box_by_id[a.dst]
        segments.append(_arrow_points(src, dst))
    occupied: list[tuple[int, int, int, int]] = []
    for idx, a in enumerate(arrows):
        _draw_arrow(
            draw,
            box_by_id[a.src],
            box_by_id[a.dst],
            label=a.label,
            occupied_label_rects=occupied,
            all_boxes=boxes,
            all_segments=segments,
            current_segment_idx=idx,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def save_block_diagram_svg(
    path: Path, title: str, boxes: list[Box], arrows: list[Arrow], size: tuple[int, int]
) -> None:
    w, h = size
    box_by_id = {b.id: b for b in boxes}

    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    )
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>')
    parts.append(
        f'<text x="20" y="40" font-family="Times New Roman" font-size="24" font-weight="bold" fill="#111111">{_svg_escape(_fix_text(title))}</text>'
    )

    # Arrows first (under boxes)
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for a in arrows:
        src = box_by_id[a.src]
        dst = box_by_id[a.dst]
        segments.append(_arrow_points(src, dst))

    occupied: list[tuple[int, int, int, int]] = []
    for idx, a in enumerate(arrows):
        src = box_by_id[a.src]
        dst = box_by_id[a.dst]
        (sx, sy), (ex, ey) = _arrow_points(src, dst)
        parts.append(
            f'<line x1="{sx}" y1="{sy}" x2="{ex}" y2="{ey}" stroke="#111111" stroke-width="2"/>'
        )
        # arrowhead
        angle = math.atan2(ey - sy, ex - sx)
        ah = 10
        a1 = angle + math.pi * 0.85
        a2 = angle - math.pi * 0.85
        p1 = (ex + ah * math.cos(a1), ey + ah * math.sin(a1))
        p2 = (ex + ah * math.cos(a2), ey + ah * math.sin(a2))
        parts.append(
            f'<polygon points="{ex},{ey} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="#111111"/>'
        )
        if a.label:
            lines = _label_lines_for_arrow(a.label, max_chars=24)
            fsize = 14
            line_spacing = 2
            pad_x, pad_y = 8, 5
            tw, th = _measure_multiline_svg(
                lines, font_size=fsize, line_spacing=line_spacing
            )
            rect_w = tw + pad_x * 2
            rect_h = th + pad_y * 2
            rect = _choose_label_rect(
                sx=sx,
                sy=sy,
                ex=ex,
                ey=ey,
                rect_w=rect_w,
                rect_h=rect_h,
                occupied_label_rects=occupied,
                all_boxes=boxes,
                all_segments=segments,
                current_segment_idx=idx,
            )
            occupied.append(rect)
            x0, y0, x1, y1 = rect
            parts.append(
                f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="#ffffff" stroke="#111111" stroke-width="1"/>'
            )
            line_h = int(round(fsize * 1.22))
            y_line = y0 + pad_y + line_h
            for ln in lines:
                ln_esc = _svg_escape(_fix_text(ln))
                parts.append(
                    f'<text x="{(x0 + x1) / 2:.1f}" y="{y_line}" text-anchor="middle" '
                    f'font-family="Times New Roman" font-size="{fsize}" fill="#111111">{ln_esc}</text>'
                )
                y_line += line_h + line_spacing

    for b in boxes:
        if b.shape == "diamond":
            cx = b.x + b.w / 2
            cy = b.y + b.h / 2
            pts = f"{cx:.1f},{b.y} {b.x+b.w:.1f},{cy:.1f} {cx:.1f},{b.y+b.h} {b.x:.1f},{cy:.1f}"
            parts.append(
                f'<polygon points="{pts}" fill="{b.fill}" stroke="{b.stroke}" stroke-width="2"/>'
            )
        elif b.shape == "rounded":
            parts.append(
                f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" rx="18" ry="18" fill="{b.fill}" stroke="{b.stroke}" stroke-width="2"/>'
            )
        else:
            parts.append(
                f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" fill="{b.fill}" stroke="{b.stroke}" stroke-width="2"/>'
            )
        # Centered multiline text with conservative wrap for readability.
        label = _fix_text(b.label or "")
        raw_lines = [x.strip() for x in label.split("\n") if x.strip()]
        if not raw_lines:
            raw_lines = [label.strip()]
        max_chars = max(8, int((b.w - 16) / 9))
        lines: list[str] = []
        for rl in raw_lines:
            cur = ""
            for word in rl.split():
                test = (cur + " " + word).strip()
                if len(test) <= max_chars or not cur:
                    cur = test
                else:
                    lines.append(cur)
                    cur = word
            if cur:
                lines.append(cur)
        if not lines:
            lines = [label]
        fsize = 16
        line_h = int(round(fsize * 1.22))
        while line_h * len(lines) > (b.h - 12) and fsize > 10:
            fsize -= 1
            line_h = int(round(fsize * 1.22))
        total_h = line_h * len(lines)
        y_line = b.y + (b.h - total_h) / 2 + line_h * 0.85
        for ln in lines:
            parts.append(
                f'<text x="{b.x + b.w / 2:.1f}" y="{y_line:.1f}" text-anchor="middle" '
                f'font-family="Times New Roman" font-size="{fsize}" font-weight="bold" fill="#111111">{_svg_escape(ln)}</text>'
            )
            y_line += line_h

    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _drawio_xml(title: str, boxes: list[Box], arrows: list[Arrow]) -> str:
    # Minimal uncompressed draw.io (mxGraphModel in diagram).
    file_id = str(uuid.uuid4())
    diagram_id = str(uuid.uuid4())
    parts: list[str] = []
    parts.append(
        f'<mxfile host="app.diagrams.net" modified="{datetime_utc()}" agent="codex" version="22.1.0" type="device">'
    )
    parts.append(
        f'  <diagram id="{diagram_id}" name="{_svg_escape(_fix_text(title))}">'
    )
    parts.append(
        '    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">'
    )
    parts.append("      <root>")
    parts.append('        <mxCell id="0"/>')
    parts.append('        <mxCell id="1" parent="0"/>')
    id_map: dict[str, str] = {}
    for idx, b in enumerate(boxes, start=2):
        cid = str(idx)
        id_map[b.id] = cid
        base_style = "whiteSpace=wrap;html=1;strokeWidth=2;"
        if b.shape == "diamond":
            style = "rhombus;" + base_style
        elif b.shape == "rounded":
            style = "rounded=1;" + base_style
        else:
            style = base_style
        parts.append(
            f'        <mxCell id="{cid}" value="{_svg_escape(_fix_text(b.label))}" style="{style}" vertex="1" parent="1">'
        )
        parts.append(
            f'          <mxGeometry x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" as="geometry"/>'
        )
        parts.append("        </mxCell>")
    edge_id = len(boxes) + 2
    for a in arrows:
        cid = str(edge_id)
        edge_id += 1
        src = id_map.get(a.src)
        dst = id_map.get(a.dst)
        if not src or not dst:
            continue
        style = "endArrow=block;html=1;strokeWidth=2;"
        value = _svg_escape(_fix_text(a.label)) if a.label else ""
        parts.append(
            f'        <mxCell id="{cid}" value="{value}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
        )
        parts.append('          <mxGeometry relative="1" as="geometry"/>')
        parts.append("        </mxCell>")
    parts.append("      </root>")
    parts.append("    </mxGraphModel>")
    parts.append("  </diagram>")
    parts.append("</mxfile>")
    return "\n".join(parts) + "\n"


def datetime_utc() -> str:
    # ISO without timezone suffix (draw.io accepts many)
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def write_drawio(path: Path, title: str, boxes: list[Box], arrows: list[Arrow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_drawio_xml(title, boxes, arrows), encoding="utf-8")


def generate_diagrams(docs_root: Path) -> dict[str, dict[str, Path]]:
    """
    Generate a minimal set of diagrams (sources + exports) for the docs bundle.
    Returns a mapping diagram_id -> {'png': Path, 'svg': Path, 'drawio': Path}.
    """
    schemes_dir = docs_root / "schemes"
    sources_dir = schemes_dir / "sources"
    exports_dir = schemes_dir / "exports"
    sources_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    out: dict[str, dict[str, Path]] = {}

    # 1) Structural/architecture
    arch_boxes = [
        Box("ui", "Интерфейс (SPA)\nReact/Vite", 80, 140, 240, 90, fill="#F3F7FF"),
        Box("api", "Сервер\nFastAPI", 380, 140, 240, 90, fill="#F3FFF7"),
        Box("ws", "WebSocket\n/ws/status", 380, 260, 240, 70, fill="#FFF7F3"),
        Box("mjpeg", "MJPEG\n/api/video/mjpeg", 380, 360, 240, 70, fill="#FFF7F3"),
        Box(
            "ctrl",
            "Контроллер шлюза\nFSM + политика",
            760,
            140,
            320,
            90,
            fill="#FFFBEA",
        ),
        Box("db", "SQLite БД\nusers/events", 720, 280, 240, 70, fill="#F7F7F7"),
        Box("vision", "Vision\n(dummy/OpenCV)", 1000, 280, 240, 70, fill="#F7F7F7"),
        Box(
            "hw",
            "Двери/датчики/сирена\n(sim/GPIO/Serial)",
            860,
            400,
            280,
            70,
            fill="#F7F7F7",
        ),
    ]
    arch_arrows = [
        Arrow("ui", "api", "HTTP /api/*"),
        Arrow("ui", "ws", "подписка"),
        Arrow("ui", "mjpeg", "поток"),
        Arrow("api", "ctrl", "вызовы"),
        Arrow("ctrl", "db", "чтение/запись"),
        Arrow("ctrl", "vision", "анализ помещения"),
        Arrow("ctrl", "hw", "блок/разблок"),
        Arrow("vision", "ctrl", "RoomAnalyzed"),
        Arrow("hw", "ctrl", "DoorClosedChanged"),
    ]
    arch_png = exports_dir / "structural.png"
    arch_svg = exports_dir / "structural.svg"
    arch_drawio = schemes_dir / "structural.drawio"
    save_block_diagram_png(
        arch_png,
        "Архитектура EyeGate Mantrap (структурная)",
        arch_boxes,
        arch_arrows,
        size=(1400, 650),
    )
    save_block_diagram_svg(
        arch_svg,
        "Архитектура EyeGate Mantrap (структурная)",
        arch_boxes,
        arch_arrows,
        size=(1400, 650),
    )
    write_drawio(arch_drawio, "Архитектура (структурная)", arch_boxes, arch_arrows)
    out["structural"] = {"png": arch_png, "svg": arch_svg, "drawio": arch_drawio}

    # 2) Electrical (block-level)
    el_boxes = [
        Box(
            "ctrl",
            "Контроллер\n(Luckfox Pico Ultra W)",
            80,
            160,
            300,
            100,
            fill="#F3FFF7",
        ),
        Box("lock1", "Замок Door1", 480, 120, 220, 70, fill="#FFFBEA"),
        Box("lock2", "Замок Door2", 480, 220, 220, 70, fill="#FFFBEA"),
        Box("sens1", "Датчик Door1\n(концевик)", 480, 320, 220, 70, fill="#F3F7FF"),
        Box("sens2", "Датчик Door2\n(концевик)", 480, 420, 220, 70, fill="#F3F7FF"),
        Box("alarm", "Сирена/ALARM", 480, 520, 220, 70, fill="#FFF7F3"),
        Box("cam", "USB камера (UVC)", 80, 320, 300, 70, fill="#F7F7F7"),
        Box("psu", "Питание\n(БП 12В/5В)", 80, 520, 300, 70, fill="#F7F7F7"),
    ]
    el_arrows = [
        Arrow("ctrl", "lock1", "GPIO lock1"),
        Arrow("ctrl", "lock2", "GPIO lock2"),
        Arrow("sens1", "ctrl", "GPIO door1_closed"),
        Arrow("sens2", "ctrl", "GPIO door2_closed"),
        Arrow("ctrl", "alarm", "GPIO alarm"),
        Arrow("cam", "ctrl", "USB"),
        Arrow("psu", "ctrl", "5V"),
        Arrow("psu", "lock1", "12V"),
        Arrow("psu", "lock2", "12V"),
    ]
    el_png = exports_dir / "electrical.png"
    el_svg = exports_dir / "electrical.svg"
    el_drawio = schemes_dir / "electrical.drawio"
    save_block_diagram_png(
        el_png,
        "Электрическая схема (принципиальная, блоковая)",
        el_boxes,
        el_arrows,
        size=(1100, 720),
    )
    save_block_diagram_svg(
        el_svg,
        "Электрическая схема (принципиальная, блоковая)",
        el_boxes,
        el_arrows,
        size=(1100, 720),
    )
    write_drawio(el_drawio, "Электрическая схема (Э3, блоковая)", el_boxes, el_arrows)
    out["electrical"] = {"png": el_png, "svg": el_svg, "drawio": el_drawio}

    # 3) FSM (states)
    fsm_boxes = [
        Box("IDLE", "IDLE\n(ожидание)", 70, 170, 190, 70, fill="#F3F7FF"),
        Box(
            "WAIT_ENTER",
            "WAIT_ENTER\n(ожидание входа)",
            300,
            170,
            250,
            70,
            fill="#F3F7FF",
        ),
        Box(
            "CHECK_ROOM",
            "CHECK_ROOM\n(проверка помещения)",
            580,
            170,
            270,
            70,
            fill="#FFFBEA",
        ),
        Box(
            "ACCESS_GRANTED",
            "ACCESS_GRANTED\n(доступ разрешен)",
            870,
            110,
            260,
            70,
            fill="#F3FFF7",
        ),
        Box(
            "ACCESS_DENIED",
            "ACCESS_DENIED\n(доступ запрещен)",
            870,
            230,
            260,
            70,
            fill="#FFF7F3",
        ),
        Box("ALARM", "ALARM\n(тревога)", 580, 320, 270, 70, fill="#FFF7F3"),
        Box("RESET", "RESET\n(сброс)", 300, 320, 250, 70, fill="#F7F7F7"),
    ]
    fsm_arrows = [
        Arrow("IDLE", "WAIT_ENTER", "Аутентификация OK"),
        Arrow("WAIT_ENTER", "CHECK_ROOM", "Door1 закрыта"),
        Arrow("CHECK_ROOM", "ACCESS_GRANTED", "Разрешено политикой"),
        Arrow("CHECK_ROOM", "ACCESS_DENIED", "Отказ/тайм-аут"),
        Arrow("CHECK_ROOM", "ALARM", "Тревога"),
        Arrow("ACCESS_GRANTED", "RESET", "Door2 закрыта"),
        Arrow("ALARM", "RESET", "Сброс/тайм-аут"),
        Arrow("RESET", "IDLE", "В IDLE"),
    ]
    fsm_png = exports_dir / "fsm.png"
    fsm_svg = exports_dir / "fsm.svg"
    fsm_drawio = schemes_dir / "fsm.drawio"
    save_block_diagram_png(
        fsm_png, "FSM шлюза EyeGate Mantrap", fsm_boxes, fsm_arrows, size=(1150, 520)
    )
    save_block_diagram_svg(
        fsm_svg, "FSM шлюза EyeGate Mantrap", fsm_boxes, fsm_arrows, size=(1150, 520)
    )
    write_drawio(fsm_drawio, "FSM шлюза", fsm_boxes, fsm_arrows)
    out["fsm"] = {"png": fsm_png, "svg": fsm_svg, "drawio": fsm_drawio}

    # 3a) Algorithms (ГОСТ 19.701-90, учебная блок-схема)
    algo1_boxes = [
        Box("start", "НАЧАЛО", 120, 90, 520, 60, fill="#F3F7FF", shape="rounded"),
        Box(
            "auth",
            "Аутентификация\n(PIN/логин/карта)",
            120,
            175,
            520,
            70,
            fill="#F3FFF7",
        ),
        Box(
            "dec_allow",
            "Доступ разрешён?",
            120,
            280,
            520,
            90,
            fill="#FFFBEA",
            shape="diamond",
        ),
        Box("unlock1", "Разблокировать Door1", 120, 405, 520, 70, fill="#F3FFF7"),
        Box("wait1", "Ожидать закрытия Door1", 120, 495, 520, 70, fill="#F7F7F7"),
        Box(
            "analyze",
            "Анализ помещения (Vision)\npeople_count + сопоставление лица",
            120,
            585,
            520,
            70,
            fill="#F7F7F7",
        ),
        Box(
            "dec_policy",
            "Политика допуска\nРАЗРЕШИТЬ / ОТКАЗ / ТРЕВОГА?",
            120,
            700,
            520,
            90,
            fill="#FFFBEA",
            shape="diamond",
        ),
        Box("unlock2", "Разблокировать Door2", 120, 825, 520, 70, fill="#F3FFF7"),
        Box("wait2", "Ожидать закрытия Door2", 120, 915, 520, 70, fill="#F7F7F7"),
        Box(
            "deny",
            "Отказ (ACCESS_DENIED)\n+ ожидание RESET",
            700,
            300,
            340,
            80,
            fill="#FFF7F3",
        ),
        Box(
            "alarm",
            "Тревога (ALARM)\nсирена/логирование",
            700,
            720,
            340,
            80,
            fill="#FFF7F3",
        ),
        Box(
            "reset",
            "RESET:\nLOCK_BOTH + очистка контекста",
            700,
            915,
            340,
            80,
            fill="#F7F7F7",
        ),
        Box("end", "КОНЕЦ", 120, 1010, 520, 60, fill="#F3F7FF", shape="rounded"),
    ]
    algo1_arrows = [
        Arrow("start", "auth"),
        Arrow("auth", "dec_allow"),
        Arrow("dec_allow", "unlock1", "да"),
        Arrow("dec_allow", "deny", "нет"),
        Arrow("unlock1", "wait1"),
        Arrow("wait1", "analyze"),
        Arrow("analyze", "dec_policy"),
        Arrow("dec_policy", "unlock2", "РАЗРЕШИТЬ"),
        Arrow("dec_policy", "alarm", "ТРЕВОГА"),
        Arrow("dec_policy", "deny", "ОТКАЗ"),
        Arrow("unlock2", "wait2"),
        Arrow("wait2", "reset"),
        Arrow("deny", "reset"),
        Arrow("alarm", "reset"),
        Arrow("reset", "end"),
    ]
    algo1_png = exports_dir / "algo_access.png"
    algo1_svg = exports_dir / "algo_access.svg"
    algo1_drawio = schemes_dir / "algo_access.drawio"
    save_block_diagram_png(
        algo1_png,
        "Схема алгоритма: цикл прохода через шлюз",
        algo1_boxes,
        algo1_arrows,
        size=(1100, 1120),
    )
    save_block_diagram_svg(
        algo1_svg,
        "Схема алгоритма: цикл прохода через шлюз",
        algo1_boxes,
        algo1_arrows,
        size=(1100, 1120),
    )
    write_drawio(
        algo1_drawio, "Алгоритм прохода (ГОСТ 19.701)", algo1_boxes, algo1_arrows
    )
    out["algo_access"] = {"png": algo1_png, "svg": algo1_svg, "drawio": algo1_drawio}

    algo2_boxes = [
        Box("start", "НАЧАЛО", 120, 100, 520, 60, fill="#F3F7FF", shape="rounded"),
        Box(
            "detect",
            "Фиксация нарушения\n(tailgating/unknown/timeout)",
            120,
            190,
            520,
            70,
            fill="#FFF7F3",
        ),
        Box(
            "alarm_on",
            "Включить ALARM\n(сирена/индикация)",
            120,
            280,
            520,
            70,
            fill="#FFF7F3",
        ),
        Box(
            "log", "Записать событие в БД\n(events)", 120, 370, 520, 70, fill="#F7F7F7"
        ),
        Box(
            "wait",
            "Сброс получен\nили TIMEOUT_ALARM?",
            120,
            480,
            520,
            90,
            fill="#FFFBEA",
            shape="diamond",
        ),
        Box(
            "reset",
            "RESET:\nALARM OFF + LOCK_BOTH\n+ отмена таймаутов",
            700,
            370,
            340,
            90,
            fill="#F7F7F7",
        ),
        Box("end", "КОНЕЦ", 120, 610, 520, 60, fill="#F3F7FF", shape="rounded"),
    ]
    algo2_arrows = [
        Arrow("start", "detect"),
        Arrow("detect", "alarm_on"),
        Arrow("alarm_on", "log"),
        Arrow("log", "wait"),
        Arrow("wait", "reset", "да"),
        Arrow("reset", "end"),
        Arrow("wait", "wait", "нет"),
    ]
    algo2_png = exports_dir / "algo_alarm.png"
    algo2_svg = exports_dir / "algo_alarm.svg"
    algo2_drawio = schemes_dir / "algo_alarm.drawio"
    save_block_diagram_png(
        algo2_png,
        "Схема алгоритма: обработка тревоги и сброс",
        algo2_boxes,
        algo2_arrows,
        size=(1100, 720),
    )
    save_block_diagram_svg(
        algo2_svg,
        "Схема алгоритма: обработка тревоги и сброс",
        algo2_boxes,
        algo2_arrows,
        size=(1100, 720),
    )
    write_drawio(
        algo2_drawio, "Алгоритм ALARM/RESET (ГОСТ 19.701)", algo2_boxes, algo2_arrows
    )
    out["algo_alarm"] = {"png": algo2_png, "svg": algo2_svg, "drawio": algo2_drawio}

    # 4) Software modules structure
    sw_boxes = [
        Box("server", "server/\nFastAPI сервер", 80, 160, 300, 90, fill="#F3FFF7"),
        Box(
            "web",
            "web/app/\nReact/Vite SPA\n(клиент)",
            80,
            320,
            300,
            100,
            fill="#F3F7FF",
        ),
        Box("gate", "gate/\nFSM + контроллер", 520, 160, 320, 90, fill="#FFFBEA"),
        Box("policy", "policy/\nправила доступа", 520, 290, 320, 70, fill="#F7F7F7"),
        Box("db", "db/\nSQLite модели", 520, 390, 320, 70, fill="#F7F7F7"),
        Box(
            "vision",
            "vision/\nанализ + сопоставление",
            900,
            150,
            360,
            90,
            fill="#F7F7F7",
        ),
        Box("hw", "hw/\nдвери/датчики/сирена", 900, 290, 360, 80, fill="#F7F7F7"),
    ]
    sw_arrows = [
        Arrow("web", "server", "HTTP/WS"),
        Arrow("server", "gate", "вызовы"),
        Arrow("gate", "policy", "решение"),
        Arrow("gate", "vision", "analyze_room()"),
        Arrow("gate", "hw", "управление"),
        Arrow("gate", "db", "логирование"),
    ]
    sw_png = exports_dir / "software_struct.png"
    sw_svg = exports_dir / "software_struct.svg"
    sw_drawio = schemes_dir / "software_struct.drawio"
    save_block_diagram_png(
        sw_png,
        "Структурная схема ПО EyeGate Mantrap",
        sw_boxes,
        sw_arrows,
        size=(1400, 650),
    )
    save_block_diagram_svg(
        sw_svg,
        "Структурная схема ПО EyeGate Mantrap",
        sw_boxes,
        sw_arrows,
        size=(1400, 650),
    )
    write_drawio(sw_drawio, "Структурная схема ПО", sw_boxes, sw_arrows)
    out["software_struct"] = {"png": sw_png, "svg": sw_svg, "drawio": sw_drawio}

    # 5) Physical layout (assembly sketch)
    lay_boxes = [
        Box("door1", "Door1\n(вход)", 80, 220, 180, 120, fill="#F3F7FF"),
        Box(
            "chamber",
            "Камера шлюза\n(mantrap zone)",
            300,
            190,
            320,
            180,
            fill="#FFFBEA",
        ),
        Box("door2", "Door2\n(выход)", 660, 220, 180, 120, fill="#F3F7FF"),
        Box("cam", "Камера\n(UVC)", 380, 110, 160, 60, fill="#F7F7F7"),
        Box("ctrl", "Контроллер\n(Luckfox)", 380, 400, 160, 70, fill="#F3FFF7"),
    ]
    lay_arrows = [
        Arrow("door1", "chamber", "проход"),
        Arrow("chamber", "door2", "проход"),
        Arrow("cam", "chamber", "FOV"),
        Arrow("ctrl", "door1", "lock/sensor"),
        Arrow("ctrl", "door2", "lock/sensor"),
        Arrow("ctrl", "cam", "USB"),
    ]
    lay_png = exports_dir / "layout.png"
    lay_svg = exports_dir / "layout.svg"
    lay_drawio = schemes_dir / "layout.drawio"
    save_block_diagram_png(
        lay_png,
        "Эскиз компоновки шлюза (mantrap)",
        lay_boxes,
        lay_arrows,
        size=(1100, 650),
    )
    save_block_diagram_svg(
        lay_svg,
        "Эскиз компоновки шлюза (mantrap)",
        lay_boxes,
        lay_arrows,
        size=(1100, 650),
    )
    write_drawio(lay_drawio, "Компоновка шлюза (эскиз)", lay_boxes, lay_arrows)
    out["layout"] = {"png": lay_png, "svg": lay_svg, "drawio": lay_drawio}

    # 6) Controller board (educational sketch)
    board_boxes = [
        Box(
            "board",
            "Центральный контроллер\n(плата/модуль)\n\nGPIO: lock1/lock2, door1_closed/door2_closed\nALARM GPIO\nUSB: camera\nUART/COM: SerialBridge (опц.)",
            140,
            170,
            820,
            360,
            fill="#F7F7F7",
            shape="rounded",
        ),
        Box("conn_pwr", "Питание", 120, 560, 200, 70, fill="#F7F7F7"),
        Box("conn_usb", "USB", 450, 560, 200, 70, fill="#F7F7F7"),
        Box("conn_gpio", "GPIO", 780, 560, 200, 70, fill="#F7F7F7"),
    ]
    board_arrows = [
        Arrow("conn_pwr", "board"),
        Arrow("conn_usb", "board"),
        Arrow("conn_gpio", "board"),
    ]
    board_png = exports_dir / "controller_board.png"
    board_svg = exports_dir / "controller_board.svg"
    board_drawio = schemes_dir / "controller_board.drawio"
    save_block_diagram_png(
        board_png,
        "Эскиз: центральный контроллер (плата)",
        board_boxes,
        board_arrows,
        size=(1100, 720),
    )
    save_block_diagram_svg(
        board_svg,
        "Эскиз: центральный контроллер (плата)",
        board_boxes,
        board_arrows,
        size=(1100, 720),
    )
    write_drawio(board_drawio, "Плата контроллера (эскиз)", board_boxes, board_arrows)
    out["controller_board"] = {
        "png": board_png,
        "svg": board_svg,
        "drawio": board_drawio,
    }

    # 7) Data flow (context of protocols)
    df_boxes = [
        Box(
            "user", "Пользователь/Оператор\n(браузер)", 80, 140, 260, 90, fill="#F3F7FF"
        ),
        Box(
            "spa",
            "Интерфейс (SPA)\n/monitor,/sim,/kiosk",
            80,
            260,
            260,
            90,
            fill="#F3F7FF",
        ),
        Box(
            "api", "Сервер FastAPI\nserver/main.py", 450, 220, 320, 110, fill="#F3FFF7"
        ),
        Box("ws", "WebSocket\n/ws/status", 450, 360, 320, 80, fill="#F3FFF7"),
        Box("mjpeg", "MJPEG\n/api/video/mjpeg", 450, 470, 320, 80, fill="#F3FFF7"),
        Box(
            "vision",
            "Vision\n(dummy/real)\n(анализ)",
            850,
            140,
            420,
            100,
            fill="#F7F7F7",
        ),
        Box(
            "hw",
            "Двери/датчики/сирена\n(SIM/Serial)",
            850,
            280,
            420,
            90,
            fill="#F7F7F7",
        ),
        Box("db", "SQLite БД\nusers/events", 850, 420, 420, 90, fill="#F7F7F7"),
    ]
    df_arrows = [
        Arrow("user", "spa", "UI"),
        Arrow("spa", "api", "HTTP JSON (/api/*), запросы"),
        Arrow("api", "ws", "статус"),
        Arrow("ws", "spa", "WS"),
        Arrow("api", "mjpeg", "кадры"),
        Arrow("mjpeg", "spa", "MJPEG"),
        Arrow("api", "vision", "analyze_room"),
        Arrow("vision", "api", "people/face"),
        Arrow("api", "db", "users/events"),
        Arrow("api", "hw", "замки/датчики"),
        Arrow("hw", "api", "события"),
    ]
    df_png = exports_dir / "dataflow.png"
    df_svg = exports_dir / "dataflow.svg"
    df_drawio = schemes_dir / "dataflow.drawio"
    save_block_diagram_png(
        df_png,
        "Поток данных и протоколы EyeGate Mantrap",
        df_boxes,
        df_arrows,
        size=(1400, 700),
    )
    save_block_diagram_svg(
        df_svg,
        "Поток данных и протоколы EyeGate Mantrap",
        df_boxes,
        df_arrows,
        size=(1400, 700),
    )
    write_drawio(df_drawio, "Поток данных и протоколы", df_boxes, df_arrows)
    out["dataflow"] = {"png": df_png, "svg": df_svg, "drawio": df_drawio}

    # Posters (24_*) — simple exports reuse diagrams at higher resolution
    posters_dir = docs_root / "24_ПЛАКАТЫ_И_СХЕМЫ"
    posters_dir.mkdir(parents=True, exist_ok=True)
    save_block_diagram_png(
        posters_dir / "PLAKAT_01_ARCHITECTURE.png",
        "Плакат: Архитектура EyeGate Mantrap",
        arch_boxes,
        arch_arrows,
        size=(1600, 900),
    )
    save_block_diagram_png(
        posters_dir / "PLAKAT_02_FSM.png",
        "Плакат: FSM шлюза EyeGate Mantrap",
        fsm_boxes,
        fsm_arrows,
        size=(1600, 900),
    )
    save_block_diagram_png(
        posters_dir / "PLAKAT_03_ELECTRICAL.png",
        "Плакат: Электрическая схема (блоковая)",
        el_boxes,
        el_arrows,
        size=(1600, 950),
    )
    save_block_diagram_png(
        posters_dir / "PLAKAT_04_SOFTWARE.png",
        "Плакат: Структура ПО",
        sw_boxes,
        sw_arrows,
        size=(1600, 900),
    )
    save_block_diagram_png(
        posters_dir / "PLAKAT_05_DATAFLOW.png",
        "Плакат: Поток данных и протоколы",
        df_boxes,
        df_arrows,
        size=(1600, 950),
    )
    save_block_diagram_png(
        posters_dir / "PLAKAT_06_LAYOUT.png",
        "Плакат: Макет/компоновка шлюза",
        lay_boxes,
        lay_arrows,
        size=(1600, 900),
    )

    # Optional PDF posters (image-only PDF)
    for name in (
        "PLAKAT_01_ARCHITECTURE",
        "PLAKAT_02_FSM",
        "PLAKAT_03_ELECTRICAL",
        "PLAKAT_04_SOFTWARE",
        "PLAKAT_05_DATAFLOW",
        "PLAKAT_06_LAYOUT",
    ):
        png = posters_dir / f"{name}.png"
        pdf = posters_dir / f"{name}.pdf"
        try:
            im = Image.open(png)
            im.save(pdf, "PDF", resolution=150.0)
        except Exception:
            pass

    return out
