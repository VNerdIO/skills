#!/usr/bin/env python3
"""Push an aisle-sorted grocery list into Apple Reminders (macOS only).

Usage: reminders.py LIST.json [--dry-run]

LIST.json:
  {"list": "Publix 11/14",
   "items": [{"title": "Produce · Bananas", "notes": "SALE $0.59/lb thru 11/17"}, ...]}

Creates the Reminders list if it doesn't exist and adds the items in the order given,
which should be the walking order through the store. Notes are optional. Data goes to
osascript as arguments, never pasted into the script, so item text needs no escaping.
"""
import argparse
import json
import subprocess
import sys

APPLESCRIPT = """
on run argv
    set listName to item 1 of argv
    tell application "Reminders"
        if not (exists list listName) then make new list with properties {name:listName}
        set theList to list listName
        repeat with i from 2 to (count of argv) by 2
            make new reminder at end of theList with properties {name:(item i of argv), body:(item (i + 1) of argv)}
        end repeat
    end tell
end run
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("list_json")
    ap.add_argument("--dry-run", action="store_true", help="print what would be added")
    args = ap.parse_args()

    with open(args.list_json) as f:
        data = json.load(f)
    name, items = data["list"], data["items"]

    if args.dry_run:
        print(f"[{name}]")
        for it in items:
            print(f"  - {it['title']}" + (f"  ({it['notes']})" if it.get("notes") else ""))
        return 0

    argv = [name]
    for it in items:
        argv += [it["title"], it.get("notes") or ""]
    proc = subprocess.run(["osascript", "-", *argv], input=APPLESCRIPT, text=True, capture_output=True)
    if proc.returncode:
        print(proc.stderr.strip(), file=sys.stderr)
        return proc.returncode
    print(f"Added {len(items)} items to Reminders list '{name}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
