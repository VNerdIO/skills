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
- **Read-only, public, no login** unless the user is signed in. Without the user's own
  session, use only sources that open without signing in. When a result is behind a
  paywall (Ancestry, Newspapers.com, MyHeritage), note it in the person's `notes` as a
  lead for the user and move on. Never sign in for the user, and never work around a
  paywall, view limit or bot challenge.
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
| Chronicling America (Library of Congress newspapers, about 1770–1963) | `scripts/loc.py search "First Last" --state <state> [--county <county>] --from YYYY --to YYYY` | Death and marriage notices, local "personals" columns, court and estate notices, veterans' lists. Prints the OCR lines around each hit. Coverage differs by state and paper, so an empty result means "not in the digitized papers", not "no notice". |
| State and county archives, Internet Archive (county histories, city directories) | Web search or fetch | Older generations (pre-1930): county histories often contain family sketches. |
| Local files | `mdfind -name .ged` and `mdfind -name people.json` (shoebox keeps one in `<out>/.shoebox/`) | An existing GEDCOM, or shoebox's flattened tree. Ask before using one that isn't obviously the user's family. |

`loc.gov/free-to-use/genealogy` is a gallery of rights-free images (decorative family
registers, county maps), not records; the records are in Chronicling America.

### Using Chronicling America

- Search initials as well as full names (`"W. R. Dunlap"`, `"Mrs. J. T. Smith"`):
  papers before about 1920 seldom printed women's or men's given names in full.
  Married women appear under the husband's name.
- Phrase search is exact, but OCR is not: a name broken across a line, or misread
  (`Dzath of`), can hide a real hit. Try a surname plus the town, too.
- Small-town "correspondent" columns (`Concord Items`) list visits, illnesses and
  deaths. They're often the only print record of a rural family.
- A matching name in another county is usually someone else. One 1866 search turned up a
  Rector Smith in Columbia, 200 miles from the family's Rector Smith. Apply the
  two-point rule below before using a notice.
- LOC rate-limits searches and page reads hard. Too many requests in a row brings a
  Cloudflare challenge that lasts up to an hour. `loc.py` spaces its requests, so run
  searches one after another, never in parallel. If a 429 persists, stop and say so.

### Signed-in sites

When the user has signed in to a site in Chrome and asks you to use it, work in a new
tab of their browser. They sign in; you never type their password.

- **FamilySearch**: record search at
  `familysearch.org/search/record/results?q.givenName=..&q.surname=..&q.birthLikeDate.from=..&q.anyPlace=..`.
  Each record is an `ark:/61903/1:1:...` page. Open the image ("View Original
  Document") whenever there is one. Indexes get places wrong. For example, 1870 and
  1880 Knox County, Tennessee districts are indexed as "Grainger County", but the image
  shows the right county. Free and especially useful: state death certificates naming
  parents (Tennessee 1914–1960s, among others), and the SSA NUMIDENT index, whose
  claim entries give parents' names for 20th-century births.
- **Newspapers.com**: a Basic subscription can search all papers but can only open the
  ones in its Basic set. "Publisher Extra" papers show hits whose pages stay locked.
  Other users' public clippings (`/clippings/?query=`) open, up to a monthly view
  limit. Note locked hits as leads, with paper, date and page.
- Record each page you rely on as a source with its URL. A FamilySearch ark is a
  stable citation.

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
