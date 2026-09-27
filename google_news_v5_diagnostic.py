# google_news_v5_diagnostic.py
#
# DIAGNOSTIC UNIQUEMENT
# - Aucun pandas
# - Aucun SQLite
# - Aucun sentiment
# - Teste seulement 5 articles pertinents

from pathlib import Path
from urllib.parse import urlparse
import base64
import csv
import html
import json
import re
import time

import requests
from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "google_news_v2_results.csv"

TEST_COUNT = 5
REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}


# ============================================================
# OUTILS
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def word_count(text):
    if not text:
        return 0

    return len(
        re.findall(
            r"\b\w+\b",
            text,
            flags=re.UNICODE
        )
    )


def is_google_news_url(url):

    if not url:
        return False

    url = url.lower()

    return (
        "news.google.com" in url
        or "google.com/rss/articles" in url
    )


# ============================================================
# LECTURE CSV SANS PANDAS
# ============================================================

def load_csv():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Fichier introuvable : {INPUT_FILE}"
        )

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        rows = list(reader)

    return rows


def is_relevant(row):

    value = str(
        row.get("relevant", "")
    ).strip().lower()

    return value in {
        "true",
        "1",
        "yes",
        "oui",
    }


# ============================================================
# GOOGLE NEWS — TOKEN DIRECT
# ============================================================

def decode_token_directly(url):

    if not url:
        return None

    patterns = [
        r"/rss/articles/([^?]+)",
        r"/articles/([^?]+)",
    ]

    token = None

    for pattern in patterns:

        match = re.search(
            pattern,
            url
        )

        if match:

            token = match.group(1)
            break

    if not token:
        return None

    candidates = [
        token,
        token.replace("-", "+").replace("_", "/"),
    ]

    for candidate in candidates:

        try:

            padding = "=" * (
                -len(candidate) % 4
            )

            decoded = base64.urlsafe_b64decode(
                candidate + padding
            )

            text = decoded.decode(
                "utf-8",
                errors="ignore"
            )

            urls = re.findall(
                r"https?://[^\s\"'<>]+",
                text
            )

            for found_url in urls:

                found_url = found_url.rstrip(
                    ".,);]"
                )

                hostname = urlparse(
                    found_url
                ).netloc.lower()

                if (
                    found_url.startswith("http")
                    and "google." not in hostname
                ):

                    return found_url

        except Exception:
            pass

    return None


# ============================================================
# GOOGLE NEWS — PAGE
# ============================================================

def extract_google_page_links(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        print(
            f"      Google HTTP       : "
            f"{response.status_code}"
        )

        print(
            f"      Google final URL  : "
            f"{response.url}"
        )

        print(
            f"      Google HTML       : "
            f"{len(response.text):,} caractères"
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        links = []

        for a in soup.find_all(
            "a",
            href=True
        ):

            href = a.get(
                "href",
                ""
            ).strip()

            if not href:
                continue

            if not href.startswith("http"):
                continue

            hostname = urlparse(
                href
            ).netloc.lower()

            if (
                "google.com" in hostname
                or "googleusercontent.com" in hostname
                or "gstatic.com" in hostname
            ):
                continue

            if href not in links:

                links.append(href)

        print(
            f"      Liens externes    : "
            f"{len(links)}"
        )

        for i, link in enumerate(
            links[:10],
            start=1
        ):

            print(
                f"        [{i}] {link}"
            )

        return links

    except Exception as e:

        print(
            f"      ERREUR Google     : "
            f"{type(e).__name__}: {e}"
        )

        return []


# ============================================================
# RESOLUTION
# ============================================================

def resolve_google_news_url(url):

    if not url:

        return None, "EMPTY"

    if not is_google_news_url(url):

        return url, "DIRECT"

    # --------------------------------------------------------
    # 1. TOKEN
    # --------------------------------------------------------

    print(
        "      Méthode 1 : token direct"
    )

    direct = decode_token_directly(
        url
    )

    if direct:

        print(
            f"      ✓ Résolu direct  : "
            f"{direct}"
        )

        return direct, "TOKEN_DIRECT"

    print(
        "      ✗ Aucun résultat"
    )

    # --------------------------------------------------------
    # 2. GOOGLE PAGE
    # --------------------------------------------------------

    print(
        "      Méthode 2 : page Google News"
    )

    links = extract_google_page_links(
        url
    )

    if links:

        selected = links[0]

        print(
            f"      ✓ Lien sélectionné : "
            f"{selected}"
        )

        return selected, "GOOGLE_PAGE"

    print(
        "      ✗ Aucun lien externe"
    )

    return None, "UNRESOLVED"


# ============================================================
# META DESCRIPTION
# ============================================================

def extract_meta_description(soup):

    candidates = [
        ("name", "description"),
        ("property", "og:description"),
        ("name", "twitter:description"),
    ]

    for attr, value in candidates:

        tag = soup.find(
            "meta",
            attrs={
                attr: value
            }
        )

        if tag:

            content = clean_text(
                tag.get(
                    "content",
                    ""
                )
            )

            if content:

                return content

    return ""


# ============================================================
# JSON-LD
# ============================================================

def extract_jsonld(soup):

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    print(
        f"      JSON-LD blocs     : "
        f"{len(scripts)}"
    )

    for script in scripts:

        raw = (
            script.string
            or script.get_text()
        )

        if not raw:
            continue

        try:

            data = json.loads(
                raw.strip()
            )

        except Exception:

            continue

        objects = []

        if isinstance(
            data,
            dict
        ):

            objects.append(data)

            graph = data.get(
                "@graph"
            )

            if isinstance(
                graph,
                list
            ):

                objects.extend(
                    graph
                )

        elif isinstance(
            data,
            list
        ):

            objects.extend(
                data
            )

        for obj in objects:

            if not isinstance(
                obj,
                dict
            ):
                continue

            body = obj.get(
                "articleBody"
            )

            if body:

                text = clean_text(
                    str(body)
                )

                if text:

                    return (
                        text,
                        "JSON_LD_ARTICLE_BODY"
                    )

    return "", None


# ============================================================
# HTML ARTICLE
# ============================================================

def extract_html_article(soup):

    article = soup.find(
        "article"
    )

    if not article:

        return "", None

    paragraphs = article.find_all(
        "p"
    )

    texts = []

    for p in paragraphs:

        text = clean_text(
            p.get_text(
                " ",
                strip=True
            )
        )

        if text:

            texts.append(text)

    result = " ".join(
        texts
    )

    if result:

        return result, "HTML_ARTICLE"

    return "", None


# ============================================================
# PARAGRAPHES
# ============================================================

def extract_paragraphs(soup):

    paragraphs = soup.find_all(
        "p"
    )

    texts = []

    for p in paragraphs:

        text = clean_text(
            p.get_text(
                " ",
                strip=True
            )
        )

        if len(text) < 40:
            continue

        texts.append(text)

    result = " ".join(
        texts
    )

    if result:

        return (
            result,
            "HTML_PARAGRAPHS"
        )

    return "", None


# ============================================================
# TRAFILATURA
# ============================================================

def extract_trafilatura(
    html_content
):

    if trafilatura is None:

        print(
            "      Trafilatura       : "
            "NON INSTALLÉE"
        )

        return "", None

    try:

        result = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=False,
            include_links=False,
            favor_precision=True,
        )

        result = clean_text(
            result
        )

        if result:

            return (
                result,
                "TRAFILATURA"
            )

    except Exception as e:

        print(
            f"      Trafilatura erreur: "
            f"{type(e).__name__}: {e}"
        )

    return "", None


# ============================================================
# DIAGNOSTIC URL MEDIA
# ============================================================

def diagnose_media_url(
    media_url
):

    print()
    print(
        "      "
        + "-" * 60
    )

    print(
        "      DIAGNOSTIC PAGE MEDIA"
    )

    print(
        "      "
        + "-" * 60
    )

    print(
        f"      URL : {media_url}"
    )

    parsed = urlparse(
        media_url
    )

    print(
        f"      Domaine            : "
        f"{parsed.netloc}"
    )

    print(
        f"      Schéma             : "
        f"{parsed.scheme}"
    )

    # --------------------------------------------------------
    # HTTP
    # --------------------------------------------------------

    try:

        start = time.time()

        response = requests.get(
            media_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        elapsed = (
            time.time() - start
        )

    except Exception as e:

        print()
        print(
            f"      ❌ ERREUR HTTP : "
            f"{type(e).__name__}: {e}"
        )

        return

    print()
    print(
        "      HTTP"
    )

    print(
        f"      Status             : "
        f"{response.status_code}"
    )

    print(
        f"      URL finale         : "
        f"{response.url}"
    )

    print(
        f"      Temps              : "
        f"{elapsed:.2f}s"
    )

    print(
        f"      Content-Type       : "
        f"{response.headers.get('Content-Type', 'N/A')}"
    )

    print(
        f"      Content-Length     : "
        f"{response.headers.get('Content-Length', 'N/A')}"
    )

    print(
        f"      Taille HTML        : "
        f"{len(response.content):,} bytes"
    )

    if not response.text:

        print(
            "      ❌ HTML VIDE"
        )

        return

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    print()
    print(
        "      STRUCTURE HTML"
    )

    print(
        f"      <title>            : "
        f"{bool(soup.find('title'))}"
    )

    print(
        f"      <article>          : "
        f"{bool(soup.find('article'))}"
    )

    print(
        f"      <p>                : "
        f"{len(soup.find_all('p'))}"
    )

    print(
        f"      JSON-LD            : "
        f"{len(soup.find_all('script', type='application/ld+json'))}"
    )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title_tag = soup.find(
        "title"
    )

    title = ""

    if title_tag:

        title = clean_text(
            title_tag.get_text()
        )

    print()
    print(
        "      TITLE"
    )

    print(
        f"      {title[:500]}"
    )

    # --------------------------------------------------------
    # META
    # --------------------------------------------------------

    print()
    print(
        "      META DESCRIPTION"
    )

    meta = extract_meta_description(
        soup
    )

    if meta:

        print(
            f"      ✓ {len(meta)} caractères"
        )

        print(
            f"      {meta[:700]}"
        )

    else:

        print(
            "      ✗ Aucune"
        )

    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    print()
    print(
        "      JSON-LD ARTICLE BODY"
    )

    jsonld_text, jsonld_method = (
        extract_jsonld(soup)
    )

    if jsonld_text:

        print(
            f"      ✓ {len(jsonld_text):,} caractères"
        )

        print(
            f"      ✓ {word_count(jsonld_text):,} mots"
        )

        print(
            f"      Méthode : {jsonld_method}"
        )

        print(
            f"      Aperçu  : "
            f"{jsonld_text[:700]}"
        )

    else:

        print(
            "      ✗ Aucun articleBody"
        )

    # --------------------------------------------------------
    # ARTICLE
    # --------------------------------------------------------

    print()
    print(
        "      HTML <ARTICLE>"
    )

    article_text, article_method = (
        extract_html_article(
            soup
        )
    )

    if article_text:

        print(
            f"      ✓ {len(article_text):,} caractères"
        )

        print(
            f"      ✓ {word_count(article_text):,} mots"
        )

        print(
            f"      Méthode : {article_method}"
        )

        print(
            f"      Aperçu  : "
            f"{article_text[:700]}"
        )

    else:

        print(
            "      ✗ Aucun contenu <article>"
        )

    # --------------------------------------------------------
    # PARAGRAPHES
    # --------------------------------------------------------

    print()
    print(
        "      PARAGRAPHES"
    )

    paragraph_text, paragraph_method = (
        extract_paragraphs(
            soup
        )
    )

    if paragraph_text:

        print(
            f"      ✓ {len(paragraph_text):,} caractères"
        )

        print(
            f"      ✓ {word_count(paragraph_text):,} mots"
        )

        print(
            f"      Méthode : {paragraph_method}"
        )

        print(
            f"      Aperçu  : "
            f"{paragraph_text[:700]}"
        )

    else:

        print(
            "      ✗ Aucun paragraphe exploitable"
        )

    # --------------------------------------------------------
    # TRAFILATURA
    # --------------------------------------------------------

    print()
    print(
        "      TRAFILATURA"
    )

    traf_text, traf_method = (
        extract_trafilatura(
            response.text
        )
    )

    if traf_text:

        print(
            f"      ✓ {len(traf_text):,} caractères"
        )

        print(
            f"      ✓ {word_count(traf_text):,} mots"
        )

        print(
            f"      Méthode : {traf_method}"
        )

        print(
            f"      Aperçu  : "
            f"{traf_text[:700]}"
        )

    else:

        print(
            "      ✗ Aucun contenu"
        )

    # --------------------------------------------------------
    # BLOCAGE
    # --------------------------------------------------------

    print()
    print(
        "      DIAGNOSTIC RAPIDE"
    )

    lower_html = response.text.lower()

    blocking_terms = [
        "access denied",
        "access forbidden",
        "forbidden",
        "captcha",
        "cloudflare",
        "robot",
        "verify you are human",
        "enable javascript",
        "just a moment",
        "request blocked",
    ]

    found = [
        term
        for term in blocking_terms
        if term in lower_html
    ]

    if found:

        print(
            "      ⚠ Signatures de blocage : "
            + ", ".join(found)
        )

    else:

        print(
            "      Aucun blocage évident détecté."
        )

    # --------------------------------------------------------
    # HTML BRUT
    # --------------------------------------------------------

    print()
    print(
        "      DÉBUT DU HTML BRUT"
    )

    print(
        "      "
        + "-" * 60
    )

    preview = response.text[:2000]

    preview = preview.replace(
        "\n",
        " "
    )

    print(
        preview
    )

    print(
        "      "
        + "-" * 60
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=" * 70
    )

    print(
        "GOOGLE NEWS V5 — DIAGNOSTIC"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Fichier : {INPUT_FILE}"
    )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    try:

        rows = load_csv()

    except Exception as e:

        print()
        print(
            f"❌ Erreur lecture CSV : "
            f"{type(e).__name__}: {e}"
        )

        return

    print(
        f"Articles V2 : {len(rows)}"
    )

    # --------------------------------------------------------
    # Pertinents
    # --------------------------------------------------------

    relevant = [
        row
        for row in rows
        if is_relevant(row)
    ]

    print(
        f"Articles pertinents : "
        f"{len(relevant)}"
    )

    if not relevant:

        print()
        print(
            "❌ Aucun article pertinent."
        )

        return

    # --------------------------------------------------------
    # TEST
    # --------------------------------------------------------

    articles = relevant[
        :TEST_COUNT
    ]

    print()
    print(
        f"Articles testés : "
        f"{len(articles)}"
    )

    # --------------------------------------------------------
    # LOOP
    # --------------------------------------------------------

    for i, row in enumerate(
        articles,
        start=1
    ):

        title = str(
            row.get(
                "title",
                ""
            )
        )

        google_url = str(
            row.get(
                "url",
                ""
            )
        )

        source = str(
            row.get(
                "source",
                ""
            )
        )

        date = str(
            row.get(
                "date",
                ""
            )
        )

        print()
        print()
        print(
            "=" * 70
        )

        print(
            f"ARTICLE {i}/{len(articles)}"
        )

        print(
            "=" * 70
        )

        print()
        print(
            f"Titre  : {title}"
        )

        print(
            f"Source : {source}"
        )

        print(
            f"Date   : {date}"
        )

        print()
        print(
            "URL GOOGLE NEWS"
        )

        print(
            google_url
        )

        # ----------------------------------------------------
        # RESOLUTION
        # ----------------------------------------------------

        print()
        print(
            "RÉSOLUTION GOOGLE NEWS"
        )

        print(
            "-" * 70
        )

        start = time.time()

        media_url, method = (
            resolve_google_news_url(
                google_url
            )
        )

        elapsed = (
            time.time() - start
        )

        print()
        print(
            f"Résultat : {method}"
        )

        print(
            f"Temps    : {elapsed:.2f}s"
        )

        if not media_url:

            print()
            print(
                "❌ URL média non résolue."
            )

            continue

        print()
        print(
            "URL MÉDIA FINALE"
        )

        print(
            media_url
        )

        # ----------------------------------------------------
        # DIAGNOSTIC
        # ----------------------------------------------------

        diagnose_media_url(
            media_url
        )

    # --------------------------------------------------------
    # FIN
    # --------------------------------------------------------

    print()
    print()
    print(
        "=" * 70
    )

    print(
        "FIN DU DIAGNOSTIC"
    )

    print(
        "=" * 70
    )

    print()
    print(
        "SQLite : AUCUNE MODIFICATION"
    )


if __name__ == "__main__":
    main()