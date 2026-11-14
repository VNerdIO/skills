# tree.json and GEDCOM 5.5.1

`tree.json` is the working file. Claude edits it; `gedcom.py write` turns it into GEDCOM
5.5.1 (lineage-linked, UTF-8), the version Ancestry, MyHeritage, FamilySearch,
RootsMagic, Family Tree Maker and Gramps all import. `gedcom.py read` reads 5.5.1 and
7.0 files into the same shape.

## Schema

```json
{
  "subject": "I1",
  "submitter": "Mike Smith",
  "people": {
    "I1": {
      "given": "Michael Owen", "surname": "Smith", "nickname": "Mike", "sex": "M",
      "living": true,
      "birth": {"date": "12 MAR 1975", "place": "Chattanooga, Hamilton, Tennessee, USA",
                "sources": [{"id": "S1", "page": "certificate 1975-0412", "quay": 3}]},
      "death": null, "burial": null,
      "father": "I2", "mother": "I3",
      "confidence": "high", "basis": "Given by the user",
      "notes": "Free text.",
      "sources": ["S2"]
    }
  },
  "marriages": [{"husband": "I2", "wife": "I3", "date": "1970", "place": "...", "sources": ["S3"]}],
  "sources": {
    "S1": {"title": "Find a Grave memorial 12345, Harold Smith", "url": "https://...",
           "author": "", "publication": "", "accessed": "14 NOV 2026", "note": ""}
  }
}
```

- IDs: `I<n>` for people, `S<n>` for sources. Keep IDs stable once assigned; the writer
  numbers families (`F<n>`) itself from father/mother pairs and `marriages`.
- A citation is a source ID or `{"id", "page", "quay"}`. `page` is where in the source
  (memorial number, census line, obituary paragraph). `quay` is GEDCOM's 0–3 quality
  scale: 3 direct primary evidence (certificate, register), 2 secondary (obituary,
  compiled tree with sources), 1 questionable (unsourced online tree), 0 unreliable.
- `confidence` (`high`, `medium`, `low`) and `basis` describe the person's *identity
  link*: how sure the chain is that this record is really the subject's ancestor.
  The chart badges `medium` and `low`; the writer puts both into a `NOTE`.
- `death` present with an empty date writes `1 DEAT Y`: known dead, date unknown.
- `living: true` people have no death event. Their details come from the user.

## Conventions the writer and checker rely on

- **Names**: women under their **birth surname** (genealogy standard; married names go
  in `notes`). Unknown surname: leave `surname` empty, never "Unknown".
- **Dates**: GEDCOM form, `DD MMM YYYY` with English month abbreviations, or partial
  (`MAR 1931`, `1931`). Qualifiers: `ABT`, `CAL`, `EST`, `BEF`, `AFT`,
  `BET 1880 AND 1885`, `FROM 1900 TO 1910`. ISO dates from WikiTree (`1931-03-00`) are
  converted on write. "Spring 1931" and "1930s" are not valid: use `ABT 1931`,
  `BET 1930 AND 1939`.
- **Places**: smallest to largest, comma-separated, with the jurisdiction *as it was at
  the time*: `Dayton, Rhea, Tennessee, USA`. Keep the county (US genealogy records are
  filed by county). Leave a level out rather than guess it.
- **Sex**: `M`, `F` or `U`. Fathers must be `M` and mothers `F` (the checker warns).

## What `check` flags

Dangling father/mother or source IDs, dates that aren't 5.5.1, death before birth,
lifespans over 110, a parent outside 12–52 (mother) or 13–75 (father) at the child's
birth, a child born after the mother's death or more than a year after the father's,
a person who is their own ancestor, and deceased people with no source. Each warning
is either a data error to fix or a real oddity to explain in `notes`.
