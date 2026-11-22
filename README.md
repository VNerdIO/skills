# Skills

A personal collection of [Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
for Claude: reusable instructions, reference notes and helper scripts that Claude loads
when a task calls for them. These are general-purpose skills I use day to day, not tied
to any one project.

## Skills

| Skill | What it does |
| --- | --- |
| [`shoebox`](shoebox/) | Turns Epson FastFoto scans of old family photos into a labeled library. Transcribes handwriting from photo backs, writes EXIF/XMP dates, places and captions, fixes orientation, and tags people using face clustering and optional GEDCOM family trees. |
| [`family-tree`](family-tree/) | Builds a four-generation family tree as a GEDCOM 5.5.1 file plus an offline, single-page pedigree chart. Reads existing GEDCOM files, or interviews you and researches deceased ancestors in WikiTree, obituaries and Find a Grave, citing every fact. |
| [`grocery-list`](grocery-list/) | Sorts a grocery list by aisle in walking order for Publix or Food City, notes this week's weekly-ad specials next to matching items, and pushes the list into Apple Reminders. |
| [`osint`](osint/) | Works out who is behind an IP address, username or email from free public sources (RDAP, Shodan InternetDB, WhatsMyName's ~700 sites, GitHub, Gravatar, PGP keyservers, Google dorks) and writes a cited report that grades every claim confirmed, likely or possible. |
| [`zscaler-troubleshooter`](zscaler-troubleshooter/) | Diagnoses Zscaler problems (ZPA private app access, ZIA web/SSL blocks, Client Connector tunnel and auth issues) with read-only API and endpoint checks, then names the likely cause and the fix. |

## Layout

Each skill is a folder with a `SKILL.md` at its root:

```
<skill-name>/
├── SKILL.md        # frontmatter (name, description) + instructions
├── references/     # longer docs Claude reads only when needed
└── scripts/        # helper scripts the instructions call
```

The `description` in the frontmatter is what Claude uses to decide when to load a skill,
so it lists the situations and phrases that should trigger it.

## Installing

### Claude Code

Link (or copy) a skill folder into your personal skills directory:

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/family-tree" ~/.claude/skills/family-tree
ln -s "$PWD/grocery-list" ~/.claude/skills/grocery-list
ln -s "$PWD/osint" ~/.claude/skills/osint
ln -s "$PWD/shoebox" ~/.claude/skills/shoebox
ln -s "$PWD/zscaler-troubleshooter" ~/.claude/skills/zscaler-troubleshooter
```

Symlinks keep the installed skills in sync with this repo. To use a skill in a single
project only, put it under that project's `.claude/skills/` instead.

### Claude.ai / Claude Desktop

Zip the skill folder (the folder itself, not just its contents) and upload it under
**Settings → Capabilities → Skills**:

```bash
zip -r shoebox.zip shoebox
```

`*.zip` and `*.skill` are gitignored, so build archives don't get committed.

## Requirements

Each skill lists its own setup in its `SKILL.md`. In short:

- **family-tree**: Python 3 (standard library only). Research uses WikiTree's public API
  and public web pages, with no account or API key. Living people are never searched
  online.
- **grocery-list**: macOS with Python 3 (standard library only). Specials come from
  Flipp's weekly-ad search, so no account or API key is needed. Pushing to Reminders needs
  the one-time macOS Automation permission.
- **osint**: Python 3 (standard library only), no account or API key. Optional keys add
  coverage: `ABUSEIPDB_KEY`, `GREYNOISE_KEY`, `VT_KEY` (IPs) and `HIBP_KEY` (email breaches).
  See [`osint/README.md`](osint/README.md) for where to get each key and which services
  are worth adding.
  The report stops at online attribution and leaves out home addresses, phone numbers and relatives.
- **shoebox**: macOS or Linux with `exiftool` (`brew install exiftool`) and Python 3.11–3.13
  (`uv` recommended). `scripts/setup.sh` creates a virtualenv at
  `~/.local/share/shoebox/venv`. Face matching uses `face_recognition` (dlib), which is
  optional. If it fails to build, the skill falls back to vision-only matching.
- **zscaler-troubleshooter**: PowerShell 5.1+ or PowerShell 7. API credentials come from
  environment variables only: either OneAPI (`ZSCALER_CLIENT_ID`, `ZSCALER_CLIENT_SECRET`,
  `ZSCALER_VANITY_DOMAIN`, `ZPA_CUSTOMER_ID`) or legacy per-product keys (`ZPA_*`, `ZIA_*`).
  See [`references/api-reference.md`](zscaler-troubleshooter/references/api-reference.md).
  Use a read-only API role.

## Adding a skill

1. Create `<skill-name>/SKILL.md` with `name` and `description` frontmatter.
2. Keep `SKILL.md` focused on the workflow. Move long reference material into
   `references/` and repeatable steps into `scripts/`.
3. Never commit credentials. Read secrets from environment variables. The `.gitignore`
   blocks common secret files (`.env`, keys, `credentials*`, `token.json`), but don't
   rely on it alone.
4. Add a row to the table above.
