#!/usr/bin/env python3
"""Local face detection, orientation hints and clustering for a shoebox batch.

  faces.py scan OUT_DIR [--known ~/.shoebox/known_faces.json] [--threshold 0.5]
      Detects faces on every front at 0/90/180/270 degrees (the rotation with the most
      faces is the orientation hint), encodes faces at that rotation, clusters them, and
      writes .shoebox/faces/{faces.json,clusters.json} plus contact sheets of body crops
      (face + clothing) per cluster in .shoebox/sheets/.

  faces.py remember OUT_DIR [--known ...]
      Reads the finished records and appends the encodings of every named face_id to the
      known-faces library, so later batches get name suggestions automatically.

Boxes are [x, y, w, h], top-left origin, normalized 0-1, in the UPRIGHT (rotated) frame.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import contact_sheet, load_json, open_rgb, rotate_cw, save_json, work_dir  # noqa: E402

DETECT_SIDE = 1600
DEFAULT_KNOWN = Path.home() / ".shoebox" / "known_faces.json"


def require_fr():
    import warnings
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
    try:
        import face_recognition  # noqa: F401
        return face_recognition
    except ImportError:
        sys.exit("face_recognition is not installed; skip local face matching and rely on vision.")


def cluster(encodings, threshold):
    if not encodings:
        return []
    try:
        import dlib
        vecs = [dlib.vector(list(map(float, e))) for e in encodings]
        return list(dlib.chinese_whispers_clustering(vecs, threshold))
    except Exception:
        # Fallback: union-find on pairwise distance (can chain; threshold kept strict).
        X = np.asarray(encodings)
        parent = list(range(len(X)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i in range(len(X)):
            d = np.linalg.norm(X[i + 1:] - X[i], axis=1)
            for j in np.nonzero(d < threshold)[0]:
                parent[find(i)] = find(i + 1 + j)
        return [find(i) for i in range(len(X))]


def body_crop(img, box):
    """Face plus torso: wide enough for shoulders, tall enough for shirt/dress."""
    x, y, w, h = box
    W, H = img.size
    l, r = (x - 1.0 * w) * W, (x + 2.0 * w) * W
    t, b = (y - 0.4 * h) * H, (y + 4.5 * h) * H
    return img.crop((max(0, int(l)), max(0, int(t)), min(W, int(r)), min(H, int(b))))


def scan(a):
    fr = require_fr()
    wd = work_dir(a.out)
    manifest = load_json(wd / "manifest.json")
    if not manifest:
        sys.exit("Run inventory.py first.")
    known = load_json(a.known, {}) or {}

    faces, orient = [], {}
    crops = {}
    for n, p in enumerate(manifest["photos"], 1):
        img = open_rgb(p["front"], DETECT_SIDE)
        counts, locs = {}, {}
        for deg in (0, 90, 180, 270):
            r = rotate_cw(img, deg)
            locs[deg] = fr.face_locations(np.asarray(r), number_of_times_to_upsample=1, model="hog")
            counts[deg] = len(locs[deg])
        best = max((0, 90, 180, 270), key=lambda d: (counts[d], d == 0))
        orient[p["id"]] = {"rotate_cw_hint": best, "faces_by_rotation": counts,
                           "hint_strength": "none" if counts[best] == 0 else
                           ("weak" if sorted(counts.values())[-2] == counts[best] else "strong")}
        up = rotate_cw(img, best)
        arr = np.asarray(up)
        encs = fr.face_encodings(arr, known_face_locations=locs[best], num_jitters=1)
        W, H = up.size
        for (t, rgt, b, l), e in zip(locs[best], encs):
            fid = f"f{len(faces):05d}"
            box = [round(l / W, 4), round(t / H, 4), round((rgt - l) / W, 4), round((b - t) / H, 4)]
            faces.append({"face_id": fid, "photo_id": p["id"], "box": box,
                          "rotate_cw": best, "encoding": [round(float(v), 5) for v in e]})
            crops[fid] = body_crop(up, box)
        if n % 25 == 0:
            print(f"  {n}/{len(manifest['photos'])} photos scanned, {len(faces)} faces", file=sys.stderr)

    labels = cluster([f["encoding"] for f in faces], a.threshold)
    by = {}
    for f, lab in zip(faces, labels):
        by.setdefault(lab, []).append(f)
    groups = sorted(by.values(), key=len, reverse=True)

    known_vecs = {name: np.asarray(v) for name, v in known.items() if v}
    clusters, singles = [], []
    for i, members in enumerate(groups):
        if len(members) == 1:
            members[0]["cluster_id"] = None
            singles.append(members[0])
            continue
        cid = f"c{i:03d}"
        for f in members:
            f["cluster_id"] = cid
        c = {"cluster_id": cid, "size": len(members),
             "face_ids": [f["face_id"] for f in members],
             "photo_ids": sorted({f["photo_id"] for f in members})}
        mean = np.mean([f["encoding"] for f in members], axis=0)
        best = min(((float(np.min(np.linalg.norm(v - mean, axis=1))), nm) for nm, v in known_vecs.items()),
                   default=None)
        if best and best[0] < 0.45:
            c["suggested_name"], c["suggested_distance"] = best[1], round(best[0], 3)
        c["sheet"] = contact_sheet([(crops[f["face_id"]], f"{f['face_id']} {f['photo_id']}") for f in members[:36]],
                                   wd / "sheets" / f"cluster_{cid}.jpg",
                                   title=f"{cid}: {len(members)} faces" +
                                         (f" - suggested {c['suggested_name']}" if "suggested_name" in c else ""))
        clusters.append(c)
    for f in singles:
        if known_vecs:
            d, nm = min((float(np.min(np.linalg.norm(v - np.asarray(f["encoding"]), axis=1))), nm)
                        for nm, v in known_vecs.items())
            if d < 0.45:
                f["suggested_name"], f["suggested_distance"] = nm, round(d, 3)
    single_sheets = []
    for i in range(0, len(singles), 36):
        chunk = singles[i:i + 36]
        single_sheets.append(contact_sheet([(crops[f["face_id"]], f"{f['face_id']} {f['photo_id']}") for f in chunk],
                                           wd / "sheets" / f"singles_{i // 36 + 1}.jpg",
                                           title="Unclustered faces"))

    save_json(wd / "faces" / "faces.json", {"faces": faces, "orientation": orient})
    save_json(wd / "faces" / "clusters.json", {"clusters": clusters, "single_sheets": single_sheets,
                                               "threshold": a.threshold})
    print(f"{len(faces)} faces, {len(clusters)} clusters, {len(singles)} unclustered. "
          f"Sheets in {wd / 'sheets'}")


def remember(a):
    wd = work_dir(a.out)
    faces = {f["face_id"]: f for f in load_json(wd / "faces" / "faces.json", {"faces": []})["faces"]}
    known = load_json(a.known, {}) or {}
    added = 0
    for rp in sorted((wd / "records").glob("*.json")):
        for person in load_json(rp).get("people", []):
            f = faces.get(person.get("face_id") or "")
            if f and person.get("name") and person.get("confidence") == "high":
                known.setdefault(person["name"], []).append(f["encoding"])
                added += 1
    for nm in known:  # cap per person so the library stays small and fast
        known[nm] = known[nm][-40:]
    save_json(a.known, known)
    print(f"Added {added} high-confidence face encodings; library has {len(known)} people: {a.known}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "remember"):
        s = sub.add_parser(name)
        s.add_argument("out")
        s.add_argument("--known", default=str(DEFAULT_KNOWN))
        if name == "scan":
            s.add_argument("--threshold", type=float, default=0.5,
                           help="cluster distance; lower is stricter (old prints: 0.45-0.55)")
    a = ap.parse_args()
    scan(a) if a.cmd == "scan" else remember(a)


if __name__ == "__main__":
    main()
