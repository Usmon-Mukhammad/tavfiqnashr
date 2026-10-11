#!/usr/bin/env python3
"""Generate the books catalogue from Markdown. Standard library only.

    python3 tools/build-books.py

Reads   content/books/<lang>/<slug>.md
Writes  kitoblar/index.html        uz catalogue    /kitoblar/
        kitoblar/<slug>.html       uz book page
        kitoblar/ru/index.html     ru catalogue    /kitoblar/ru/
        kitoblar/ru/<slug>.html    ru book page
        index.html, ru.html        the Kitoblar cards and the featured release,
                                   between BOOKS:START/END and FEATURED:START/END

Front matter is `key: value` lines ended by a blank line; the rest is the long
description in Markdown. Required: title, author, date (YYYY-MM-DD),
description, image. Optional: price, pages, cover, language, tag, quote,
featured.

Newest first by date. The featured release is the newest book marked
`featured: yes`, else simply the newest. Pages are rewritten whole on every
run, so the command is idempotent.
"""
from __future__ import annotations

import html
import os
import re
import struct
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://tavfiqnashr.uz"
IMG_DIR = os.path.join("assets", "img", "books")

MONTHS = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
}

L = {
    "uz": {
        "htmllang": "uz", "dir": "kitoblar", "depth": 1,
        "home": "index.html", "rel_from_home": "kitoblar/", "rel_other_index": "ru/",
        "url": f"{SITE}/kitoblar/",
        "skip": "Asosiy qismga o‘tish", "brand_sub": "nashriyoti",
        "lang_label": "Sayt tili", "menu_label": "Asosiy menyu",
        "nav_toggle": "Menyuni ochish",
        "nav": [("#biz-haqimizda", "Biz haqimizda"), ("#kitoblar", "Kitoblar"),
                ("#sittayi", "Sittayi turkiy"), ("#hikmatlar", "Hikmatlar"),
                ("#aloqa", "Aloqa")],
        "tg": "Telegram kanal",
        "cat_title": "Barcha kitoblar", "cat_kicker": "Nashrlarimiz",
        "cat_lead": "Tasavvuf, aqida va mumtoz turkiy meros yo‘lidagi nashrlarimiz.",
        "cat_meta_title": "Kitoblar — TAVFIQNASHR",
        "cat_meta_desc": "TAVFIQNASHR nashriyoti kitoblari: tasavvuf, aqida va mumtoz "
                         "turkiy meros. Asl manbaga tayangan nashrlar.",
        "home_kicker": "Nashrlarimiz", "home_title": "Kitoblar",
        "home_lead": "Tasavvuf, aqida va ma’rifat yo‘lidagi asarlar — asl manbaga tayangan nashrlar.",
        "all": "Barcha kitoblar", "more": "Batafsil", "back": "← Barcha kitoblar",
        "new": "Yangilik", "order": "Buyurtma berish",
        "order_note": "Kitobni sotib olish uchun Telegram orqali murojaat qiling.",
        "price": "Narxi", "pages": "Sahifalar", "cover": "Muqova",
        "language_l": "Matn", "author_l": "Muallif",
        "empty": "Hozircha kitob qo‘shilmagan.",
        "footer_tag": "o‘qiladigan kitoblar bulog‘i",
        "footer_nav_label": "Sahifa bo‘limlari",
        "footer_lang": "Русская версия сайта →",
        "copyright": "TAVFIQNASHR nashriyoti. Barcha huquqlar himoyalangan.",
        "totop": "Yuqoriga", "og_image": f"{SITE}/assets/og-image.png",
        "locale": "uz_UZ", "alt_locale": "ru_RU",
    },
    "ru": {
        "htmllang": "ru", "dir": "kitoblar/ru", "depth": 2,
        "home": "ru.html", "rel_from_home": "kitoblar/ru/", "rel_other_index": "../",
        "url": f"{SITE}/kitoblar/ru/",
        "skip": "Перейти к основному содержанию", "brand_sub": "издательство",
        "lang_label": "Язык сайта", "menu_label": "Основное меню",
        "nav_toggle": "Открыть меню",
        "nav": [("#o-nas", "О нас"), ("#knigi", "Книги"), ("#sittai", "Ситтаи турки"),
                ("#mudrosti", "Изречения"), ("#kontakty", "Контакты")],
        "tg": "Telegram-канал",
        "cat_title": "Все книги", "cat_kicker": "Наши издания",
        "cat_lead": "Наши издания по тасаввуфу, вероучению и классическому тюркскому наследию.",
        "cat_meta_title": "Книги — TAVFIQNASHR",
        "cat_meta_desc": "Книги издательства TAVFIQNASHR: тасаввуф, вероучение и "
                         "классическое тюркское наследие. Издания, опирающиеся на первоисточник.",
        "home_kicker": "Наши издания", "home_title": "Книги",
        "home_lead": "Труды на пути тасаввуфа, вероучения и ма‘рифата — издания, опирающиеся на первоисточник.",
        "all": "Все книги", "more": "Подробнее", "back": "← Все книги",
        "new": "Новинка", "order": "Оформить заказ",
        "order_note": "Для приобретения книги свяжитесь с нами через Telegram.",
        "price": "Цена", "pages": "Страниц", "cover": "Переплёт",
        "language_l": "Текст", "author_l": "Автор",
        "empty": "Книги пока не добавлены.",
        "footer_tag": "родник книг, достойных прочтения",
        "footer_nav_label": "Разделы страницы",
        "footer_lang": "Saytning o‘zbekcha versiyasi →",
        "copyright": "Издательство TAVFIQNASHR. Все права защищены.",
        "totop": "Наверх", "og_image": f"{SITE}/assets/og-image-ru.png",
        "locale": "ru_RU", "alt_locale": "uz_UZ",
    },
}

E = html.escape


# ------------------------------------------------------------------ images --
def image_size(path: str):
    """Width/height of a PNG or JPEG, so pages can reserve space and avoid
    layout shift. Returns (None, None) when the format is not recognised."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(26)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", head[16:24])
                return int(w), int(h)
            if head[:2] == b"\xff\xd8":
                fh.seek(2)
                while True:
                    b = fh.read(1)
                    while b and b != b"\xff":
                        b = fh.read(1)
                    marker = fh.read(1)
                    while marker == b"\xff":
                        marker = fh.read(1)
                    if not marker:
                        return None, None
                    if marker[0] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                                     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        fh.read(3)
                        h, w = struct.unpack(">HH", fh.read(4))
                        return int(w), int(h)
                    size = struct.unpack(">H", fh.read(2))[0]
                    fh.seek(size - 2, 1)
    except (OSError, struct.error):
        pass
    return None, None


# ---------------------------------------------------------------- markdown --
def inline(s: str) -> str:
    s = E(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def md_to_html(text: str) -> str:
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
            out.append(f"<{mode}>" + "".join(f"<li>{inline(i)}</li>" for i in buf) + f"</{mode}>")
        buf, mode = [], None

    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            flush(); continue
        if line.startswith("### "):
            flush(); out.append("<h3>" + inline(line[4:]) + "</h3>"); continue
        if line.startswith("## "):
            flush(); out.append("<h2>" + inline(line[3:]) + "</h2>"); continue
        if re.fullmatch(r"-{3,}", line):
            flush(); out.append("<hr>"); continue
        if line.startswith(">"):
            if mode != "quote":
                flush(); mode = "quote"
            buf.append(line.lstrip(">").strip()); continue
        if line.startswith("- "):
            if mode != "ul":
                flush(); mode = "ul"
            buf.append(line[2:]); continue
        if re.match(r"\d+\.\s", line):
            if mode != "ol":
                flush(); mode = "ol"
            buf.append(re.sub(r"^\d+\.\s+", "", line)); continue
        if mode != "p":
            flush(); mode = "p"
        buf.append(line)
    flush()
    return "\n".join(out)


# ------------------------------------------------------------------ loading --
def load_books(lang: str) -> list[dict]:
    d = os.path.join(ROOT, "content", "books", lang)
    if not os.path.isdir(d):
        return []
    books = []
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
        for req in ("title", "author", "date", "description", "image"):
            if not meta.get(req):
                sys.exit(f"error: {lang}/{name} is missing '{req}' in its front matter")
        try:
            y, m, dd = (int(x) for x in meta["date"].split("-"))
            meta["_date"] = date(y, m, dd)
        except ValueError:
            sys.exit(f"error: {lang}/{name} has a bad date '{meta['date']}' (want YYYY-MM-DD)")
        img = os.path.join(ROOT, IMG_DIR, meta["image"])
        if not os.path.exists(img):
            sys.exit(f"error: {lang}/{name} references a missing cover: {IMG_DIR}/{meta['image']}")
        meta["_w"], meta["_h"] = image_size(img)
        meta["slug"] = name[:-3]
        meta["body_html"] = md_to_html(body)
        meta["_featured"] = meta.get("featured", "").lower() in ("yes", "true", "1")
        books.append(meta)
    books.sort(key=lambda b: b["_date"], reverse=True)
    return books


def fmt_date(d: date, lang: str) -> str:
    mon = MONTHS[lang][d.month - 1]
    return f"{d.day}-{mon}, {d.year}" if lang == "uz" else f"{d.day} {mon} {d.year}"


# -------------------------------------------------------------------- shell --
def shell(lang, *, title, desc, canonical, og_image, body, alt_url, alt_href,
          self_href, og_type="website", extra_head=""):
    c = L[lang]
    up = "../" * c["depth"]
    other = "ru" if lang == "uz" else "uz"
    uz_url, ru_url = (canonical, alt_url) if lang == "uz" else (alt_url, canonical)
    uz_href, ru_href = (self_href, alt_href) if lang == "uz" else (alt_href, self_href)

    # Links stay relative so the site also works from the github.io fallback and
    # a local server; only canonical / hreflang / og URLs are absolute.
    def nav_html():
        items = [(f'{up}{c["home"]}{href}', E(label)) for href, label in c["nav"]]
        return "\n".join(f'      <a href="{h}">{t}</a>' for h, t in items)

    nav = nav_html()
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
<meta property="og:url" content="{canonical}">
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
{nav}
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


# --------------------------------------------------------------- components --
def card(b, lang, href, img_prefix):
    c = L[lang]
    dims = f' width="{b["_w"]}" height="{b["_h"]}"' if b.get("_w") else ""
    tag = f'            <span class="tag">{E(b["tag"])}</span>\n' if b.get("tag") else ""
    price = f'            <p class="price">{E(b["price"])}</p>\n' if b.get("price") else ""
    quote = (f'            <p class="quote-mini">{E(b["quote"])}</p>\n'
             if b.get("quote") else "")
    return f"""        <article class="card">
          <div class="card-media"><img src="{img_prefix}{E(b['image'])}" alt="{E(b['title'], quote=True)}"{dims} loading="lazy"></div>
          <div class="card-body">
{tag}            <h3><a href="{href}">{E(b['title'])}</a></h3>
            <p class="byline">{E(b['author'])}</p>
            <p>{E(b['description'])}</p>
{price}{quote}            <a class="link-arrow" href="{href}">{E(c['more'])}</a>
          </div>
        </article>"""


def specs(b, lang):
    c = L[lang]
    rows = [(c["pages"], b.get("pages")), (c["cover"], b.get("cover")),
            (c["language_l"], b.get("language")), (c["price"], b.get("price"))]
    items = "".join(f"<li><span>{E(k)}</span><strong>{E(v)}</strong></li>"
                    for k, v in rows if v)
    return f'<ul class="specs">{items}</ul>' if items else ""


# ------------------------------------------------------------------- builds --
def build_catalogue(lang, books):
    c = L[lang]
    cards = "\n".join(card(b, lang, f"{b['slug']}.html", "../" * c["depth"] + "assets/img/books/")
                      for b in books) or f'        <p class="section-sub">{E(c["empty"])}</p>'
    body = f"""
  <section class="section page-head">
    <div class="wrap">
      <p class="kicker">{E(c['cat_kicker'])}</p>
      <h1>{E(c['cat_title'])}</h1>
      <p class="section-sub">{E(c['cat_lead'])}</p>
    </div>
  </section>

  <section class="section section-tint">
    <div class="wrap">
      <div class="cards">
{cards}
      </div>
    </div>
  </section>
"""
    return shell(lang, title=c["cat_meta_title"], desc=c["cat_meta_desc"],
                 canonical=c["url"], og_image=c["og_image"], body=body,
                 alt_url=L["ru" if lang == "uz" else "uz"]["url"],
                 alt_href=c["rel_other_index"], self_href="index.html")


def build_book(lang, b, has_counterpart):
    c = L[lang]
    other = "ru" if lang == "uz" else "uz"
    url = f"{c['url']}{b['slug']}.html"
    alt = f"{L[other]['url']}{b['slug']}.html" if has_counterpart else L[other]["url"]
    alt_href = (c["rel_other_index"] + b["slug"] + ".html") if has_counterpart else c["rel_other_index"]
    up = "../" * c["depth"]
    dims = f' width="{b["_w"]}" height="{b["_h"]}"' if b.get("_w") else ""
    body = f"""
  <article class="section book">
    <div class="wrap book-grid">
      <div class="book-cover">
        <img src="{up}assets/img/books/{E(b['image'])}" alt="{E(b['title'], quote=True)}"{dims}>
      </div>

      <div class="book-info">
        <a class="post-back" href="index.html">{E(c['back'])}</a>
        {f'<span class="tag">{E(b["tag"])}</span>' if b.get('tag') else ''}
        <h1>{E(b['title'])}</h1>
        <p class="byline">{E(b['author'])}</p>
        <p class="post-lead">{E(b['description'])}</p>
        {specs(b, lang)}
        <a class="btn btn-lg" href="https://t.me/tavfiqnashr" target="_blank" rel="noopener">{E(c['order'])}</a>
        <p class="order-note">{E(c['order_note'])}</p>
      </div>
    </div>

    <div class="wrap book-body">
      <div class="prose">
{b['body_html']}
      </div>
    </div>
  </article>
"""
    return shell(lang, title=f"{b['title']} — TAVFIQNASHR", desc=b["description"],
                 canonical=url, og_image=c["og_image"], body=body, alt_url=alt,
                 alt_href=alt_href, self_href=b["slug"] + ".html", og_type="book")


def build_home_books(lang, books):
    c = L[lang]
    anchor = "kitoblar" if lang == "uz" else "knigi"
    shown = books[:3]
    cards = "\n".join(card(b, lang, f"{c['rel_from_home']}{b['slug']}.html",
                           "assets/img/books/") for b in shown) \
        or f'        <p class="section-sub">{E(c["empty"])}</p>'
    more = (f"""
      <div class="series-cta">
        <a class="btn" href="{c['rel_from_home']}">{E(c['all'])}</a>
      </div>""" if len(books) > 3 else "")
    return f"""  <!-- BOOKS:START (generated by tools/build-books.py — do not edit by hand) -->
  <section id="{anchor}" class="section">
    <div class="wrap">
      <header class="section-head">
        <p class="kicker">{E(c['home_kicker'])}</p>
        <h2>{E(c['home_title'])}</h2>
        <p class="section-sub">{E(c['home_lead'])}</p>
      </header>

      <div class="cards">
{cards}
      </div>{more}
    </div>
  </section>
  <!-- BOOKS:END -->"""


def build_featured(lang, books):
    c = L[lang]
    picks = [b for b in books if b["_featured"]] or books
    if not picks:
        return ("  <!-- FEATURED:START (generated by tools/build-books.py — do not edit by hand) -->\n"
                "  <!-- FEATURED:END -->")
    b = picks[0]
    dims = f' width="{b["_w"]}" height="{b["_h"]}"' if b.get("_w") else ""
    href = f"{c['rel_from_home']}{b['slug']}.html"
    return f"""  <!-- FEATURED:START (generated by tools/build-books.py — do not edit by hand) -->
  <section class="section section-dark">
    <div class="wrap release">
      <div class="release-media">
        <img src="assets/img/books/{E(b['image'])}" alt="{E(b['title'], quote=True)}"{dims} loading="lazy">
      </div>
      <div class="release-body">
        <p class="kicker gold">{E(c['new'])}</p>
        <h2>{E(b['title'])}</h2>
        <p class="byline">{E(b['author'])}</p>
        <p>{E(b['description'])}</p>
        {specs(b, lang)}
        <a class="btn btn-gold" href="{href}">{E(c['more'])}</a>
      </div>
    </div>
  </section>
  <!-- FEATURED:END -->"""


def inject(path, name, block, fallback_marker):
    src = open(path, encoding="utf-8").read()
    pat = re.compile(rf"[ \t]*<!-- {name}:START.*?<!-- {name}:END -->", re.S)
    if pat.search(src):
        new = pat.sub(lambda _: block, src, count=1)
    else:
        if fallback_marker not in src:
            sys.exit(f"error: cannot find '{fallback_marker}' in {path} to place the {name} block")
        new = src.replace(fallback_marker, block + "\n\n" + fallback_marker, 1)
    if new != src:
        open(path, "w", encoding="utf-8").write(new)
        return True
    return False


def main():
    uz, ru = load_books("uz"), load_books("ru")
    have = {"uz": {b["slug"] for b in uz}, "ru": {b["slug"] for b in ru}}
    written, removed = [], []

    for lang, books in (("uz", uz), ("ru", ru)):
        d = os.path.join(ROOT, L[lang]["dir"])
        os.makedirs(d, exist_ok=True)
        other = "ru" if lang == "uz" else "uz"
        idx = os.path.join(d, "index.html")
        open(idx, "w", encoding="utf-8").write(build_catalogue(lang, books))
        written.append(os.path.relpath(idx, ROOT))
        for b in books:
            f = os.path.join(d, b["slug"] + ".html")
            open(f, "w", encoding="utf-8").write(build_book(lang, b, b["slug"] in have[other]))
            written.append(os.path.relpath(f, ROOT))

        keep = {b["slug"] + ".html" for b in books} | {"index.html"}
        for name in sorted(os.listdir(d)):
            if name.endswith(".html") and name not in keep:
                os.remove(os.path.join(d, name))
                removed.append(os.path.relpath(os.path.join(d, name), ROOT))

    for lang, books, page in (("uz", uz, "index.html"), ("ru", ru, "ru.html")):
        p = os.path.join(ROOT, page)
        if inject(p, "BOOKS", build_home_books(lang, books), "  <!-- SITTAYI"):
            written.append(page)
        if inject(p, "FEATURED", build_featured(lang, books), "  <!-- BOOKS:START"):
            written.append(page)

    # Covers are deliberately NOT auto-deleted: the same file is normally shared
    # by the uz and ru entries, and a cover is uploaded before its book is
    # saved — a build triggered by that upload would delete it mid-flow. Report
    # them instead so they can be cleaned up by hand.
    used = {b["image"] for b in uz} | {b["image"] for b in ru}
    img_dir = os.path.join(ROOT, IMG_DIR)
    if os.path.isdir(img_dir):
        for name in sorted(os.listdir(img_dir)):
            if name.lower().endswith((".jpg", ".png", ".webp")) and name not in used:
                print(f"  note: {IMG_DIR}/{name} is not used by any book")

    for slug in sorted(have["uz"] ^ have["ru"]):
        side = "uz" if slug in have["uz"] else "ru"
        print(f"  note: '{slug}' exists only in {side}; its language switcher "
              f"points at the other catalogue")

    print(f"built {len(uz)} uz + {len(ru)} ru books")
    for w in dict.fromkeys(written):
        print("  ", w)
    for r in removed:
        print("   removed", r)


if __name__ == "__main__":
    main()
