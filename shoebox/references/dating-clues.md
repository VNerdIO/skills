# Dating clues for prints

Combine several clues, and say which ones you used in `basis`. A single clue usually gives
a range. Where several clues overlap, the range narrows.

## On the back (strongest after handwriting)

- **Lab and processor stamps**: month and year codes such as "AUG 78", "MAR 1985" or
  "Week 23". These record when the film was processed, which is usually weeks or months after
  the shot. Christmas photos are often processed in January.
- **Paper watermarks**: Kodak's repeating "KODAK PAPER" or "THIS PAPER MANUFACTURED BY KODAK"
  marks changed design over the decades. "Kodak Royal", "Fujicolor Crystal Archive" (late 1990s
  and later), Agfa and Konica each suggest an era. Use the pattern as a rough decade signal,
  not a precise date.
- **Negative and frame numbers** printed along the edge (1980s and later) show which prints
  came off the same roll, so they share a date and an event.
- **Handwriting style and ink**: the same writer, same pen and same phrasing across several
  backs usually means one sorting session, which often covers one period.

## On the front

- **Camera date imprint** (orange digits in a corner, such as `'87 6 14`): exact, but check
  for a camera clock that was never set (for example `'80 1 1` on a 1990s photo).
- **Print format**: deckled (scalloped) edges were common from the 1940s to the early
  1960s. Square prints with rounded corners suggest 126 Instamatic, roughly 1963–1980s. Small
  white-bordered prints are typical of the 1950s–60s. Borderless glossy 4×6 suggests the late
  1980s onward. Instant prints are integral-film Polaroids, 1972 and later. 110-format prints
  are small and grainy, 1972–1990s.
- **Color shifts**: a magenta or red cast is typical of faded 1960s–70s prints. Black and white
  as an everyday snapshot format points to before about 1970.
- **Clothing, hair, glasses, cars, TVs, toys and decor**: these are rough decade signals,
  and old clothes persist, so treat them as a floor, not a pinpoint.

## From people (GEDCOM)

Estimate the apparent age of anyone who is identified, then use date = birth year + apparent
age. Give a wide range for adults (±5 years) and a narrow one for young children (±1–2 years).
Babies are very precise. A baby who is named, or in the arms of a known parent, often dates a
photo to within a year. Sanity checks:

- Nobody appears before their birth or after their death. If they do, the ID or the date is wrong.
- A couple shown with their children dates the photo after the children were born.

## From neighbors (propagation)

Photos scanned one after another often came from the same envelope or roll. A run of nearby
`seq` numbers that share setting, light, outfits or print stock is probably one event. Give
the whole run the best-evidenced date in the group, with `source: inferred` and a basis such
as "same outfits and backyard as 0041 (dated back: 4 Jul 1976)". Lower the confidence by one
step for each hop away from the anchor photo.
