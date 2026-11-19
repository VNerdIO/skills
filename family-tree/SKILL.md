---
name: family-tree
description: Build a four-generation family tree (a person, their parents, grandparents and great-grandparents) as a GEDCOM 5.5.1 file plus a single-page interactive pedigree chart. Reads an existing GEDCOM (5.5.1 or 7.0, including Ancestry and FamilySearch exports). With no GEDCOM, interviews the user and then researches deceased ancestors in WikiTree, obituaries, Find a Grave, Library of Congress newspapers and other free public records (or sites the user is signed in to), citing every fact. Use this whenever the user wants a family tree, pedigree or ancestor chart, asks who their great-grandparents were, wants to trace their ancestry or genealogy, or wants to view, clean up or convert a .ged file, even if they don't name the skill.
---

# Family tree

Produce two files for one **subject** (usually the user): a standard GEDCOM 5.5.1 file
that any genealogy program imports, and a self-contained HTML pedigree chart of the
subject's 15-person, four-generation tree that opens offline in any browser.

The working file is `tree.json`. Everything flows through it: a GEDCOM is read into it,
research is written into it, and both outputs are generated from it. Read
[`references/gedcom.md`](references/gedcom.md) before writing to `tree.json` for the
first time. It holds the schema and the date, name and place conventions.

## Output

Write to `./<surname>-family-tree/` in the current directory unless the user names a
folder: `tree.json`, `<surname>-family.ged` and `<surname>-family-tree.html`. Scripts
live in `scripts/` next to this file and need only the Python 3 standard library.

## 1. Find the starting point

- **The user gave a GEDCOM**: read it, then go to step 4.

  ```bash
  python3 scripts/gedcom.py read family.ged OUT/tree.json
  python3 scripts/gedcom.py find OUT/tree.json "first last"   # get the subject's id
  ```

  Ask who the subject is if the request doesn't say. Set `"subject"` in `tree.json`.
  `read` marks as living anyone with no death record unless a dated birth (theirs or
  a descendant's) puts them over 110, so undated ancestors often come out "living".
  Correct the flag for the 15 pedigree people. Research is only for filling empty
  slots, and only if the user wants it.
- **No GEDCOM mentioned**: look for one before asking anything. Run
  `mdfind -name .ged 2>/dev/null` and `mdfind -name people.json 2>/dev/null` (shoebox's
  flattened tree). If any turn up, ask the user whether to start from one. Otherwise,
  go to step 2.

## 2. Interview

Ask once, in one message, as a fill-in form the user can answer loosely. Ask for:

- **The subject**: full name, birth date and place. Usually the user; confirm.
- **Each of the 14 ancestors they know**: full name (women's **maiden** names), birth
  and death dates and places (years and towns are fine), and whether they're living.
  Lay this out as the pedigree (father, mother, father's father...) so blanks are
  obvious.
- **Leads**: obituaries they know of, cemeteries, hometowns and counties, an existing
  online tree or WikiTree ID, family stories ("came from Ireland around 1900").
- **Submitter name** for the GEDCOM header.

Record every answer in `tree.json` right away. Facts from the user get a source like
`{"title": "Information from <user name>, 14 NOV 2026"}` and `"confidence": "high"`. The
step is done when every one of the 15 slots is either filled or known to be blank.
Ask follow-up questions only when answers conflict.

## 3. Research the blanks

Read [`references/research.md`](references/research.md) first. It holds the
living-people rule, the source list and the two-point match rule.

Work generation by generation outward from the subject, reaching each new ancestor
through a record that links them to someone already established:

```bash
python3 scripts/wikitree.py search Harold Smith --birth 1931 --place Tennessee
python3 scripts/wikitree.py ancestors Smith-12345 --depth 3
python3 scripts/wikitree.py profile Smith-12345
python3 scripts/loc.py search "Harold Smith" --state tennessee --from 1900 --to 1963   # old newspapers
```

Use the web search and fetch tools for obituaries, Find a Grave and archives. For
anyone who died before 1964, also search Chronicling America with `scripts/loc.py`.
If the user says they're signed in to FamilySearch, Newspapers.com or Ancestry in
Chrome, use those sites through the browser (see "Signed-in sites" in research.md). Add each
accepted person and source to `tree.json` as you go, with `confidence` and `basis`.
The step is done when every empty slot whose child is a `medium` or `high` person has
been searched in WikiTree, an obituary search and Find a Grave. Record which sources
came up empty in the child's `notes`, so the report can say what was tried.

If a source fails (network error, blocked fetch, no results), say so in the report and
continue. A slot stays empty rather than being filled from memory.

## 4. Write and check

```bash
python3 scripts/gedcom.py write OUT/tree.json "OUT/<surname>-family.ged"
python3 scripts/chart.py OUT/tree.json "OUT/<surname>-family-tree.html" --ged "OUT/<surname>-family.ged"
```

`write` re-reads its own output and runs the checks. Resolve every `WARN` that touches
the 15 pedigree people: fix the data, or explain the oddity in `notes`. A GEDCOM from
elsewhere may warn about people outside the pedigree; summarize those for the user
and leave them alone. Numeric dates like `03/04/1931` stay flagged when month and day
could be either way round. Ask the user which.

`chart.py` reports how many of the 15 slots are filled and names the empty ones. Add
`--hide-living` when the user plans to share the chart: living people then show as
"Living" with no dates or places. Open the HTML once (`open <file>`) so the user sees
it.

## 5. Report

In chat, give:

- The two file paths, and the slot count ("12 of 15 ancestors").
- The pedigree as a short indented list: name, years, and a `medium`/`low` marker.
- Every `low` and `medium` person with their `basis`, as questions the user can answer
  ("Is Elmer Smith, 1899–1970, Rhea County, your great-grandfather? Matched on county and
  son's name only").
- Empty slots, with what was searched, and paywalled leads worth the user's own login
  (Ancestry, Newspapers.com).

When the user confirms or corrects someone, update `tree.json`, raise or lower
`confidence`, and re-run step 4.
