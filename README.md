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
assets/css/styles.css hand-written CSS, no framework
assets/js/main.js     mobile menu, sticky header, scroll reveal, back-to-top
assets/img/           artwork pulled from the Telegram channel
```

## Sections

| Section | Uzbek anchor | Russian anchor | Content |
| --- | --- | --- | --- |
| Hero | `#top` | `#top` | Tagline, CTAs, stats |
| About | `#biz-haqimizda` | `#o-nas` | Positioning, four trust points |
| New release | — | — | Featured: *Daloilul xoyrot* |
| Books | `#kitoblar` | `#knigi` | Four catalogue cards |
| Series | `#sittayi` | `#sittai` | The five-book classical Turkic series |
| Quotes | `#hikmatlar` | `#mudrosti` | Four quotes drawn from published books |
| Contact | `#aloqa` | `#kontakty` | Telegram, two phone numbers, contact bot |

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
  the *Sittayi turkiy* series, and *Flowgorithm* (60 000 so'm).
- **Quotes** — verbatim from the channel's book excerpt posts.
- **Contacts** — +998 97 521 67 00 (general), +998 99 725 12 44 (Flowgorithm orders),
  [@Akrom_Malikka_maktubBot](https://t.me/Akrom_Malikka_maktubBot).
- **Regulatory notes** — the Committee for Religious Affairs approval references
  quoted in the *Ibodati Islomiyya* and *Risolayi marg'uba* posts.

The subscriber count in the hero (840+) is a snapshot from **9 August 2026** and is
hardcoded — update it in `index.html` when it drifts.

## Images

`assets/img/*.jpg` are the channel's own promotional graphics, downloaded from
Telegram's CDN so the site has no external dependencies. Two notes:

- `flowgorithm.jpg` is only 180×320 — the largest size Telegram serves publicly for
  that post. Its card uses `object-fit: contain` so it is never upscaled into blur.
  Replace it with a proper cover shot when one is available.
- `logo.jpg` doubles as the favicon. A transparent SVG or PNG logo would be better;
  the current file is a JPEG with a cream background.

## Known gaps

- **No e-commerce.** Every "buy" action points to Telegram or a phone number, which is
  how the publisher currently sells. Add a cart only if they want to take orders online.
- **Prices** are only known for *Flowgorithm*; no other book has a published price.
- **The Russian text is a translation, not publisher-supplied copy.** Book and author
  names are transliterated (*Komil inson* → «Камиль инсан», *Aziziddin Nasafiy* →
  Азизуддин Насафи); the publisher may prefer different forms. Worth a review by a
  native speaker before launch.
- **No Uzbek Cyrillic version**, though part of the audience reads it — one of the
  book covers is set in Cyrillic.
- The fonts load from Google Fonts, so first paint depends on an external request.
  Self-host the two families if the site must work fully offline.
