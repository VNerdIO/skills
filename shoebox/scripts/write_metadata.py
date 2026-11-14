#!/usr/bin/env python3
"""Copy scans to OUT_DIR and write metadata from .shoebox/records/<id>.json via exiftool.

Usage: write_metadata.py OUT_DIR [--dry-run] [--only ID ...]

Originals are never modified: front and unsuffixed original are copied into
OUT_DIR/<rel_dir>/ first, then tagged. Backs are left out (their writing is transcribed onto
the front) unless the record sets "keep_back": true; stale back copies are removed. Also writes OUT_DIR/shoebox_report.{csv,md}.
See references/metadata.md for the record schema and the tag mapping.
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROTATE_CW_TO_ORIENTATION, load_json, work_dir  # noqa: E402

TAGGED_CONF = {"high", "medium"}  # people at low confidence go to the report, not the tags


def exif_datetime(value, precision):
    """Fill a partial ISO date to a full EXIF timestamp, picking a midpoint for the unknown part."""
    parts = (value or "").split("-")
    y = parts[0]
    m = parts[1] if len(parts) > 1 else "07"
    d = parts[2] if len(parts) > 2 else ("15" if len(parts) > 1 else "01")
    return f"{y}:{m}:{d} 12:00:00"


def xmp_date(value, precision):
    parts = (value or "").split("-")
    keep = {"day": 3, "month": 2, "season": 2}.get(precision, 1)
    return ":".join(parts[:keep])


def describe_date(dt):
    v, prec, circa = dt.get("value"), dt.get("precision", "year"), dt.get("circa_years") or 0
    s = {"decade": f"{str(v)[:3]}0s"}.get(prec, v)
    if circa and prec != "decade":
        s = f"c. {s} (+/-{circa}y)"
    return s


def build_tags(rec, front=True):
    t = {}
    notes = []
    dt = rec.get("date") or {}
    if dt.get("value"):
        prec = dt.get("precision", "year")
        t["EXIF:DateTimeOriginal"] = exif_datetime(dt["value"], prec)
        t["XMP-exif:DateTimeOriginal"] = t["EXIF:DateTimeOriginal"]
        t["XMP-photoshop:DateCreated"] = xmp_date(dt["value"], prec)
        notes.append(f"Date {describe_date(dt)} [{dt.get('confidence', '?')}]: {dt.get('basis', '')}")
    loc = rec.get("location") or {}
    if loc.get("name") or loc.get("city"):
        for src, tags in (("sublocation", ["XMP-iptcCore:Location", "IPTC:Sub-location"]),
                          ("city", ["XMP-photoshop:City", "IPTC:City"]),
                          ("state", ["XMP-photoshop:State", "IPTC:Province-State"]),
                          ("country", ["XMP-photoshop:Country", "IPTC:Country-PrimaryLocationName"])):
            val = loc.get(src) or (loc.get("name") if src == "sublocation" else None)
            for tag in tags:
                if val:
                    t[tag] = val
        if loc.get("lat") is not None and loc.get("lon") is not None and loc.get("confidence") != "low":
            t["EXIF:GPSLatitude"], t["EXIF:GPSLatitudeRef"] = abs(loc["lat"]), "N" if loc["lat"] >= 0 else "S"
            t["EXIF:GPSLongitude"], t["EXIF:GPSLongitudeRef"] = abs(loc["lon"]), "E" if loc["lon"] >= 0 else "W"
        notes.append(f"Location {loc.get('name') or loc.get('city')} [{loc.get('confidence', '?')}]: "
                     f"{loc.get('basis', '')}")

    keywords = list(rec.get("keywords") or [])
    if dt.get("value"):
        if dt.get("precision") != "day" or dt.get("circa_years"):
            keywords.append("shoebox:date-approximate")
        if dt.get("source") == "inferred":
            keywords.append("shoebox:date-inferred")
    if rec.get("event"):
        keywords.append(rec["event"])
    for k in ("city", "state", "country"):
        if loc.get(k):
            keywords.append(loc[k])

    text = (rec.get("transcription") or "").strip()
    if front:
        rot = int(rec.get("rotate_cw", 0)) % 360
        t["EXIF:Orientation#"] = ROTATE_CW_TO_ORIENTATION[rot]
        # FastFoto leaves a stale XMP-tiff:Orientation that XMP-first apps (Lightroom, digiKam) honor
        # over EXIF, so keep the two in agreement.
        t["XMP-tiff:Orientation#"] = ROTATE_CW_TO_ORIENTATION[rot]
        people = [p for p in rec.get("people", []) if p.get("name") and p.get("confidence") in TAGGED_CONF]
        names = list(dict.fromkeys(p["name"] for p in people))
        if names:
            t["XMP-iptcExt:PersonInImage"] = names
            keywords += names
        boxed = [p for p in people if p.get("box")]
        if boxed and rec.get("_dims"):
            W, H = rec["_dims"]
            if rot in (90, 270):
                W, H = H, W  # regions are in the upright frame
            t["XMP-mwg-rs:RegionInfo"] = {
                "AppliedToDimensions": {"W": W, "H": H, "Unit": "pixel"},
                "RegionList": [{"Name": p["name"], "Type": "Face",
                                "Area": {"X": round(p["box"][0] + p["box"][2] / 2, 4),
                                         "Y": round(p["box"][1] + p["box"][3] / 2, 4),
                                         "W": p["box"][2], "H": p["box"][3], "Unit": "normalized"}}
                               for p in boxed]}
            t["XMP-MP:RegionInfoMP"] = {"Regions": [
                {"PersonDisplayName": p["name"],
                 "Rectangle": ", ".join(str(round(v, 4)) for v in p["box"])} for p in boxed]}
        low = [p for p in rec.get("people", []) if p.get("name") and p.get("confidence") == "low"]
        if low:
            notes.append("Possibly also: " + ", ".join(p["name"] for p in low))
        if people:
            notes.append("People: " + "; ".join(f"{p['name']} [{p['confidence']}] {p.get('basis', '')}"
                                                 for p in people))
        if text:
            for tag in ("EXIF:ImageDescription", "XMP-dc:Description", "IPTC:Caption-Abstract"):
                t[tag] = text
        elif rec.get("caption"):
            t["XMP-dc:Title"] = rec["caption"]
        if rec.get("_back_name"):
            notes.append(f"Back scan: {rec['_back_name']}" + ("" if rec.get("keep_back") else " (source folder)"))
    else:
        t["XMP-dc:Description"] = f"Back of {rec.get('_front_name', '')}" + (f". Reads: {text}" if text else "")

    if keywords:
        t["XMP-dc:Subject"] = list(dict.fromkeys(keywords))
        t["IPTC:Keywords"] = t["XMP-dc:Subject"]
    if notes:
        t["EXIF:UserComment"] = "shoebox: " + " | ".join(notes)
    t["IPTC:CodedCharacterSet"] = "UTF8"
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    wd = work_dir(out)
    manifest = load_json(wd / "manifest.json")
    if not manifest:
        sys.exit("Run inventory.py first.")

    jobs, report, missing = [], [], []
    for p in manifest["photos"]:
        if a.only and p["id"] not in a.only:
            continue
        rec = load_json(wd / "records" / f"{p['id']}.json")
        if rec is None:
            missing.append(p["id"])
            continue
        dest_dir = out / p["rel_dir"]
        rec["_dims"] = (p.get("width"), p.get("height"))
        rec["_front_name"] = Path(p["front"]).name
        rec["_back_name"] = Path(p["back"]).name if p.get("back") else None
        targets = [(p["front"], True)]
        if p.get("original"):
            targets.append((p["original"], True))
        if p.get("back"):
            # The transcription lives on the front, so the back is only copied when the record
            # asks for it (e.g. writing that still needs a second look). Clear stale copies.
            back_dest = dest_dir / Path(p["back"]).name
            if rec.get("keep_back"):
                targets.append((p["back"], False))
            elif back_dest.exists() and not a.dry_run:
                back_dest.unlink()
        for src, is_front in targets:
            dest = dest_dir / Path(src).name
            tags = build_tags(rec, front=is_front)
            if src == p.get("original"):
                tags.pop("XMP-mwg-rs:RegionInfo", None)  # original may differ in crop/size
                tags.pop("XMP-MP:RegionInfoMP", None)
            jobs.append((src, dest, tags))
        dt, loc = rec.get("date") or {}, rec.get("location") or {}
        report.append({
            "id": p["id"], "front": rec["_front_name"], "rotate_cw": rec.get("rotate_cw", 0),
            "date": describe_date(dt) if dt.get("value") else "", "date_confidence": dt.get("confidence", ""),
            "date_basis": dt.get("basis", ""), "location": loc.get("name") or loc.get("city") or "",
            "people": "; ".join(f"{x['name']} ({x.get('confidence')})" for x in rec.get("people", []) if x.get("name")),
            "unknown_faces": sum(1 for x in rec.get("people", []) if not x.get("name")),
            "event": rec.get("event", ""), "transcription": (rec.get("transcription") or "").replace("\n", " / "),
        })

    if a.dry_run:
        print(json.dumps([{"dest": str(d), "tags": t} for _, d, t in jobs], indent=2, ensure_ascii=False))
        return

    payload = []
    for src, dest, tags in jobs:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        payload.append({"SourceFile": str(dest), **tags})
    if payload:
        jpath = wd / "exiftool_payload.json"
        jpath.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(["exiftool", "-overwrite_original", "-m", f"-j={jpath}"] + [x["SourceFile"] for x in payload],
                           capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0 or r.stderr.strip():
            print(r.stderr.strip(), file=sys.stderr)

    cols = list(report[0].keys()) if report else []
    with open(out / "shoebox_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(report)
    with open(out / "shoebox_report.md", "w", encoding="utf-8") as f:
        f.write(f"# Shoebox report\n\n{len(report)} photos written to `{out}`.\n\n")
        if missing:
            f.write(f"**No record (not tagged, not copied):** {', '.join(missing)}\n\n")
        f.write("| Photo | Date | Location | People | Back says |\n|---|---|---|---|---|\n")
        for r in report:
            cell = lambda s: str(s).replace("|", "/")  # noqa: E731
            f.write(f"| {cell(r['front'])} | {cell(r['date'])} {('(' + r['date_confidence'] + ')') if r['date'] else ''} "
                    f"| {cell(r['location'])} | {cell(r['people'])} | {cell(r['transcription'][:120])} |\n")
    print(f"Tagged {len(payload)} files for {len(report)} photos; {len(missing)} photos lack records. "
          f"Report: {out / 'shoebox_report.md'}")


if __name__ == "__main__":
    main()
