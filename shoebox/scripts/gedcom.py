#!/usr/bin/env python3
"""Flatten a GEDCOM file into people.json for name matching and age-based dating.

Usage: gedcom.py FILE.ged OUT_DIR   ->  OUT_DIR/.shoebox/people.json
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import save_json, work_dir  # noqa: E402

LINE = re.compile(r"^\s*(\d+)\s+(@[^@]+@\s+)?(\S+)\s?(.*)$")
YEAR = re.compile(r"\b(\d{4})\b")


def parse(path):
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    root = []
    stack = []  # (level, node)
    for line in text.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        lvl, xref, tag, val = int(m.group(1)), (m.group(2) or "").strip(), m.group(3).upper(), m.group(4)
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        if tag in ("CONC", "CONT") and stack:
            stack[-1][1]["val"] += ("\n" if tag == "CONT" else "") + val
            continue
        node = {"tag": tag, "xref": xref, "val": val, "kids": []}
        (stack[-1][1]["kids"] if stack else root).append(node)
        stack.append((lvl, node))
    return root


def first(node, tag):
    return next((k for k in node["kids"] if k["tag"] == tag), None)


def event(node, tag):
    e = first(node, tag)
    if not e:
        return None
    d, p = first(e, "DATE"), first(e, "PLAC")
    date = d["val"] if d else None
    y = YEAR.search(date or "")
    return {"date": date, "year": int(y.group(1)) if y else None, "place": p["val"] if p else None}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    recs = parse(sys.argv[1])
    people, fams = {}, {}
    for r in recs:
        if r["tag"] == "INDI":
            names = [k for k in r["kids"] if k["tag"] == "NAME"]
            full = [re.sub(r"\s+", " ", n["val"].replace("/", " ")).strip() for n in names]
            nick = [k["val"] for n in names for k in n["kids"] if k["tag"] == "NICK"]
            nick += [k["val"] for k in r["kids"] if k["tag"] == "NICK"]
            given = names[0]["val"].split("/")[0].strip() if names else ""
            married = [f"{given} {k['val']}".strip() for n in names for k in n["kids"] if k["tag"] == "_MARNM"]
            people[r["xref"]] = {
                "id": r["xref"], "name": full[0] if full else "", "alt_names": full[1:] + married,
                "nicknames": nick, "sex": (first(r, "SEX") or {}).get("val"),
                "birth": event(r, "BIRT"), "death": event(r, "DEAT"),
                "residences": [x for x in (event({"kids": [k]}, "RESI") for k in r["kids"] if k["tag"] == "RESI") if x],
                "famc": [k["val"] for k in r["kids"] if k["tag"] == "FAMC"],
                "fams": [k["val"] for k in r["kids"] if k["tag"] == "FAMS"],
            }
        elif r["tag"] == "FAM":
            fams[r["xref"]] = {
                "husb": (first(r, "HUSB") or {}).get("val"), "wife": (first(r, "WIFE") or {}).get("val"),
                "children": [k["val"] for k in r["kids"] if k["tag"] == "CHIL"],
                "marriage": event(r, "MARR"),
            }
    for p in people.values():
        p["parents"] = [x for f in p.pop("famc") for x in (fams.get(f, {}).get("husb"), fams.get(f, {}).get("wife")) if x]
        p["spouses"], p["children"], p["marriages"] = [], [], []
        for f in p.pop("fams"):
            fam = fams.get(f, {})
            p["spouses"] += [x for x in (fam.get("husb"), fam.get("wife")) if x and x != p["id"]]
            p["children"] += fam.get("children", [])
            if fam.get("marriage"):
                p["marriages"].append(fam["marriage"])
        for k in ("parents", "spouses", "children"):
            p[k] = [{"id": x, "name": people.get(x, {}).get("name")} for x in p[k]]
    out = work_dir(sys.argv[2]) / "people.json"
    save_json(out, {"source": sys.argv[1], "people": list(people.values())})
    print(f"{len(people)} people, {len(fams)} families -> {out}")


if __name__ == "__main__":
    main()
