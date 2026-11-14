---
name: shoebox
description: Process scanned family photos from an Epson FastFoto (FF-680W or similar) where fronts end in _a and backs in _b. Transcribes handwriting from the backs into each front's metadata. Sets EXIF/XMP dates and locations, approximate where needed, and infers dates for undated photos from matching people, clothing and settings. Fixes the orientation tag and identifies and tags people, using face clustering, notes on the backs and optional GEDCOM family trees. Use this whenever the user mentions FastFoto, scanned prints, old family photos, shoebox or album scans, photo backs with writing, or wants to date, geotag, caption or tag people in scanned pictures, even if they don't name the skill.
---

# Shoebox

Turn a folder of FastFoto scans into a well-labeled photo library. The writing on the backs,
plus clues inside the pictures, become dates, places, captions and people tags that any
photo app can read.

The key idea: **evidence spreads**. One back that says "Bob & Mom, Tahoe, July '74" can
date and name a dozen undated photos that show the same faces, the same striped shirt or
the same dock. Most of the value comes from that propagation, so the workflow first collects
evidence from every photo, then links photos together, then writes the tags.

## Inputs and conventions

- FastFoto saves `NAME_a.jpg` (enhanced front), `NAME_b.jpg` (back) and often `NAME.jpg`
  (the unenhanced original front). `_a` is the front. When a bare original exists, it gets
  the same metadata. Backs are optional. Some photos have no `_b`, or a blank one.
- **Originals are never modified.** Everything is copied to an output folder and tagged
  there. The default output is `<source>-shoebox` next to the source folder. Ask before
  writing anywhere else.
- **Backs stay out of the output.** Once a back's writing is transcribed onto the front, the
  `_b` scan is not copied (it remains in the source folder). Set `"keep_back": true` in a
  record only when the back still needs a human look, e.g. illegible words.
- The working state lives in `OUT/.shoebox/`: the manifest, previews, face data, contact
  sheets and one record per photo. Records persist, so a big batch can be resumed, and an
  answer can be corrected and the photo rewritten without starting over.
- GEDCOM (`.ged`) family-tree files are optional but valuable. They give correct spellings
  and full names, nicknames, birth and death years for age-based dating, and residences for
  locations. Ask the user whether they have one.

## Workflow

Scripts live in `scripts/` next to this file. Run them with the venv python printed by
setup (`$PY` below).

### 1. Setup and inventory

```bash
PY=$(bash scripts/setup.sh | tail -1)      # first run builds dlib: several minutes
$PY scripts/inventory.py SRC OUT           # pairs files, makes previews, flags blank backs
$PY scripts/gedcom.py family.ged OUT       # optional -> .shoebox/people.json
$PY scripts/faces.py scan OUT              # only if setup printed FACES=yes
```

`faces.py scan` gives three things. Every front gets a rotation hint: the rotation at which
the detector finds the most faces. It also produces face IDs with boxes and encodings, and
clusters of probably-the-same-person, each with a contact sheet of **face and torso crops**
so clothing can be compared. If a library exists at `~/.shoebox/known_faces.json` from
earlier batches, clusters get `suggested_name`.

If face_recognition is unavailable, skip that step and do person matching by looking at the
photos directly. It is slower and less consistent, but it works.

### 2. Read every photo (evidence pass)

Go through `manifest.json` in `seq` order (scan order often follows envelope or roll order,
which matters later). For each photo:

1. **Back**: view `preview_back` unless `back_likely_blank` is true. Check the likely-blank
   backs in bulk on the `blank_back_sheets` instead, and open any of them that shows marks.
   Transcribe exactly what is written. Handwriting on old prints is often faint pencil, so
   if a word is uncertain, open the full-resolution `back` file before guessing. Separate
   handwriting from printed lab stamps and paper watermarks. Both help dating, but only the
   handwriting is "the note".
2. **Front**: view `preview_front`. Decide `rotate_cw` relative to the preview as displayed.
   Start from the face-scan hint, but judge from the whole scene: horizon, gravity, text and
   furniture. The hint is weak with zero or one face. FastFoto usually gets the orientation
   right, so 0 is the most common answer.
3. **Note the evidence**: who is named and in what order ("L to R"), date, place, camera date
   imprint, and the setting. For each visible person, note clothing in a few distinctive words
   ("red plaid shirt, horn-rim glasses"). Also note the print format, border and color cast.
4. Save a draft record to `.shoebox/records/<id>.json` immediately. The schema is in
   `references/metadata.md`. Read it before writing the first record. Keep the clothing
   and setting notes in a `notes` field in the record (the writer ignores it), because the
   linking pass needs them.

For batches over about 50 photos, work in chunks and save as you go. Tell the user how far
you've got now and then.

### 3. Link people

Anchor names first, then spread them:

- **Anchors**: names on backs. Map "L to R" lists to face boxes by x position. When a back
  names people without an order, use sex, age and GEDCOM relationships to assign them, and
  mark the result `medium` unless it is unambiguous. Normalize names with `people.json`, so
  that "Grandma Rose" becomes the GEDCOM full name, with `gedcom_id` set.
- **Clusters**: view each cluster sheet. If any member face is anchored, the whole cluster
  usually is that person. Look for intruders, though: clustering on old, soft prints
  sometimes merges siblings or parent and child. Split a cluster mentally where the face,
  age or clothing disagrees.
- **Clothing and context**: within one event (same day, same outfits), a person in the same
  distinctive clothing is the same person even when the face is turned away, tiny or blurred.
  This is how the back-of-head and far-away figures get tagged. Across events, clothing alone
  is weak evidence. Combine it with the face, the build and who they're standing with.
- **Ages**: with GEDCOM birth years and an approximate photo date, check that each name fits
  the apparent age. A "Bob" who looks 40 in a 1955 photo can't be the Bob born in 1950.
- **Confidence**: `high` means named on the back and matched, or a strong cluster match
  confirmed visually. `medium` means a cluster or clothing match with a consistent age and
  context. `low` means plausible but uncertain. Tag as many people as the evidence honestly
  supports. The user wants broad coverage, and the confidence levels keep it honest.
  `low` stays out of the visible tags.
- Faces that remain unnamed get `name: null`, and should still be listed.

### 4. Date and place the undated

Read `references/dating-clues.md`, then for each photo without a written date:

- Group photos into **events**: neighboring `seq` numbers combined with the same outfits,
  setting, light and print stock. Give each event a short `event` label and copy the
  best-evidenced date and place across the group, with `source: inferred` and a basis that
  names the anchor photo.
- Otherwise, triangulate. Use GEDCOM age estimates of identified people, camera imprints,
  lab stamps, print format and period details. Prefer an honest range (`precision: year`
  with `circa_years: 3`) over a falsely precise date.
- Fill in a location only when there is real evidence: written text, a recognizable landmark,
  the same house or setting as a placed photo, or a GEDCOM residence for the person whose
  home it clearly is. Estimate lat/lon only to city or landmark precision.

### 5. Write and report

```bash
$PY scripts/write_metadata.py OUT --dry-run --only <id>   # spot-check one photo's tags
$PY scripts/write_metadata.py OUT                          # copy + tag fronts (backs only if keep_back)
$PY scripts/faces.py remember OUT                          # learn high-confidence faces
```

Check one written file with `exiftool -G1 -a OUT/<file>` to confirm that the tags landed.
Then summarize for the user:

- How many photos were processed, transcribed, dated (by exact, approximate and inferred),
  placed and tagged.
- The path to `OUT/shoebox_report.md`, the full per-photo table.
- **Unnamed clusters**, largest first, each with its sheet path. Naming even one big
  cluster can tag dozens of photos, so this is the most useful thing to ask the user for.
  When they reply with names, update the records and re-run `write_metadata.py`.
- Anything uncertain: illegible words, conflicting dates, and backs that disagree with the
  faces.

## Judgment notes

- **The transcription is sacred; inferences are labeled.** The description fields hold only
  what is literally written on the back. Everything Claude inferred goes in the date and
  location fields, with its basis in `UserComment`, so a family member can always tell
  "Grandma wrote this" from "the software guessed this".
- People's names are personal data that the user has chosen to process. Keep everything
  local: no web lookups of faces or family names.
- When a note conflicts with the visual evidence (for example, a back says 1962 but the
  camera imprint says '88), trust neither blindly. Record both in `basis`, choose the better
  supported one, lower the confidence, and list the conflict for the user.
- Notes are sometimes about the occasion, not the people ("Debbie's 5th birthday").
  Combined with a GEDCOM birth date, that gives an exact day.
