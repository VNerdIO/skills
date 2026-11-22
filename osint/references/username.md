# Usernames

## Reading `username.py` output

`hits` are sites where the page matched WhatsMyName's account-exists signature. Treat
each hit as **possible** until correlated: a common handle such as `torvalds` returns
over 90 hits, most of them strangers. A rare handle (`zq_kestrel77`) with many hits is
more likely one person, but still needs corroboration.

Work the hits in this order, because these sites expose the most linkable detail:

1. **Developer sites** (GitHub, GitLab, Bitbucket, Docker Hub, HuggingFace,
   StackOverflow): real names, employers, personal sites, and emails in commits.
   `--profiles` pulls GitHub's public commit-author emails. For older commits, open
   `https://github.com/<user>/<repo>/commits` and add `.patch` to a commit URL
   (`…/commit/<sha>.patch`). The `From:` line shows the author email.
2. **Identity hubs** (Keybase, Gravatar, linktr.ee, about.me, Mastodon, Bluesky): the
   owner lists their other accounts here, which makes those links **confirmed**.
   Keybase proofs in `--profiles` are cryptographically verified.
3. **Social and creative sites** (Reddit, Twitch, YouTube, DeviantArt, SoundCloud):
   bios, profile photos, writing style and active hours.
4. Everything else: open only to check avatar or bio matches against what you already
   have.

`unclear` hits matched both the exists and missing signatures. Open them by hand.
`errors` are sites that timed out or blocked automated checks.

## Correlation signals

- **Same avatar**: reverse-search the image with Google Lens
  (`https://lens.google.com/uploadbyurl?url=<image-url>`), Bing Visual Search,
  TinEye (`https://tineye.com/search?url=<image-url>`) and Yandex Images. An avatar
  reused across sites is strong evidence. Stock or cartoon avatars are not.
- **Cross-links**: a profile's website or "links" field pointing at another account.
- **Account age**: creation dates across sites that line up with one persona's
  timeline. A 2009 account cannot belong to someone who adopted the handle in 2020.
- **Writing and interests**: the same niche topics, phrasing, language and time zone
  across sites. Supporting evidence only, never enough by itself.
- **Name variants**: `jsmith`, `j.smith`, `jsmith_`, and handles with the birth year
  appended. Run `username.py` on variants seen in real profiles, not on guesses.

## Manual sources (free)

| Source | Use |
| --- | --- |
| `https://whatsmyname.app` | Same dataset as the script, with a browser UI to double-check hits |
| `https://web.archive.org/web/*/<profile-url>` | Deleted or edited profiles, old bios and links |
| `https://www.reddit.com/user/<user>/` | Post history: interests, region and time zone from activity |
| `https://socialblade.com/search/search?query=<user>` | Username change history on YouTube, Twitch and others |
| `https://namechk.com` | Second opinion on availability |
| Sherlock / Maigret (`pipx install sherlock-project` / `maigret`) | Extra site coverage if installed. Run only when the user wants deeper enumeration |
