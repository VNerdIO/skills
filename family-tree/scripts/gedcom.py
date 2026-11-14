#!/usr/bin/env python3
"""Read, write and check GEDCOM files against the tree.json working format.

Usage:
  gedcom.py read FILE.ged TREE.json      GEDCOM 5.5.1 or 7.0 -> tree.json
  gedcom.py write TREE.json FILE.ged     tree.json -> GEDCOM 5.5.1 (UTF-8), then check it
  gedcom.py check TREE.json              consistency warnings only
  gedcom.py find TREE.json NAME          list people whose name contains NAME

The tree.json schema is in references/gedcom.md.
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

LINE = re.compile(r"^\s*(\d+)\s+(@[^@]+@\s+)?(\S+)\s?(.*)$")
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DATE_551 = re.compile(
    r"^(?:(?:ABT|CAL|EST|BEF|AFT|FROM|TO|INT)\s+)?"
    r"(?:(?:\d{1,2}\s+)?(?:" + "|".join(MONTHS) + r")\s+)?\d{3,4}(?:/\d{2})?"
    r"(?:\s+(?:AND|TO)\s+(?:(?:\d{1,2}\s+)?(?:" + "|".join(MONTHS) + r")\s+)?\d{3,4})?$"
)
BET = re.compile(r"^BET\s+(.+)\s+AND\s+(.+)$")
YEAR = re.compile(r"\b(\d{4})\b")
EVENTS = {"BIRT": "birth", "DEAT": "death", "BURI": "burial"}
LIVING_YEARS = 110  # no death record and born within this many years -> treat as living


# ---------------------------------------------------------------- dates

def normalize_date(value):
    """Return a GEDCOM 5.5.1 date. Accepts GEDCOM dates and ISO dates with 00 for unknown parts."""
    if not value:
        return ""
    v = re.sub(r"\s+", " ", str(value).strip()).upper()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", v)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        if y == 0:
            return ""
        if mo == 0:
            return str(y)
        return f"{d} {MONTHS[mo - 1]} {y}" if d else f"{MONTHS[mo - 1]} {y}"
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", v)
    if m:  # numeric: convert only when the day can't be mistaken for the month
        a, b, y = (int(x) for x in m.groups())
        if a > 12 >= b:
            return f"{a} {MONTHS[b - 1]} {y}"
        if b > 12 >= a:
            return f"{b} {MONTHS[a - 1]} {y}"
        return v
    v = re.sub(r"\b(ABT|ABOUT|CIRCA|CA|C|BEF|BEFORE|AFT|AFTER|EST|CAL)\.", r"\1", v)
    for word, short in (("ABOUT", "ABT"), ("CIRCA", "ABT"), ("CA", "ABT"), ("C", "ABT"),
                        ("BEFORE", "BEF"), ("AFTER", "AFT")):
        v = re.sub(rf"^{word} ", f"{short} ", v)
    v = re.sub(r"\b(JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(?:UARY|RUARY|CH|IL|E|Y|UST|T|TEMBER|OBER|EMBER)?"
               r"(?:\.|\b)", r"\1", v)
    return re.sub(r"\b(" + "|".join(MONTHS) + r") (\d{1,2}),? (\d{4})\b", r"\2 \1 \3", v)  # "JUL 4, 1931"


def valid_date(value):
    v = normalize_date(value)
    m = BET.match(v)
    if m:
        return all(DATE_551.match(p) for p in m.groups())
    return bool(DATE_551.match(v))


def year_of(value):
    m = YEAR.search(value or "")
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- reading

def parse(path):
    raw = Path(path).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")  # ANSEL and ANSI files: close enough for names
    root, stack = [], []
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
        node = {"tag": tag, "xref": xref.strip("@"), "val": val, "kids": []}
        (stack[-1][1]["kids"] if stack else root).append(node)
        stack.append((lvl, node))
    return root


def first(node, tag):
    return next((k for k in node["kids"] if k["tag"] == tag), None)


def ptr(value):
    v = (value or "").strip()
    return v.strip("@") if v.startswith("@") and v != "@VOID@" else None


def citations(node):
    out = []
    for s in (k for k in node["kids"] if k["tag"] == "SOUR"):
        sid = ptr(s["val"])
        if not sid:
            continue
        c = {"id": sid}
        for tag, key in (("PAGE", "page"), ("QUAY", "quay")):
            k = first(s, tag)
            if k:
                c[key] = int(k["val"]) if key == "quay" and k["val"].isdigit() else k["val"]
        out.append(c)
    return out


def event(node, tag):
    e = first(node, tag)
    if not e:
        return None
    d, p = first(e, "DATE"), first(e, "PLAC")
    ev = {"date": normalize_date(d["val"]) if d else "", "place": p["val"] if p else ""}
    if citations(e):
        ev["sources"] = citations(e)
    return ev


def read(ged_path):
    recs = parse(ged_path)
    people, fams, sources = {}, {}, {}
    this_year = dt.date.today().year
    for r in recs:
        if r["tag"] == "INDI":
            names = [k for k in r["kids"] if k["tag"] == "NAME"]
            given = surname = ""
            if names:
                n = names[0]
                g, s = first(n, "GIVN"), first(n, "SURN")
                parts = n["val"].split("/")
                given = g["val"] if g else parts[0].strip()
                surname = s["val"] if s else (parts[1].strip() if len(parts) > 1 else "")
            p = {"given": given, "surname": surname, "sex": (first(r, "SEX") or {}).get("val", "U")[:1]}
            nick = first(names[0], "NICK") if names else None
            if nick:
                p["nickname"] = nick["val"]
            for tag, key in EVENTS.items():
                ev = event(r, tag)
                if ev is not None:
                    p[key] = ev
            by = year_of((p.get("birth") or {}).get("date"))
            p["living"] = "death" not in p and "burial" not in p and (by is None or this_year - by < LIVING_YEARS)
            notes = [k["val"] for k in r["kids"] if k["tag"] == "NOTE" and not ptr(k["val"])]
            if notes:
                p["notes"] = "\n".join(notes)
            if citations(r):
                p["sources"] = citations(r)
            p["_famc"] = [ptr(k["val"]) for k in r["kids"] if k["tag"] == "FAMC" and ptr(k["val"])]
            people[r["xref"]] = p
        elif r["tag"] == "FAM":
            fams[r["xref"]] = {
                "husband": ptr((first(r, "HUSB") or {}).get("val")),
                "wife": ptr((first(r, "WIFE") or {}).get("val")),
                "children": [ptr(k["val"]) for k in r["kids"] if k["tag"] == "CHIL"],
                "marriage": event(r, "MARR"),
            }
        elif r["tag"] == "SOUR" and r["xref"]:
            s = {}
            for tag, key in (("TITL", "title"), ("AUTH", "author"), ("PUBL", "publication"), ("NOTE", "note"),
                             ("WWW", "url")):
                k = first(r, tag)
                if k:
                    s[key] = k["val"]
            url = re.search(r"https?://\S+", s.get("note", "") + " " + s.get("publication", ""))
            if url and "url" not in s:
                s["url"] = url.group(0)
            sources[r["xref"]] = s
    marriages = []
    for fid, f in fams.items():
        for c in f["children"]:
            if c in people:
                people[c].setdefault("father", f["husband"])
                people[c].setdefault("mother", f["wife"])
        if f["marriage"] and (f["husband"] or f["wife"]):
            marriages.append({"husband": f["husband"], "wife": f["wife"], **f["marriage"]})
    for p in people.values():
        for fid in p.pop("_famc"):  # FAMC without a matching CHIL line
            f = fams.get(fid)
            if f:
                p.setdefault("father", f["husband"])
                p.setdefault("mother", f["wife"])
        for k in ("father", "mother"):
            if not p.get(k):
                p.pop(k, None)
    # undated parents: estimate birth as 20 years before their eldest dated child, up the tree
    est = {pid: year_of((p.get("birth") or {}).get("date")) for pid, p in people.items()}
    for _ in range(12):
        changed = False
        for pid, p in people.items():
            for k in ("father", "mother"):
                par, guess = p.get(k), est[pid] and est[pid] - 20
                if par in people and guess and (est[par] is None or est[par] > guess):
                    est[par] = guess
                    changed = True
        if not changed:
            break
    for pid, p in people.items():
        if p["living"] and est.get(pid) and this_year - est[pid] >= LIVING_YEARS:
            p["living"] = False
    return {"subject": None, "source_file": str(ged_path), "people": people,
            "marriages": marriages, "sources": sources}


# ---------------------------------------------------------------- writing

def cite_list(items):
    return [{"id": c} if isinstance(c, str) else c for c in (items or [])]


class Writer:
    def __init__(self):
        self.lines = []

    def add(self, level, tag, value="", xref=None):
        value = str(value or "")
        head = f"{level} " + (f"@{xref}@ " if xref else "") + tag
        chunks = value.split("\n")
        self._long(head, chunks[0], level)
        for more in chunks[1:]:
            self._long(f"{level + 1} CONT", more, level)

    def _long(self, head, value, level, limit=240):
        # 5.5.1 caps a line at 255 characters; split long values with CONC
        self.lines.append(f"{head} {value[:limit]}".rstrip())
        rest = value[limit:]
        while rest:
            self.lines.append(f"{level + 1} CONC {rest[:limit]}")
            rest = rest[limit:]

    def cites(self, level, items):
        for c in cite_list(items):
            self.add(level, "SOUR", f"@{c['id']}@")
            if c.get("page"):
                self.add(level + 1, "PAGE", c["page"])
            if c.get("quay") is not None:
                self.add(level + 1, "QUAY", c["quay"])

    def event(self, level, tag, ev):
        if ev is None:
            return
        date, place = normalize_date(ev.get("date")), ev.get("place")
        self.add(level, tag, "" if date or place or ev.get("sources") else "Y")
        if date:
            self.add(level + 1, "DATE", date)
        if place:
            self.add(level + 1, "PLAC", place)
        self.cites(level + 1, ev.get("sources"))


def families(tree):
    """Group parents into FAM records: one per (father, mother) pair, plus marriages without children."""
    fams = {}

    def fam(h, w):
        key = (h, w)
        if key not in fams:
            fams[key] = {"id": f"F{len(fams) + 1}", "husband": h, "wife": w, "children": [], "marriage": None}
        return fams[key]

    for pid, p in tree["people"].items():
        if p.get("father") or p.get("mother"):
            fam(p.get("father"), p.get("mother"))["children"].append(pid)
    for m in tree.get("marriages", []):
        fam(m.get("husband"), m.get("wife"))["marriage"] = m
    return list(fams.values())


def write(tree, out_path):
    w = Writer()
    today = dt.date.today()
    w.add(0, "HEAD")
    w.add(1, "SOUR", "FAMILY_TREE_SKILL")
    w.add(2, "NAME", "family-tree skill")
    w.add(1, "DATE", f"{today.day} {MONTHS[today.month - 1]} {today.year}")
    w.add(1, "SUBM", "@U1@")
    w.add(1, "GEDC")
    w.add(2, "VERS", "5.5.1")
    w.add(2, "FORM", "LINEAGE-LINKED")
    w.add(1, "CHAR", "UTF-8")
    w.add(0, "SUBM", xref="U1")
    w.add(1, "NAME", tree.get("submitter") or "Unknown")

    fams = families(tree)
    famc = {c: f["id"] for f in fams for c in f["children"]}
    fams_of = {}
    for f in fams:
        for k in ("husband", "wife"):
            if f[k]:
                fams_of.setdefault(f[k], []).append(f["id"])

    for pid, p in tree["people"].items():
        w.add(0, "INDI", xref=pid)
        given, surname = p.get("given", ""), p.get("surname", "")
        w.add(1, "NAME", f"{given} /{surname}/".strip())
        if given:
            w.add(2, "GIVN", given)
        if surname:
            w.add(2, "SURN", surname)
        if p.get("nickname"):
            w.add(2, "NICK", p["nickname"])
        w.add(1, "SEX", (p.get("sex") or "U")[:1].upper())
        for key in ("birth", "death", "burial"):
            w.event(1, {v: k for k, v in EVENTS.items()}[key], p.get(key))
        if pid in famc:
            w.add(1, "FAMC", f"@{famc[pid]}@")
        for fid in fams_of.get(pid, []):
            w.add(1, "FAMS", f"@{fid}@")
        note = p.get("notes", "")
        if p.get("confidence"):
            basis = f": {p['basis']}" if p.get("basis") else ""
            note = (note + "\n" if note else "") + f"Confidence {p['confidence']}{basis}"
        if note:
            w.add(1, "NOTE", note)
        w.cites(1, p.get("sources"))

    for f in fams:
        w.add(0, "FAM", xref=f["id"])
        if f["husband"]:
            w.add(1, "HUSB", f"@{f['husband']}@")
        if f["wife"]:
            w.add(1, "WIFE", f"@{f['wife']}@")
        for c in f["children"]:
            w.add(1, "CHIL", f"@{c}@")
        w.event(1, "MARR", f["marriage"])

    for sid, s in tree.get("sources", {}).items():
        w.add(0, "SOUR", xref=sid)
        w.add(1, "TITL", s.get("title") or sid)
        if s.get("author"):
            w.add(1, "AUTH", s["author"])
        if s.get("publication"):
            w.add(1, "PUBL", s["publication"])
        note = "\n".join(x for x in (
            s.get("url") and f"URL: {s['url']}",
            s.get("accessed") and f"Accessed {normalize_date(s['accessed'])}",
            s.get("note"),
        ) if x)
        if note:
            w.add(1, "NOTE", note)
    w.add(0, "TRLR")

    tmp = Path(str(out_path) + ".tmp")
    tmp.write_text("\n".join(w.lines) + "\n", encoding="utf-8")
    os.replace(tmp, out_path)
    return len(tree["people"]), len(fams), len(tree.get("sources", {}))


# ---------------------------------------------------------------- checking

def check(tree):
    warn = []
    people, srcs = tree["people"], tree.get("sources", {})

    def name(pid):
        p = people.get(pid, {})
        return f"{p.get('given', '')} {p.get('surname', '')}".strip() or pid

    if tree.get("subject") and tree["subject"] not in people:
        warn.append(f"subject {tree['subject']} is not in people")
    for pid, p in people.items():
        for k in ("father", "mother"):
            if p.get(k) and p[k] not in people:
                warn.append(f"{name(pid)}: {k} {p[k]} is not in people")
        for key in ("birth", "death", "burial"):
            ev = p.get(key) or {}
            if ev.get("date") and not valid_date(ev["date"]):
                warn.append(f"{name(pid)}: {key} date {ev['date']!r} is not a GEDCOM 5.5.1 date")
            for c in cite_list(ev.get("sources")):
                if c["id"] not in srcs:
                    warn.append(f"{name(pid)}: {key} cites unknown source {c['id']}")
        for c in cite_list(p.get("sources")):
            if c["id"] not in srcs:
                warn.append(f"{name(pid)}: cites unknown source {c['id']}")
        by, dy = year_of((p.get("birth") or {}).get("date")), year_of((p.get("death") or {}).get("date"))
        if by and dy and dy < by:
            warn.append(f"{name(pid)}: died ({dy}) before born ({by})")
        if by and dy and dy - by > 110:
            warn.append(f"{name(pid)}: lifespan {dy - by} years")
        if p.get("living") and dy:
            warn.append(f"{name(pid)}: marked living but has a death date")
        if p.get("sex") == "F" and pid in {q.get("father") for q in people.values()}:
            warn.append(f"{name(pid)}: female but listed as a father")
        if p.get("sex") == "M" and pid in {q.get("mother") for q in people.values()}:
            warn.append(f"{name(pid)}: male but listed as a mother")
        for k, lo, hi in (("father", 13, 75), ("mother", 12, 52)):
            par = people.get(p.get(k) or "")
            if not par or not by:
                continue
            pb = year_of((par.get("birth") or {}).get("date"))
            pd = year_of((par.get("death") or {}).get("date"))
            if pb and not lo <= by - pb <= hi:
                warn.append(f"{name(pid)} born {by}: {k} {name(p[k])} would be {by - pb}")
            if pd and by > pd + (1 if k == "father" else 0):
                warn.append(f"{name(pid)} born {by}: after {k} {name(p[k])} died ({pd})")
        if not p.get("living") and not p.get("sources") and not any(
                (p.get(k) or {}).get("sources") for k in ("birth", "death", "burial")):
            warn.append(f"{name(pid)}: no source cited")
    for pid in people:  # a person can't be their own ancestor
        seen, todo = set(), [pid]
        while todo:
            cur = todo.pop()
            for k in ("father", "mother"):
                par = people.get(cur, {}).get(k)
                if par == pid:
                    warn.append(f"{name(pid)} is their own ancestor")
                    todo = []
                    break
                if par and par not in seen:
                    seen.add(par)
                    todo.append(par)
    for m in tree.get("marriages", []):
        if m.get("date") and not valid_date(m["date"]):
            warn.append(f"marriage {name(m.get('husband'))} & {name(m.get('wife'))}: date {m['date']!r} is not valid")
    return warn


# ---------------------------------------------------------------- cli

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("read", "write", "check", "find"):
        sys.exit(__doc__)
    cmd = args[0]
    if cmd == "read" and len(args) == 3:
        tree = read(args[1])
        save(args[2], tree)
        living = sum(p["living"] for p in tree["people"].values())
        print(f"{len(tree['people'])} people ({living} presumed living), {len(tree['sources'])} sources -> {args[2]}")
    elif cmd == "write" and len(args) == 3:
        tree = load(args[1])
        n, f, s = write(tree, args[2])
        print(f"{n} people, {f} families, {s} sources -> {args[2]}")
        back = read(args[2])
        if len(back["people"]) != n:
            print(f"ROUND-TRIP MISMATCH: re-read {len(back['people'])} people")
        for w in check(tree):
            print("WARN", w)
    elif cmd == "check" and len(args) == 2:
        warns = check(load(args[1]))
        for w in warns:
            print("WARN", w)
        print(f"{len(warns)} warnings")
    elif cmd == "find" and len(args) == 3:
        needle = args[2].lower()
        for pid, p in load(args[1])["people"].items():
            full = f"{p.get('given', '')} {p.get('surname', '')}"
            if all(part in full.lower() for part in needle.split()):
                b, d = (p.get("birth") or {}).get("date", ""), (p.get("death") or {}).get("date", "")
                print(f"{pid}\t{full.strip()}\t{b} - {d}\t{(p.get('birth') or {}).get('place', '')}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
