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
| National Archives (NARA) | In Chrome, no login: AAD and the Catalog (see below) | WWII Army enlistments (birth year, county, enlistment date, occupation, marital status); Civil War service records, Union and Confederate, and pension index cards. |
| State and county archives, Internet Archive (county histories, city directories) | Web search or fetch | Older generations (pre-1930): county histories often contain family sketches. |
| Local files | `mdfind -name .ged` and `mdfind -name people.json` (shoebox keeps one in `<out>/.shoebox/`) | An existing GEDCOM, or shoebox's flattened tree. Ask before using one that isn't obviously the user's family. |

`loc.gov/free-to-use/genealogy` is a gallery of rights-free images (decorative family
registers, county maps), not records; the records are in Chronicling America.

### Using Chronicling America

- Papers before about 1920 seldom printed given names in full, and married women appear
  under the husband's name (`Mrs. J. T. Smith`). But the search index drops single
  letters, so `"W. R. Dunlap"` searches for every Dunlap. For initials, narrow by
  `--county` and a short date range and read the excerpts. `loc.py` matches the
  initials in the OCR, so a hit with no excerpt is a different Dunlap.
- Phrase search on full words is exact, but OCR is not: a name broken across a line, or misread
  (`Dzath of`), can hide a real hit. Try a surname plus the town, too.
- Small-town "correspondent" columns (`Concord Items`) list visits, illnesses and
  deaths. They're often the only print record of a rural family.
- A matching name in another county is usually someone else. One 1866 search turned up a
  Rector Smith in Columbia, 200 miles from the family's Rector Smith. Apply the
  two-point rule below before using a notice.
- LOC rate-limits searches and page reads hard. Too many requests in a row brings a
  Cloudflare challenge that lasts up to an hour. `loc.py` spaces its requests, so run
  searches one after another, never in parallel. If a 429 persists, stop and say so.

### Using the National Archives

`archives.gov/research/genealogy` itself is guides. Its census, immigration and
naturalization records are mostly searched through FamilySearch or Ancestry. Two of its
own tools are worth a pass. Both refuse plain `curl` (AAD returns 403, the Catalog
returns an empty app shell) but open without a login in a Chrome tab.

- **AAD, WWII Army Enlistment Records** (`aad.archives.gov/aad/fielded-search.jsp?dt=893&tf=F&cat=all&bc=sl`).
  About 9 million Army enlistments, 1938–46. That's not every soldier, and there's no Navy or Marines. Fill
  the NAME field (`SURNAME GIVEN`) and YEAR OF BIRTH (two digits) and submit the form in
  the page. The free-text box matches any word and floods with namesakes. Names are
  stored as `SURNAME#GIVEN#INITIAL`. Many 1942 residence fields read "Undefined Code",
  but the county code is often still the county's FIPS number. Cite the record page as
  `record-detail.jsp?dt=893&rid=<rid>`, which is stable. One record gives name, birth year and state,
  and usually a residence county, so apply the two-point rule. The county and a known
  middle initial are what settle it.
- **National Archives Catalog** (`catalog.archives.gov/search?q="Surname, Given"&availableOnline=true`).
  Civil War compiled service records are digitized and searchable by name. Confederate
  records are titled `<State> - <Unit> - Compiled Service Record of Surname, Given`, with the age at
  enlistment. Union records are titled `Surname, Given - Age N, Year: YYYY - <Unit>`. Pension index cards are in RG 15. Each
  record's `catalog.archives.gov/id/<NAID>` page lists its card images. From a Catalog tab,
  `fetch('/proxy/records/search?naId_is=<NAID>')` returns JSON whose
  `digitalObjects[].objectUrl` images download with `curl`. The search endpoint
  answers a few times in a row, then returns the app shell, so read the results page instead.
  Cards aren't in date order: read them all. The quickest exclusion is a muster roll
  showing the man alive after your ancestor's death. Enlistment place matters too,
  because regiments were raised locally.
- **Pension index cards** (RG 15, titled `Pension File Number N`) come up in the same
  name search. One card can list several unrelated pensioners, so check the card image for
  your name and unit. A widow's application (WO) or certificate (WC) shows the soldier
  died before she applied. Application numbers rose over time, so a low one dates the
  claim roughly. The pension file itself isn't online. Note it as a lead, because it usually
  gives the death date and the widow's name.
- **WWII draft cards** are series named `Draft Registration Cards for <State>, October 16,
  1940–March 31, 1947`, covering men born 1896–1929. The 1942 cards for older men are a
  separate series. Open the series page first, because many say "Not yet available online"
  (Tennessee and South Carolina did in 2026), while others are partly scanned. Scanned
  file units are alphabetical ranges of about 2,000 images, such as `Arvin, Vernie - Asher,
  Theodore`, with no transcription. Cards run by surname, then given name, front and
  back alternating. Find a man by checking a few images, cutting the range in half each
  time: get the image URLs from the file unit's
  `digitalObjects`, download them with `curl`, and convert the TIFFs with `sips -s format jpeg`.
  Cite the file unit's `/id/<NAID>` page plus the image number.
- The 1950 census site has an open JSON search
  (`1950census.archives.gov/api/search?name=&state=&county=`), but its name matching is
  loose. FamilySearch's 1950 index is easier to use.

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
