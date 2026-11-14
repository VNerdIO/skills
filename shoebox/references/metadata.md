# Record schema and tag mapping

One JSON file per photo at `OUT/.shoebox/records/<id>.json`. `write_metadata.py` turns
these into tags. Records are the source of truth: to fix a photo, edit its record and
re-run `write_metadata.py --only <id>`.

## Record

```json
{
  "id": "FastFoto_0042",
  "rotate_cw": 90,
  "orientation_confidence": "high",
  "transcription": "Bob, Mom & Aunt Jean\nLake Tahoe - July '74",
  "transcription_notes": "Ballpoint, two hands. 'Jean' could be 'Joan'. Lab stamp 'AUG 74' not included above.",
  "date": {
    "value": "1974-07",
    "precision": "month",
    "circa_years": 0,
    "confidence": "high",
    "source": "back",
    "basis": "Written on back: July '74; lab stamp AUG 74 agrees"
  },
  "location": {
    "name": "Lake Tahoe",
    "sublocation": "",
    "city": "South Lake Tahoe",
    "state": "California",
    "country": "United States",
    "lat": 38.94, "lon": -119.98,
    "confidence": "medium",
    "basis": "Written on back; city-level coordinates estimated"
  },
  "people": [
    {"name": "Robert Smith", "face_id": "f00101", "box": [0.12, 0.20, 0.08, 0.11],
     "confidence": "high", "basis": "Named on back, leftmost; matches cluster c004",
     "gedcom_id": "@I12@"},
    {"name": null, "face_id": "f00103", "box": [0.70, 0.25, 0.07, 0.10],
     "confidence": null, "basis": "Unidentified; in cluster c017 (6 photos)"}
  ],
  "event": "Lake Tahoe trip 1974",
  "keywords": ["lake", "summer", "boat"],
  "caption": "Three adults on a dock beside a lake"
}
```

Field rules:

- `rotate_cw`: degrees clockwise (0/90/180/270) needed to make the **stored pixels**
  (what the preview shows) upright. Not relative to any existing Orientation tag.
- `transcription`: what is written, verbatim. Keep original spelling, abbreviations and line
  breaks (`\n`). Mark unreadable words as `[illegible]` and best guesses as `[Jean?]`. Leave
  printed lab marks out unless they carry information; mention them in `transcription_notes`.
  Use `""` when the back is blank.
- `keep_back` (optional, default false): copy the `_b` scan into the output too. Backs are
  otherwise left out, since the transcription is on the front. Use it when `[illegible]`
  words or an uncertain reading mean a person should still see the back.
- `date.value`: partial ISO date: `YYYY`, `YYYY-MM` or `YYYY-MM-DD`. Precision `decade` uses the
  middle year (`1975`) with `circa_years: 5`. Precision `season` uses the middle month of the
  season. Never omit `basis`, because a later reader needs to know where a date came from.
- `date.source`: `back`, `front-stamp` (date printed on the photo by the camera), `lab-stamp`,
  or `inferred`.
- `location.lat/lon`: fill these only when the place is known at least to the city or landmark
  level. They are written to GPS unless `confidence` is `low`. Leave them null for vague places
  like "Grandma's house" unless GEDCOM or another photo gives the address.
- `people[].box`: `[x, y, w, h]`, normalized, top-left origin, **in the upright frame**.
  The face IDs and boxes from `faces.json` are already in that frame. For faces Claude found
  that the detector missed, estimate the box from the upright view.
- `people[].confidence`: `high` and `medium` are written as tags. `low` appears only in the
  UserComment ("Possibly also: …") and the report. Include unnamed faces with `name: null`
  so the report can count them.

## Tags written

| Record | Front (`_a` + unsuffixed original) | Back (`_b`, only with `keep_back`) |
|---|---|---|
| rotate_cw | `EXIF:Orientation` (0→1, 90→6, 180→3, 270→8) | not changed |
| transcription | `EXIF:ImageDescription`, `XMP-dc:Description`, `IPTC:Caption-Abstract` | `XMP-dc:Description` "Back of X. Reads: …" |
| caption (no writing on back) | `XMP-dc:Title` | |
| date | `EXIF:DateTimeOriginal` (unknown parts filled with a midpoint, 12:00), `XMP-exif:DateTimeOriginal`, `XMP-photoshop:DateCreated` (partial, true precision) | same |
| location | `XMP-iptcCore:Location`, `XMP-photoshop:City/State/Country`, IPTC equivalents, `EXIF:GPS*` | same |
| people | `XMP-iptcExt:PersonInImage`, keywords, `XMP-mwg-rs:RegionInfo` face regions (Lightroom, digiKam), `XMP-MP:RegionInfoMP` (Windows Photos) | not written |
| keywords, event, flags | `XMP-dc:Subject`, `IPTC:Keywords` (+ `shoebox:date-approximate`, `shoebox:date-inferred`) | same |
| notes and basis | `EXIF:UserComment` "shoebox: Date … \| Location … \| People …" | same |

`EXIF:CreateDate` (DateTimeDigitized) is deliberately left alone, because the scan date is
the correct value there. Face regions are not written to the unsuffixed original, because
FastFoto's enhancement step can change its crop.
