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
kitoblar/             generated — uz catalogue + book pages
kitoblar/ru/          generated — ru catalogue + book pages
content/books/uz/     Markdown sources (uz)
content/books/ru/     Markdown sources (ru)
assets/img/books/     book covers (uploaded via the admin)
tools/build-books.py  regenerates the catalogue from Markdown
tools/hash-password.py generates the admin password hash
tools/test-worker.mjs  tests for the admin Worker
admin/                the publisher's editor page (static)
worker/               Cloudflare Worker: login + GitHub commits
tools/make-og-image.py regenerates the social cards
assets/css/styles.css hand-written CSS, no framework
assets/js/main.js     mobile menu, sticky header, scroll reveal, back-to-top
assets/img/           artwork pulled from the Telegram channel
```

## Books

The catalogue is the part the publisher maintains. Books are written as
Markdown and compiled to committed HTML, so Pages still serves a static site.

```bash
python3 tools/build-books.py
```

Reads `content/books/<lang>/<slug>.md` and writes:

| Output | URL |
| --- | --- |
| `kitoblar/index.html` | `/kitoblar/` |
| `kitoblar/<slug>.html` | `/kitoblar/<slug>.html` |
| `kitoblar/ru/index.html` | `/kitoblar/ru/` |
| `kitoblar/ru/<slug>.html` | `/kitoblar/ru/<slug>.html` |

It also rewrites two blocks on each homepage: the **Kitoblar** cards
(`BOOKS:START` / `BOOKS:END`, newest three plus an "all books" link) and the
featured release (`FEATURED:START` / `FEATURED:END`). **Nothing inside those
markers or under `kitoblar/` should be hand-edited** — it is overwritten on the
next run. The command is idempotent.

### Front matter

```
title: Daloilul xoyrot
author: Muhammad ibn Jazuliy
date: 2026-09-20
description: One sentence, used on the card and as og:description.
image: daloilul-xoyrot.jpg
pages: 236 bet
cover: Qattiq muqova
language: Arabiy, asl holida
price: 60 000 so'm
tag: To'plam · 5 kitob
quote: A short line shown on the card.
featured: yes

The long description, in Markdown.
```

`title`, `author`, `date`, `description` and `image` are required; the rest are
optional and simply omitted when blank. Covers live in `assets/img/books/`, and
the build **fails** if a book references one that is missing — better than
shipping a broken image.

Books are ordered newest first. The featured release is the newest book marked
`featured: yes`, falling back to the newest book overall.

## Admin (publisher login)

The publisher manages books at **https://tavfiqnashr.uz/admin/** with a username
and password — no GitHub account. The site stays static; only `/api/admin/*` is
dynamic, served by a Cloudflare Worker.

```
publisher → /admin/ (static page on Pages)
          → POST /api/admin/* → Cloudflare Worker
              · checks username + PBKDF2 password hash
              · commits content/books/<lang>/<slug>.md
              · commits covers to assets/img/books/
          → Action "Build books" runs tools/build-books.py, commits the HTML
          → Pages redeploys (1–2 minutes)
```

Cover images are uploaded in the editor, capped at 2MB, and the file name is
slugified server-side. The GitHub token lives only as a Worker secret.

### One-time setup

1. **Fine-grained GitHub token** — repository access limited to
   `Usmon-Mukhammad/tavfiqnashr`, permission **Contents: Read and write**.
2. **Password:** `python3 tools/gen-admin-password.py` writes a generated
   password to `worker/.admin-password.txt` and prints only its hash.
3. **Deploy and set secrets:**

   ```bash
   cd worker
   npm install --save-dev wrangler
   npx wrangler deploy
   npx wrangler secret put ADMIN_USERNAME
   npx wrangler secret put ADMIN_PASSWORD_HASH
   npx wrangler secret put SESSION_SECRET
   npx wrangler secret put GITHUB_TOKEN
   ```

4. **Rate-limit rule** in Cloudflare (Security → WAF → Rate limiting) on
   `/api/admin/login`, e.g. 5 requests per minute per IP.

PBKDF2 is pinned to 100 000 iterations because Workers' WebCrypto rejects more;
`tools/test-worker.mjs` asserts this so it cannot regress.

### Tests

```bash
node tools/test-worker.mjs
```

22 checks: login, session forgery and expiry, the CSRF header, slug and front
matter validation, create/update/delete, cover upload (naming, extension, size
cap), and that the token never appears in a response.

## Sections

| Section | Uzbek anchor | Russian anchor | Content |
| --- | --- | --- | --- |
| Hero | `#top` | `#top` | Tagline, CTAs, stats |
| About | `#biz-haqimizda` | `#o-nas` | Positioning, four trust points |
| New release | — | — | Featured book (generated) |
| Books | `#kitoblar` | `#knigi` | Newest three books (generated) |
| Series | `#sittayi` | `#sittai` | The five-book classical Turkic series |
| Quotes | `#hikmatlar` | `#mudrosti` | Four quotes drawn from published books |
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
- **Book pages share the site-wide social card.** A per-book `og:image` (the
  cover) would make shared links stronger; the cover is already in the repo.
- **The Russian book entries are my translations**, not publisher-supplied copy.
- The fonts load from Google Fonts, so first paint depends on an external request.
  Self-host the two families if the site must work fully offline.
