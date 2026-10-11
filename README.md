# TAVFIQNASHR — welcome website

A static welcome site for the **TAVFIQNASHR** publishing house
([@tavfiqnashr](https://t.me/tavfiqnashr) on Telegram), in two languages:

| Page | Language | Default |
| --- | --- | --- |
| `index.html` | Uzbek (Latin script) — the channel's own language | yes (`x-default`) |
| `ru.html` | Russian | — |

Both pages share `assets/`, so there is one stylesheet and one script to maintain.
A `UZ / RU` pill in the header switches between them, and each page carries
`hreflang` links to the other. **Adding a section means editing both files** — the
translations are hand-written, not generated at runtime.

## Deployment

Hosted on GitHub Pages from `main` at the repo root — no build step, no Actions
workflow. Pushing to `main` republishes within a minute or so.

- Repo: <https://github.com/ameer611/tavfiqnashr>
- Fallback URL: <https://ameer611.github.io/tavfiqnashr/>
- Custom domain: **tavfiqnashr.uz** (registered at ahost)

`CNAME` and `.nojekyll` at the repo root are both load-bearing: deleting `CNAME`
resets the custom domain, and `.nojekyll` stops Pages from running the files
through Jekyll.

### DNS records

`tavfiqnashr.uz` is an apex domain, so it needs **A records** — a CNAME is not
valid at the apex. In the ahost DNS panel:

| Type | Host | Value |
| --- | --- | --- |
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `ameer611.github.io.` |

Optional IPv6 (AAAA on `@`): `2606:50c0:8000::153`, `2606:50c0:8001::153`,
`2606:50c0:8002::153`, `2606:50c0:8003::153`.

Check propagation, then turn on HTTPS once GitHub has issued the certificate:

```bash
gh api repos/ameer611/tavfiqnashr/pages/health --jq '.domain | {dns_resolves, is_valid, reason}'
gh api -X PUT repos/ameer611/tavfiqnashr/pages -F https_enforced=true
```

## Running

No build step. Any static server works:

```bash
python3 -m http.server 4173
```

Then open <http://localhost:4173>. (A `.claude/launch.json` entry named `tavfiqnashr`
starts the same server from the editor's preview pane.)

## Structure

```
index.html            Uzbek page, all sections
ru.html               Russian page, same structure
blog/                 generated — uz listing + articles
blog/ru/              generated — ru listing + articles
content/blog/uz/      Markdown sources (uz)
content/blog/ru/      Markdown sources (ru)
tools/build-blog.py   regenerates the blog from Markdown
tools/hash-password.py generates the admin password hash
tools/test-worker.mjs  tests for the admin Worker
admin/                the publisher's editor page (static)
worker/               Cloudflare Worker: login + GitHub commits
tools/make-og-image.py regenerates the social cards
assets/css/styles.css hand-written CSS, no framework
assets/js/main.js     mobile menu, sticky header, scroll reveal, back-to-top
assets/img/           artwork pulled from the Telegram channel
```

## Blog

Articles are written as Markdown and compiled to static HTML — there is still no
build step at deploy time, the HTML is committed.

```bash
python3 tools/build-blog.py
```

That reads `content/blog/<lang>/<slug>.md` and writes:

| Output | URL |
| --- | --- |
| `blog/index.html` | `/blog/` |
| `blog/<slug>.html` | `/blog/<slug>.html` |
| `blog/ru/index.html` | `/blog/ru/` |
| `blog/ru/<slug>.html` | `/blog/ru/<slug>.html` |

It also rewrites the "latest articles" teaser on both homepages, between the
`<!-- BLOG:START -->` / `<!-- BLOG:END -->` markers. **Do not hand-edit anything
inside those markers or under `blog/`** — it is overwritten on the next run. The
command is idempotent: run it after any `.md` change and commit the result.

### Adding a post

Create `content/blog/uz/<slug>.md` (and the same `<slug>.md` under `ru/` for the
translation), then run the build. Front matter is `key: value` lines ended by a
blank line:

```
title: Tasavvuf nima? Mashhur ta'riflar
date: 2026-09-14
description: One sentence, used for the listing card and og:description.
source: "Tasavvuf bilan tanishuv" — Abdulvaliy Abdussalom
tags: Tasavvuf

Body starts here.
```

`title`, `date` and `description` are required; `source` and `tags` are optional.
Posts are ordered newest first by `date`.

Supported Markdown: `##`/`###` headings, paragraphs, `>` blockquotes (a line
starting with an em dash becomes the attribution), `-` and `1.` lists, `---`
rules, `**bold**`, `*italic*`, `[links](url)`. That subset is deliberate — the
parser is ~40 lines of stdlib in `tools/build-blog.py`, with no dependencies.

Matching slugs across `uz/` and `ru/` are linked as translations of each other.
If a slug exists in only one language, the build prints a note and that page's
language switcher points at the other language's blog index instead.

## Blog admin (publisher login)

The publisher writes posts at **https://tavfiqnashr.uz/admin/** with a username
and password — no GitHub account. The public site stays static; only
`/api/admin/*` is dynamic, handled by a Cloudflare Worker.

```
publisher → /admin/ (static page on Pages)
          → POST /api/admin/* → Cloudflare Worker
              · checks username + PBKDF2 password hash
              · commits content/blog/<lang>/<slug>.md via the GitHub API
          → Action "Build blog" runs tools/build-blog.py, commits the HTML
          → Pages redeploys (1–2 minutes)
```

The GitHub token lives only as a Worker secret and is never sent to the browser.

### One-time setup

1. **Create a fine-grained GitHub token** — github.com/settings/personal-access-tokens
   - Repository access: **only** `Usmon-Mukhammad/tavfiqnashr`
   - Permissions: **Contents → Read and write** (nothing else)

2. **Generate the password hash** (the password never leaves your machine):

   ```bash
   python3 tools/hash-password.py
   ```

3. **Deploy the Worker and set its secrets:**

   ```bash
   cd worker
   npm install --save-dev wrangler
   npx wrangler deploy
   npx wrangler secret put ADMIN_USERNAME
   npx wrangler secret put ADMIN_PASSWORD_HASH   # paste the hash from step 2
   npx wrangler secret put SESSION_SECRET        # openssl rand -base64 48
   npx wrangler secret put GITHUB_TOKEN          # the token from step 1
   ```

4. **Add a rate-limit rule** in Cloudflare (Security → WAF → Rate limiting) on
   path `/api/admin/login`, e.g. 5 requests per minute per IP. The Worker already
   delays failed logins, but this is the real brake on guessing.

Non-secret settings (repo owner, branch, session length) are plain `[vars]` in
`worker/wrangler.toml`.

### Changing the password

Re-run `tools/hash-password.py` and `npx wrangler secret put ADMIN_PASSWORD_HASH`.
Rotating `SESSION_SECRET` immediately signs out any active session.

### Tests

```bash
node tools/test-worker.mjs
```

16 checks covering login, session forgery and expiry, the CSRF header, slug and
front-matter validation, create/update/delete against a mocked GitHub API, and
that the token never appears in a response.

## Sections

| Section | Uzbek anchor | Russian anchor | Content |
| --- | --- | --- | --- |
| Hero | `#top` | `#top` | Tagline, CTAs, stats |
| About | `#biz-haqimizda` | `#o-nas` | Positioning, four trust points |
| New release | — | — | Featured: *Daloilul xoyrot* |
| Books | `#kitoblar` | `#knigi` | Three catalogue cards |
| Series | `#sittayi` | `#sittai` | The five-book classical Turkic series |
| Quotes | `#hikmatlar` | `#mudrosti` | Four quotes drawn from published books |
| Blog teaser | `#maqolalar` | `#stati` | Latest three articles (generated) |
| Contact | `#aloqa` | `#kontakty` | Telegram channel, phone, contact bot |

Anchors are localised, so the language pill always links to the page root rather
than preserving the reader's scroll position.

## Mobile

Small screens get their own treatment rather than a narrowed desktop layout:

- **Menu** — a rounded slide-down panel with a blurred backdrop, 52 px rows with
  chevrons, staggered entry, body scroll lock, and close on Esc / backdrop / link tap.
- **Crops** — book cards switch to a top-anchored square (then 4:3 at one column).
  These are promo graphics with their headline at the top, so the desktop centred
  4:5 crop cut the title off.
- **Stats** — an even three-column row with hairline dividers instead of a wrapping flex row.
- **Series** — the index becomes a gold pill above each title instead of a side column.
- **Touch targets** — nav rows, buttons, contact cards and the language pill are all
  ≥ 36 px; contact cards gain a trailing arrow.
- **Safe areas** — footer and back-to-top respect `env(safe-area-inset-*)` for notched phones.

## Where the content came from

Everything is sourced from the channel's public posts (`t.me/s/tavfiqnashr`):

- **Books** — *Daloilul xoyrot* (Muhammad ibn Jazuliy, 236 pp., hardcover),
  *Komil inson* (Aziziddin Nasafiy), *Tasavvuf bilan tanishuv* (Abdulvaliy Abdussalom),
  and the *Sittayi turkiy* series.
- **Quotes** — verbatim from the channel's book excerpt posts.
- **Contacts** — +998 97 521 67 00 (general) and
  [@Akrom_Malikka_maktubBot](https://t.me/Akrom_Malikka_maktubBot).
- **Regulatory notes** — the Committee for Religious Affairs approval references
  quoted in the *Ibodati Islomiyya* and *Risolayi marg'uba* posts.

The subscriber count in the hero (840+) is a snapshot from **9 August 2026** and is
hardcoded — update it in `index.html` when it drifts.

## Images

`assets/img/*.jpg` are the channel's own promotional graphics, downloaded from
Telegram's CDN so the site has no external dependencies. One note:

- `logo.jpg` doubles as the favicon. A transparent SVG or PNG logo would be better;
  the current file is a JPEG with a cream background.

## Known gaps

- **No e-commerce.** Every "buy" action points to Telegram or a phone number, which is
  how the publisher currently sells. Add a cart only if they want to take orders online.
- **No prices are shown.** The channel has not published a price for any of the
  three titles currently listed.
- **The Russian text is a translation, not publisher-supplied copy.** Book and author
  names are transliterated (*Komil inson* → «Камиль инсан», *Aziziddin Nasafiy* →
  Азизуддин Насафи); the publisher may prefer different forms. Worth a review by a
  native speaker before launch.
- **No Uzbek Cyrillic version**, though part of the audience reads it — one of the
  book covers is set in Cyrillic.
- **The seed blog posts are compiled from the channel's own published excerpts**
  and attributed to the source books, but nobody at the publisher has reviewed
  the selection or the Russian translations of them yet.
- **Blog posts share the site-wide social card.** Per-article images would need
  `og:image` support in the front matter.
- The fonts load from Google Fonts, so first paint depends on an external request.
  Self-host the two families if the site must work fully offline.
