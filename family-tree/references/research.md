# Researching ancestors

Work **one generation at a time, from the known toward the unknown**. Every new person
is reached *through* a record that links them to someone already established: a
child's death certificate naming parents, an obituary naming survivors, a Find a Grave
memorial with family links. Searching a bare name and adopting the best-looking hit is
how wrong trees are built.

## Ground rules

- **Living people stay offline.** Search only for people known to be deceased. Facts
  about the living come from the user. If an online record turns up a living
  relative, use it only as a link to the deceased, and keep their details out of the
  tree unless the user gave them.
- **Read-only, public, no login.** Use only sources that open without signing in.
  When a result is behind a paywall (Ancestry, Newspapers.com, MyHeritage), note it in
  the person's `notes` as a lead for the user and move on.
- **Cite as you go.** The moment a fact is accepted, add the source to `sources` with
  its URL and today's date as `accessed`, and cite it from the fact. A fact without a
  citation is an assumption; put it in `notes` instead.

## Sources, in order of usefulness

| Source | How | Gives |
| --- | --- | --- |
| WikiTree | `scripts/wikitree.py search`, then `ancestors ID --depth 3` | Sourced, collaboratively checked profiles with parent links. Read the profile's biography and sources section before trusting it. |
| Obituaries | Web search `"First Last" obituary <town or county> <death year>`; funeral home sites, legacy.com, local newspaper archives | Parents, spouse (often maiden name), siblings, children, places. The best bridge from the living generation to the first deceased one. |
| Find a Grave | Web search `site:findagrave.com "First Last" <county or state>`, then fetch the memorial page | Exact dates, burial place, photos of headstones, **family links** to parents and spouse memorials. Volunteer-compiled: the headstone photo is evidence, the bio is a lead. |
| FamilySearch public pages | Web search; open only pages that don't require sign-in | Indexed vital records and the occasional public tree person. Most of FamilySearch needs a login, so skip it unless the page opens. |
| State and county archives, Chronicling America (loc.gov), Internet Archive (county histories, city directories) | Web search or fetch | Older generations (pre-1930): county histories often contain family sketches. |
| Local files | `mdfind -name .ged` and `mdfind -name people.json` (shoebox keeps one in `<out>/.shoebox/`) | An existing GEDCOM, or shoebox's flattened tree. Ask before using one that isn't obviously the user's family. |

When a site blocks fetching or returns nothing, say so in the report and try the next
source; don't fill the gap from memory.

## Accepting a match

Accept a record as the ancestor only when it agrees with the established person on
**at least two independent points** beyond the name: a date (±2 years), a place
(same county or a neighboring one), or a named relative. Then set `confidence`:

- **high**: a record that explicitly names the relationship (an obituary naming the
  child, a death certificate listing parents, Find a Grave family links backed by a
  headstone), plus two matching points.
- **medium**: two matching points, but the relationship is inferred (right age, right
  county, same household in a compiled tree).
- **low**: a plausible candidate with one matching point. Keep it, mark it, and list it
  for the user to confirm. A `low` person's parents are not researched further.

Write the reasoning into `basis` in one sentence: which record, which points matched.

## Conflicts and dead ends

- Two sources disagree on a date: use the record made closest to the event. For a death
  date, a death certificate beats an obituary, which beats an online tree. For a birth
  date, a birth or baptism record or an early census beats a death certificate, whose
  informant was often guessing. Record the losing value in `notes`.
- Two candidates fit equally: don't pick. Leave the slot empty, describe both in the
  child's `notes`, and ask the user.
- Stop a line at the first unknown. A guessed great-grandparent poisons everything
  above them.
- Common names (John Smith in a big county) need a third matching point.
