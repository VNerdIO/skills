---
name: grocery-list
description: Organize a grocery list by store aisle in walking order for Publix or Food City, check each item against the store's current weekly-ad specials (sales, BOGOs, ValuCard prices) and push the result into Apple Reminders. Use this whenever the user shares a shopping or grocery list, asks what's on sale at Publix or Food City, wants a list sorted by aisle, or is planning a grocery trip, even if they don't name the skill.
---

# Grocery list

Turn a messy grocery list into one sorted for walking through the store, with this
week's specials noted next to the items that have them, and put it in Apple Reminders so
it can be checked off on the phone in the store.

## Inputs

- **The list**: pasted text, a file, or items named in chat. Normalize obvious
  shorthand ("OJ" → orange juice, "TP" → toilet paper) and merge duplicates.
- **Store**: `publix` or `foodcity`. If the user doesn't say, ask. Don't guess.
- **ZIP code**: weekly ads are regional. Use the one in the store's aisle file under
  "My store". If it's unknown, ask, then save it there.

## Workflow

Scripts live in `scripts/` next to this file and need only the Python 3 standard library.

### 1. Sort by aisle

Read the store's map: [`references/publix.md`](references/publix.md) or
[`references/foodcity.md`](references/foodcity.md). Corrections under "My store" override
the generic table. Put each item in a section, then order the sections by walking order.
If an item could go in two sections, pick the likelier one. Don't ask about it.

### 2. Look up specials

```bash
python3 scripts/specials.py --store publix --zip 37919 milk "ground beef" bananas
```

The script searches the store's weekly ad on Flipp (one request per item) and prints JSON
with up to 5 current deals per item. The search is fuzzy, so **judge each deal yourself**.
"milk" can return evaporated milk or milk chocolate, and a `score` of 1.0 only means the
words overlap. Attach a deal only when it's the product the user means, or an obvious
substitute (another brand of the same thing). Note "With Card" prices at Food City, and
show BOGOs as BOGO.

Also scan for strong deals on close substitutes ("chicken thighs are BOGO, you listed
breasts") and mention them in chat, but don't add them to the list.

If the request fails or a store returns nothing at all, tell the user and continue
without specials. Don't invent prices.

### 3. Push to Reminders

Write a JSON file in the scratchpad and run the push:

```json
{"list": "Publix 11/14",
 "items": [{"title": "Produce · Bananas", "notes": ""},
           {"title": "Meat · Ground beef", "notes": "SALE Lean Ground Beef $6.99 lb, save up to $4.29/lb, thru 11/17"}]}
```

```bash
python3 scripts/reminders.py /path/to/list.json --dry-run   # check first
python3 scripts/reminders.py /path/to/list.json
```

- Name the list `<Store> <M/D>` for the trip date. Items go in walking order.
- Title format: `<Section> · <Item>`, plus a quantity if one was given.
- Notes: the deal, price, savings and the ad's end date (the local day before
  `valid_to`, which is stored in UTC).
- The first run triggers a macOS prompt to let the terminal control Reminders. If it
  fails with "not authorized", ask the user to allow it under System Settings → Privacy &
  Security → Automation.

### 4. Report

In chat, show the sorted list as a compact Markdown checklist grouped by section, with
sale items marked, then a one-line savings summary and any substitute deals worth a look.

## Learning the store

When the user corrects a section ("eggs are on aisle 9 at my Publix") or gives their
store's location, record it under "My store" in that store's aisle file. That keeps the
next list right. Keep corrections short, one line each.

## Limits

- Specials come from the printed weekly ad as published on Flipp. Digital coupons
  clipped in the Publix or Food City app (and Publix "extra savings") need a login and
  aren't included.
- Flipp is an unofficial data source with no published API. If its responses change shape,
  `specials.py` needs updating.
