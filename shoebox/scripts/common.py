"""Shared helpers for the shoebox scripts."""
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMAGE_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}

# Clockwise rotation needed to display the stored pixels upright -> EXIF Orientation value.
ROTATE_CW_TO_ORIENTATION = {0: 1, 90: 6, 180: 3, 270: 8}
ORIENTATION_TO_ROTATE_CW = {v: k for k, v in ROTATE_CW_TO_ORIENTATION.items()}

# PIL transpose ops that rotate an image clockwise by the given degrees.
CW_TRANSPOSE = {
    90: Image.Transpose.ROTATE_270,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}


def rotate_cw(img, degrees):
    degrees %= 360
    return img if degrees == 0 else img.transpose(CW_TRANSPOSE[degrees])


def work_dir(out_dir):
    return Path(out_dir) / ".shoebox"


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def open_rgb(path, max_side=None):
    img = Image.open(path)
    img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return img


def contact_sheet(items, out_path, thumb=220, cols=6, title=None):
    """items: list of (PIL.Image, label). Writes a labeled grid JPEG."""
    if not items:
        return None
    font = ImageFont.load_default()
    label_h = 16
    title_h = 24 if title else 0
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb, title_h + rows * (thumb + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((6, 4), title, fill="black", font=font)
    for i, (img, label) in enumerate(items):
        t = img.copy()
        t.thumbnail((thumb - 6, thumb - 6))
        r, c = divmod(i, cols)
        x = c * thumb + (thumb - t.width) // 2
        y = title_h + r * (thumb + label_h) + (thumb - t.height) // 2
        sheet.paste(t, (x, y))
        draw.text((c * thumb + 4, title_h + r * (thumb + label_h) + thumb), str(label)[:34],
                  fill="black", font=font)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=85)
    return str(out_path)
