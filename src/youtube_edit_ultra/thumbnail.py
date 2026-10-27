"""Create a readable source-derived thumbnail without replacing faces."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .planner import Edit


def create_thumbnail(edit: Edit, title: str, out: Path, *, width: int = 1280,
                     height: int = 720) -> Path:
    import subprocess
    at = edit.source_peak if edit.source_peak is not None else (edit.source_start + edit.source_end) / 2
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.3f}",
                           "-i", edit.source, "-frames:v", "1", "-vf",
                           f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
                           "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                          capture_output=True, check=True)
    img = Image.open(io.BytesIO(proc.stdout)).convert("RGB")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    start = int(height * 0.68)
    for y in range(start, height):
        # Gradient ONLY in lower 32%, no synthetic faces/body manipulation.
        alpha = int(125 * (y - start) / max(1, height - start))
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    font_paths = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    font = None
    for size in (72, 64, 56, 48, 42):
        for path in font_paths:
            if Path(path).is_file():
                candidate = ImageFont.truetype(path, size)
                if draw.textbbox((0, 0), title.upper(), font=candidate, stroke_width=2)[2] <= width - 90:
                    font = candidate
                    break
        if font:
            break
    font = font or ImageFont.load_default()
    label = title.upper()[:90]
    # Pillow's "mm" anchor expects the text centre, not its left edge.
    x = width // 2
    y = int(height * .84)
    draw.text((x, y), label, font=font, fill=(245, 245, 245, 255),
              stroke_width=3, stroke_fill=(6, 8, 12, 230), anchor="mm")
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out


def create_storyboard(edits: list[Edit], out: Path, *, columns: int = 3,
                      rows: int = 4) -> Path:
    """A contact sheet of ACTUAL source frames, useful for manual action QA."""
    import subprocess
    if not edits:
        raise ValueError("Timeline vide")
    selected = [e for e in edits if e.source_peak is not None]
    if not selected:
        selected = edits
    indices = [min(len(selected) - 1, int(i * len(selected) / (columns * rows)))
               for i in range(columns * rows)]
    cellw, cellh = 320, 215
    canvas = Image.new("RGB", (columns * cellw, rows * cellh), (12, 15, 21))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for n, i in enumerate(indices):
        edit = selected[i]
        at = edit.source_peak or (edit.source_start + edit.source_end) / 2
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.3f}",
               "-i", edit.source, "-frames:v", "1", "-vf",
               "scale=320:180:force_original_aspect_ratio=increase,crop=320:180",
               "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode or not proc.stdout:
            continue
        image = Image.open(io.BytesIO(proc.stdout)).convert("RGB")
        x, y = (n % columns) * cellw, (n // columns) * cellh
        canvas.paste(image, (x, y))
        description = (f"{edit.timeline_start:.0f}s  " + edit.label.replace("_", " "))[:47]
        draw.text((x + 5, y + 187), description, font=font, fill=(245, 245, 245))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, format="JPEG", quality=84)
    return out
