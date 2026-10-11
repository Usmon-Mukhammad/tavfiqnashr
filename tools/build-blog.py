#!/usr/bin/env python3
"""Generate the blog from Markdown sources. Standard library only.

    python3 tools/build-blog.py

Reads   content/blog/<lang>/<slug>.md
Writes  blog/index.html            uz listing      /blog/
        blog/<slug>.html           uz article
        blog/ru/index.html         ru listing      /blog/ru/
        blog/ru/<slug>.html        ru article
        index.html, ru.html        teaser section, between BLOG:START/END markers

Front matter is `key: value` lines terminated by a blank line; everything after
is Markdown. Keys: title, date (YYYY-MM-DD), description, source, tags.

Pages are written whole on every run, so the command is idempotent — run it
after editing any .md and commit whatever changes.
"""
from __future__ import annotations

import html
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://tavfiqnashr.uz"

MONTHS = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
}

L = {
    "uz": {
        "htmllang": "uz",
        "dir": "blog",
        "depth": 1,
        "home": "index.html",
        "other_home": "ru.html",
        "blog_url": f"{SITE}/blog/",
        "rel_from_home": "blog/",
        "rel_other_index": "ru/",
        "skip": "Asosiy qismga o‘tish",
        "brand_sub": "nashriyoti",
        "lang_label": "Sayt tili",
        "menu_label": "Asosiy menyu",
        "nav_toggle": "Menyuni ochish",
        "nav": [("#biz-haqimizda", "Biz haqimizda"), ("#kitoblar", "Kitoblar"),
                ("#sittayi", "Sittayi turkiy"), ("#hikmatlar", "Hikmatlar"),
                ("#aloqa", "Aloqa")],
        "blog_nav": "Maqolalar",
        "tg": "Telegram kanal",
        "listing_title": "Maqolalar",
        "listing_kicker": "Bloglar",
        "listing_lead": "Nashriyotimiz kitoblaridan parchalar, tasavvuf istilohlari va "
                        "ajdodlar merosiga oid maqolalar.",
        "listing_meta_title": "Maqolalar — TAVFIQNASHR",
        "listing_meta_desc": "TAVFIQNASHR nashriyoti maqolalari: tasavvuf, aqida va mumtoz "
                             "turkiy meros mavzusidagi yozmalar hamda kitoblardan parchalar.",
        "read": "daqiqalik o‘qish",
        "back": "← Barcha maqolalar",
        "source_label": "Manba",
        "teaser_kicker": "Bloglar",
        "teaser_title": "So‘nggi maqolalar",
        "teaser_lead": "Kitoblarimizdan parchalar va tasavvuf istilohlari haqida yozmalar.",
        "teaser_all": "Barcha maqolalar",
        "more": "Batafsil",
        "footer_tag": "o‘qiladigan kitoblar bulog‘i",
        "footer_nav_label": "Sahifa bo‘limlari",
        "footer_lang": "Русская версия сайта →",
        "copyright": "TAVFIQNASHR nashriyoti. Barcha huquqlar himoyalangan.",
        "totop": "Yuqoriga",
        "og_image": f"{SITE}/assets/og-image.png",
        "locale": "uz_UZ", "alt_locale": "ru_RU",
        "cta_title": "Yangi maqolalardan xabardor bo‘ling",
        "cta_text": "Yangi nashrlar va kitoblardan parchalar Telegram kanalimizda e’lon qilinadi.",
        "cta_btn": "Telegram kanalga obuna bo‘lish",
    },
    "ru": {
        "htmllang": "ru",
        "dir": "blog/ru",
        "depth": 2,
        "home": "ru.html",
        "other_home": "index.html",
        "blog_url": f"{SITE}/blog/ru/",
        "rel_from_home": "blog/ru/",
        "rel_other_index": "../",
        "skip": "Перейти к основному содержанию",
        "brand_sub": "издательство",
        "lang_label": "Язык сайта",
        "menu_label": "Основное меню",
        "nav_toggle": "Открыть меню",
        "nav": [("#o-nas", "О нас"), ("#knigi", "Книги"), ("#sittai", "Ситтаи турки"),
                ("#mudrosti", "Изречения"), ("#kontakty", "Контакты")],
        "blog_nav": "Статьи",
        "tg": "Telegram-канал",
        "listing_title": "Статьи",
        "listing_kicker": "Блог",
        "listing_lead": "Отрывки из книг издательства, термины тасаввуфа и материалы "
                        "о наследии предков.",
        "listing_meta_title": "Статьи — TAVFIQNASHR",
        "listing_meta_desc": "Статьи издательства TAVFIQNASHR: тасаввуф, вероучение и "
                             "классическое тюркское наследие, отрывки из книг.",
        "read": "мин. чтения",
        "back": "← Все статьи",
        "source_label": "Источник",
        "teaser_kicker": "Блог",
        "teaser_title": "Последние статьи",
        "teaser_lead": "Отрывки из наших книг и материалы о терминах тасаввуфа.",
        "teaser_all": "Все статьи",
        "more": "Читать",
        "footer_tag": "родник книг, достойных прочтения",
        "footer_nav_label": "Разделы страницы",
        "footer_lang": "Saytning o‘zbekcha versiyasi →",
        "copyright": "Издательство TAVFIQNASHR. Все права защищены.",
        "totop": "Наверх",
        "og_image": f"{SITE}/assets/og-image-ru.png",
        "locale": "ru_RU", "alt_locale": "uz_UZ",
        "cta_title": "Следите за новыми статьями",
        "cta_text": "Новинки и отрывки из книг публикуются в нашем Telegram-канале.",
        "cta_btn": "Подписаться на Telegram-канал",
    },
}

E = html.escape


# ---------------------------------------------------------------- markdown ---
def inline(s: str) -> str:
    s = E(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def md_to_html(text: str) -> str:
    """Supports: ##/### headings, paragraphs, > quotes (with an em-dash
    attribution line), - and 1. lists, --- rules, **bold**, *italic*, links."""
    out, buf, mode = [], [], None

    def flush():
        nonlocal buf, mode
        if not buf:
            mode = None
            return
        if mode == "p":
            out.append("<p>" + inline(" ".join(buf)) + "</p>")
        elif mode == "quote":
            body, attrib = [], None
            for ln in buf:
                if ln.startswith("—"):
                    attrib = ln.lstrip("—").strip()
                else:
                    body.append(ln)
            q = "<blockquote><p>" + inline(" ".join(body)) + "</p>"
            if attrib:
                q += "<footer>" + inline(attrib) + "</footer>"
            out.append(q + "</blockquote>")
        elif mode in ("ul", "ol"):
            items = "".join(f"<li>{inline(i)}</li>" for i in buf)
            out.append(f"<{mode}>{items}</{mode}>")
        buf, mode = [], None

    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("### "):
            flush(); out.append("<h3>" + inline(stripped[4:]) + "</h3>"); continue
        if stripped.startswith("## "):
            flush(); out.append("<h2>" + inline(stripped[3:]) + "</h2>"); continue
        if re.fullmatch(r"-{3,}", stripped):
            flush(); out.append("<hr>"); continue
        if stripped.startswith(">"):
            if mode != "quote":
                flush(); mode = "quote"
            buf.append(stripped.lstrip(">").strip()); continue
        if stripped.startswith("- "):
            if mode != "ul":
                flush(); mode = "ul"
            buf.append(stripped[2:]); continue
        if re.match(r"\d+\.\s", stripped):
            if mode != "ol":
                flush(); mode = "ol"
            buf.append(re.sub(r"^\d+\.\s+", "", stripped)); continue
        if mode != "p":
            flush(); mode = "p"
        buf.append(stripped)
    flush()
    return "\n".join(out)


# ------------------------------------------------------------------ parsing --
def load_posts(lang: str) -> list[dict]:
    d = os.path.join(ROOT, "content", "blog", lang)
    if not os.path.isdir(d):
        return []
    posts = []
    for name in sorted(os.listdir(d)):
        if not name.endswith(".md"):
            continue
        raw = open(os.path.join(d, name), encoding="utf-8").read()
        head, _, body = raw.partition("\n\n")
        meta = {}
        for line in head.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        for req in ("title", "date", "description"):
            if req not in meta:
                sys.exit(f"error: {lang}/{name} is missing '{req}' in its front matter")
        try:
            y, m, dd = (int(x) for x in meta["date"].split("-"))
            meta["_date"] = date(y, m, dd)
        except ValueError:
            sys.exit(f"error: {lang}/{name} has a bad date '{meta['date']}' (want YYYY-MM-DD)")
        meta["slug"] = name[:-3]
        meta["body_html"] = md_to_html(body)
        words = len(re.findall(r"\w+", body))
        meta["minutes"] = max(1, round(words / 160))
        posts.append(meta)
    posts.sort(key=lambda p: p["_date"], reverse=True)
    return posts


def fmt_date(d: date, lang: str) -> str:
    mon = MONTHS[lang][d.month - 1]
    return f"{d.day}-{mon}, {d.year}" if lang == "uz" else f"{d.day} {mon} {d.year} г."


# ------------------------------------------------------------------ shells ---
def shell(lang, *, title, desc, canonical, og_url, og_image, body,
          alt_url, alt_href, self_href, og_type="website", extra_head=""):
    c = L[lang]
    up = "../" * c["depth"]
    other = "ru" if lang == "uz" else "uz"
    oc = L[other]
    nav = "\n".join(
        f'      <a href="{up}{c["home"]}{href}">{E(label)}</a>'
        for href, label in c["nav"])
    fnav = "\n".join(
        f'      <a href="{up}{c["home"]}{href}">{E(label)}</a>'
        for href, label in c["nav"])
    uz_url, ru_url = (canonical, alt_url) if lang == "uz" else (alt_url, canonical)
    # hreflang/canonical stay absolute; the visible switcher stays relative so the
    # blog also works from the github.io fallback and from a local server.
    uz_href, ru_href = (self_href, alt_href) if lang == "uz" else (alt_href, self_href)
    return f"""<!DOCTYPE html>
<html lang="{c['htmllang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title>
<meta name="description" content="{E(desc, quote=True)}">
<meta name="theme-color" content="#0f3d33">
<link rel="icon" href="{up}assets/img/logo.jpg">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="uz" href="{uz_url}">
<link rel="alternate" hreflang="ru" href="{ru_url}">
<link rel="alternate" hreflang="x-default" href="{uz_url}">
<meta property="og:title" content="{E(title, quote=True)}">
<meta property="og:description" content="{E(desc, quote=True)}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:type" content="image/png">
<meta property="og:url" content="{og_url}">
<meta property="og:site_name" content="TAVFIQNASHR">
<meta property="og:locale" content="{c['locale']}">
<meta property="og:locale:alternate" content="{c['alt_locale']}">
<meta property="og:type" content="{og_type}">
<meta name="twitter:card" content="summary_large_image">{extra_head}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}assets/css/styles.css">
</head>
<body>

<a class="skip" href="#main">{E(c['skip'])}</a>

<header class="site-header" id="top">
  <div class="wrap header-inner">
    <a class="brand" href="{up}{c['home']}">
      <img src="{up}assets/img/logo.jpg" alt="TAVFIQNASHR" width="48" height="48">
      <span class="brand-text">
        <strong>TAVFIQNASHR</strong>
        <em>{E(c['brand_sub'])}</em>
      </span>
    </a>

    <div class="header-tools">
      <div class="lang" role="group" aria-label="{E(c['lang_label'], quote=True)}">
        <a {'class="is-active" ' if lang == 'uz' else ''}href="{uz_href}" lang="uz"{' aria-current="page"' if lang == 'uz' else ' hreflang="uz"'}>UZ</a>
        <a {'class="is-active" ' if lang == 'ru' else ''}href="{ru_href}" lang="ru"{' aria-current="page"' if lang == 'ru' else ' hreflang="ru"'}>RU</a>
      </div>

      <button class="nav-toggle" aria-expanded="false" aria-controls="nav" aria-label="{E(c['nav_toggle'], quote=True)}">
        <span></span><span></span><span></span>
      </button>
    </div>

    <nav id="nav" class="nav" aria-label="{E(c['menu_label'], quote=True)}">
{nav}
      <a href="index.html" aria-current="page">{E(c['blog_nav'])}</a>
      <a class="btn btn-sm" href="https://t.me/tavfiqnashr" target="_blank" rel="noopener">{E(c['tg'])}</a>
    </nav>
  </div>
</header>

<div class="nav-backdrop" hidden></div>

<main id="main">
{body}
</main>

<footer class="site-footer">
  <div class="wrap footer-inner">
    <div class="footer-brand">
      <img src="{up}assets/img/logo.jpg" alt="" width="40" height="40" aria-hidden="true">
      <div>
        <strong>TAVFIQNASHR</strong>
        <p>{E(c['footer_tag'])}</p>
      </div>
    </div>

    <nav class="footer-nav" aria-label="{E(c['footer_nav_label'], quote=True)}">
{fnav}
      <a href="index.html">{E(c['blog_nav'])}</a>
    </nav>

    <p class="footer-lang"><a href="{c['rel_other_index']}" hreflang="{other}" lang="{other}">{E(c['footer_lang'])}</a></p>

    <p class="copyright">© <span id="year">{date.today().year}</span> {E(c['copyright'])}</p>
  </div>
</footer>

<a class="to-top" href="#top" aria-label="{E(c['totop'], quote=True)}">↑</a>

<script src="{up}assets/js/main.js"></script>
</body>
</html>
"""


def post_card(p, lang, href):
    c = L[lang]
    tag = f'<span class="post-tag">{E(p["tags"])}</span>' if p.get("tags") else ""
    return f"""        <article class="post-item">
          <div class="post-meta">
            <time datetime="{p['_date'].isoformat()}">{E(fmt_date(p['_date'], lang))}</time>
            <span class="dot">·</span>
            <span>{p['minutes']} {E(c['read'])}</span>
            {tag}
          </div>
          <h3><a href="{href}">{E(p['title'])}</a></h3>
          <p>{E(p['description'])}</p>
          <a class="link-arrow" href="{href}" aria-label="{E(p['title'], quote=True)}">{E(c['more'])}</a>
        </article>"""


# ------------------------------------------------------------------- build ---
def build_listing(lang, posts):
    c = L[lang]
    items = "\n".join(post_card(p, lang, f"{p['slug']}.html") for p in posts) \
        or '        <p class="section-sub">—</p>'
    body = f"""
  <section class="section page-head">
    <div class="wrap">
      <p class="kicker">{E(c['listing_kicker'])}</p>
      <h1>{E(c['listing_title'])}</h1>
      <p class="section-sub">{E(c['listing_lead'])}</p>
    </div>
  </section>

  <section class="section section-tint">
    <div class="wrap">
      <div class="post-list">
{items}
      </div>
    </div>
  </section>
"""
    return shell(lang, title=c["listing_meta_title"], desc=c["listing_meta_desc"],
                 canonical=c["blog_url"], og_url=c["blog_url"], og_image=c["og_image"],
                 body=body, alt_url=L["ru" if lang == "uz" else "uz"]["blog_url"],
                 alt_href=c["rel_other_index"], self_href="index.html")


def build_post(lang, p, has_counterpart):
    c = L[lang]
    other = "ru" if lang == "uz" else "uz"
    url = f"{c['blog_url']}{p['slug']}.html"
    alt = f"{L[other]['blog_url']}{p['slug']}.html" if has_counterpart else L[other]["blog_url"]
    alt_href = (c["rel_other_index"] + p["slug"] + ".html") if has_counterpart else c["rel_other_index"]
    src = (f'\n        <p class="post-source">{E(c["source_label"])}: '
           f'<cite>{E(p["source"])}</cite></p>') if p.get("source") else ""
    extra = (f'\n<meta property="article:published_time" content="{p["_date"].isoformat()}">')
    body = f"""
  <article class="section post">
    <div class="wrap post-wrap">
      <a class="post-back" href="index.html">{E(c['back'])}</a>
      <div class="post-meta">
        <time datetime="{p['_date'].isoformat()}">{E(fmt_date(p['_date'], lang))}</time>
        <span class="dot">·</span>
        <span>{p['minutes']} {E(c['read'])}</span>
        {f'<span class="post-tag">{E(p["tags"])}</span>' if p.get('tags') else ''}
      </div>
      <h1>{E(p['title'])}</h1>
      <p class="post-lead">{E(p['description'])}</p>{src}

      <div class="prose">
{p['body_html']}
      </div>
    </div>
  </article>

  <section class="section section-dark">
    <div class="wrap post-cta">
      <h2>{E(c['cta_title'])}</h2>
      <p>{E(c['cta_text'])}</p>
      <a class="btn btn-gold" href="https://t.me/tavfiqnashr" target="_blank" rel="noopener">{E(c['cta_btn'])}</a>
    </div>
  </section>
"""
    return shell(lang, title=f"{p['title']} — TAVFIQNASHR", desc=p["description"],
                 canonical=url, og_url=url, og_image=c["og_image"], body=body,
                 alt_url=alt, alt_href=alt_href, self_href=p["slug"] + ".html",
                 og_type="article", extra_head=extra)


def build_teaser(lang, posts):
    c = L[lang]
    anchor = "maqolalar" if lang == "uz" else "stati"
    cards = "\n".join(
        post_card(p, lang, f"{c['rel_from_home']}{p['slug']}.html") for p in posts[:3])
    return f"""  <!-- BLOG:START (generated by tools/build-blog.py — do not edit by hand) -->
  <section id="{anchor}" class="section section-tint">
    <div class="wrap">
      <header class="section-head">
        <p class="kicker">{E(c['teaser_kicker'])}</p>
        <h2>{E(c['teaser_title'])}</h2>
        <p class="section-sub">{E(c['teaser_lead'])}</p>
      </header>

      <div class="post-list">
{cards}
      </div>

      <div class="series-cta">
        <a class="btn" href="{c['rel_from_home']}">{E(c['teaser_all'])}</a>
      </div>
    </div>
  </section>
  <!-- BLOG:END -->"""


def inject(path, block, before_marker):
    src = open(path, encoding="utf-8").read()
    pat = re.compile(r"[ \t]*<!-- BLOG:START.*?<!-- BLOG:END -->", re.S)
    if pat.search(src):
        new = pat.sub(lambda _: block, src, count=1)
    else:
        if before_marker not in src:
            sys.exit(f"error: cannot find '{before_marker}' in {path} to place the blog section")
        new = src.replace(before_marker, block + "\n\n" + before_marker, 1)
    if new != src:
        open(path, "w", encoding="utf-8").write(new)
        return True
    return False


def main():
    uz, ru = load_posts("uz"), load_posts("ru")
    have = {"uz": {p["slug"] for p in uz}, "ru": {p["slug"] for p in ru}}
    written = []

    for lang, posts in (("uz", uz), ("ru", ru)):
        d = os.path.join(ROOT, L[lang]["dir"])
        os.makedirs(d, exist_ok=True)
        other = "ru" if lang == "uz" else "uz"
        idx = os.path.join(d, "index.html")
        open(idx, "w", encoding="utf-8").write(build_listing(lang, posts))
        written.append(os.path.relpath(idx, ROOT))
        for p in posts:
            f = os.path.join(d, p["slug"] + ".html")
            open(f, "w", encoding="utf-8").write(
                build_post(lang, p, p["slug"] in have[other]))
            written.append(os.path.relpath(f, ROOT))

    for lang, posts, page, marker in (
            ("uz", uz, "index.html", "  <!-- CONTACT -->"),
            ("ru", ru, "ru.html", "  <!-- CONTACT -->")):
        if inject(os.path.join(ROOT, page), build_teaser(lang, posts), marker):
            written.append(page)

    for slug in sorted(have["uz"] ^ have["ru"]):
        side = "uz" if slug in have["uz"] else "ru"
        print(f"  note: '{slug}' exists only in {side}; "
              f"its language switcher points at the other blog index")

    print(f"built {len(uz)} uz + {len(ru)} ru posts")
    for w in written:
        print("  ", w)


if __name__ == "__main__":
    main()
