#!/usr/bin/env python3
"""Pair FastFoto scans (front _a, back _b, optional unsuffixed original) and build previews.

Usage: inventory.py SRC_DIR OUT_DIR

Writes OUT_DIR/.shoebox/manifest.json, previews/ and sheets/blank_backs_*.jpg.
Previews keep the stored pixel orientation (EXIF orientation is NOT applied) so that
any rotation judged from a preview is relative to the stored pixels.
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from common import IMAGE_EXTS, ORIENTATION_TO_ROTATE_CW, contact_sheet, open_rgb, save_json, work_dir  # noqa: E402

NAME_RE = re.compile(r"^(?P<stem>.+?)(?:_(?P<side>[abAB]))?$")
FRONT_PREVIEW = 1280
BACK_PREVIEW = 2000  # larger so faint handwriting stays legible
BLANK_INK = 0.0025   # fraction of dark pixels below which a back is probably blank


def ink_score(img):
    """Rough fraction of 'ink' pixels on a back, ignoring a margin for scanner edges."""
    g = np.asarray(img.convert("L").resize((400, int(400 * img.height / img.width) or 1)), dtype=np.float32)
    h, w = g.shape
    m = max(2, int(min(h, w) * 0.04))
    g = g[m:h - m, m:w - m]
    if g.size == 0:
        return 0.0
    paper = np.median(g)
    return float((g < paper - 45).mean())


def exif_summary(path):
    try:
        with Image.open(path) as im:
            ex = im.getexif()
            w, h = im.size
            orient = ex.get(0x0112, 1)
            dto = ex.get_ifd(0x8769).get(0x9003) or ex.get(0x0132)
        return {"width": w, "height": h, "existing_orientation": orient,
                "existing_rotate_cw": ORIENTATION_TO_ROTATE_CW.get(orient, 0),
                "existing_datetime": dto}
    except Exception as e:  # unreadable file: still list it so the user hears about it
        return {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    a = ap.parse_args()
    src, out = Path(a.src).resolve(), Path(a.out).resolve()
    wd = work_dir(out)
    (wd / "previews").mkdir(parents=True, exist_ok=True)

    groups = {}
    for p in sorted(src.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS or out in p.parents:
            continue
        m = NAME_RE.match(p.stem)
        side = (m.group("side") or "").lower()
        key = (str(p.parent.relative_to(src)), m.group("stem"))
        groups.setdefault(key, {})[{"a": "front", "b": "back", "": "original"}[side]] = p

    photos, orphans_back = [], []
    for seq, ((rel, stem), g) in enumerate(sorted(groups.items())):
        front = g.get("front") or g.get("original")
        if not front:
            orphans_back.append(str(g["back"]))
            continue
        pid = (stem if rel == "." else f"{rel}/{stem}").replace("/", "__")
        rec = {"id": pid, "seq": seq, "rel_dir": rel,
               "front": str(front),
               "original": str(g["original"]) if "front" in g and "original" in g else None,
               "back": str(g["back"]) if "back" in g else None}
        rec.update(exif_summary(front))
        pf = wd / "previews" / f"{pid}_front.jpg"
        open_rgb(front, FRONT_PREVIEW).save(pf, quality=85)
        rec["preview_front"] = str(pf)
        if rec["back"]:
            bimg = open_rgb(rec["back"], BACK_PREVIEW)
            pb = wd / "previews" / f"{pid}_back.jpg"
            bimg.save(pb, quality=88)
            rec["preview_back"] = str(pb)
            rec["back_ink"] = round(ink_score(bimg), 5)
            rec["back_likely_blank"] = rec["back_ink"] < BLANK_INK
        photos.append(rec)

    # One sheet per 30 probably-blank backs so they can be confirmed at a glance.
    blanks = [p for p in photos if p.get("back_likely_blank")]
    sheets = []
    for i in range(0, len(blanks), 30):
        items = [(open_rgb(p["preview_back"], 400), p["id"]) for p in blanks[i:i + 30]]
        sheets.append(contact_sheet(items, wd / "sheets" / f"blank_backs_{i // 30 + 1}.jpg",
                                    title="Probably blank backs - check for faint writing"))

    manifest = {"source": str(src), "out": str(out), "photos": photos,
                "orphan_backs": orphans_back, "blank_back_sheets": sheets}
    save_json(wd / "manifest.json", manifest)
    with_back = sum(1 for p in photos if p["back"])
    print(f"{len(photos)} photos ({with_back} with backs, {len(blanks)} backs look blank, "
          f"{len(orphans_back)} orphan backs). Manifest: {wd / 'manifest.json'}")


if __name__ == "__main__":
    main()
