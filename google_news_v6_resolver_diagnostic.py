# google_news_v6_resolver_diagnostic.py
#
# DIAGNOSTIC GOOGLE NEWS V6
#
# Objectif :
#   Trouver la vraie URL de l'article média à partir
#   d'une URL Google News RSS /articles/...
#
# IMPORTANT :
#   - Aucun pandas
#   - Aucun SQLite
#   - Aucun GPT-OSS
#   - Aucun changement dans le projet
#   - Teste seulement 5 articles
#
# Sortie :
#   - google_news_v6_candidates.csv
#
# Le script affiche toutes les URLs candidates trouvées
# afin de comprendre comment Google News encode maintenant
# les destinations.

from pathlib import Path
from urllib.parse import (
    urlparse,
    unquote,
)
import base64
import csv
import html
import json
import re
import time

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "google_news_v2_results.csv"
OUTPUT_FILE = BASE_DIR / "google_news_v6_candidates.csv"

TEST_COUNT = 5

REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Cache-Control": "no-cache",
}


# ============================================================
# OUTILS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = html.unescape(str(value))
    value = value.replace("\\/", "/")

    return value.strip()


def is_google_domain(url):
    if not url:
        return True

    try:
        hostname = urlparse(url).netloc.lower()
    except Exception:
        return True

    google_domains = (
        "google.com",
        "googleusercontent.com",
        "gstatic.com",
        "googleapis.com",
        "googletagmanager.com",
        "google-analytics.com",
    )

    return hostname.endswith(google_domains)


def is_http_url(url):
    return (
        isinstance(url, str)
        and (
            url.startswith("http://")
            or url.startswith("https://")
        )
    )


def normalize_url(url):

    if not url:
        return ""

    url = html.unescape(url)
    url = url.replace("\\/", "/")
    url = url.replace("\\u002F", "/")
    url = url.replace("\\u003A", ":")
    url = url.replace("\\u003F", "?")
    url = url.replace("\\u003D", "=")
    url = url.replace("\\u0026", "&")

    url = unquote(url)

    # Nettoyage caractères de fin
    url = url.strip(
        " \t\r\n\"'<>[](){};,."
    )

    return url


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


# ============================================================
# CSV
# ============================================================

def load_articles():

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

        rows = list(
            csv.DictReader(f)
        )

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
# EXTRACTION DES URLS BRUTES
# ============================================================

def extract_raw_urls(text):

    if not text:
        return []

    urls = re.findall(
        r'https?://[^\s"\'<>\\]+',
        text
    )

    results = []

    for url in urls:

        url = normalize_url(url)

        if not is_http_url(url):
            continue

        if url not in results:
            results.append(url)

    return results


# ============================================================
# EXTRACTION DES URLS DEPUIS LE HTML
# ============================================================

def extract_href_urls(soup):

    candidates = []

    for tag in soup.find_all(
        href=True
    ):

        href = tag.get(
            "href",
            ""
        )

        href = normalize_url(
            href
        )

        if is_http_url(href):

            if href not in candidates:
                candidates.append(href)

    return candidates


# ============================================================
# EXTRACTION DE TOUS LES ATTRIBUTS
# ============================================================

def extract_attribute_urls(soup):

    candidates = []

    for tag in soup.find_all(True):

        for key, value in tag.attrs.items():

            if isinstance(value, list):
                value = " ".join(
                    str(x)
                    for x in value
                )

            if not isinstance(
                value,
                str
            ):
                continue

            # URL directe
            urls = extract_raw_urls(
                value
            )

            for url in urls:

                if url not in candidates:
                    candidates.append(url)

            # URL encodée
            decoded = normalize_url(
                value
            )

            urls = extract_raw_urls(
                decoded
            )

            for url in urls:

                if url not in candidates:
                    candidates.append(url)

    return candidates


# ============================================================
# EXTRACTION JSON-LD
# ============================================================

def extract_jsonld_urls(soup):

    candidates = []

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        raw = (
            script.string
            or script.get_text()
        )

        if not raw:
            continue

        # URLs brutes
        for url in extract_raw_urls(raw):

            if url not in candidates:
                candidates.append(url)

        # JSON
        try:

            data = json.loads(
                raw
            )

            serialized = json.dumps(
                data,
                ensure_ascii=False
            )

            for url in extract_raw_urls(
                serialized
            ):

                if url not in candidates:
                    candidates.append(url)

        except Exception:
            pass

    return candidates


# ============================================================
# EXTRACTION DES SCRIPTS
# ============================================================

def extract_script_urls(soup):

    candidates = []

    scripts = soup.find_all(
        "script"
    )

    print(
        f"      Scripts trouvés    : "
        f"{len(scripts)}"
    )

    for script in scripts:

        raw = script.string

        if raw is None:
            raw = script.get_text()

        if not raw:
            continue

        # ----------------------------------------------------
        # URLs directes
        # ----------------------------------------------------

        urls = extract_raw_urls(
            raw
        )

        for url in urls:

            if url not in candidates:
                candidates.append(url)

        # ----------------------------------------------------
        # Décodage Unicode JS
        # ----------------------------------------------------

        decoded = raw

        replacements = {
            r"\u002F": "/",
            r"\u003A": ":",
            r"\u003F": "?",
            r"\u003D": "=",
            r"\u0026": "&",
            r"\/": "/",
        }

        for old, new in replacements.items():

            decoded = decoded.replace(
                old,
                new
            )

        urls = extract_raw_urls(
            decoded
        )

        for url in urls:

            if url not in candidates:
                candidates.append(url)

    return candidates


# ============================================================
# EXTRACTION DE PATTERNS GOOGLE
# ============================================================

def extract_google_patterns(text):

    candidates = []

    if not text:
        return candidates

    patterns = [

        # url:"https://..."
        r'["\']url["\']\s*:\s*["\'](https?://[^"\']+)',

        # url=https://...
        r'url=(https?://[^&"\']+)',

        # targetUrl
        r'targetUrl["\']?\s*[:=]\s*["\'](https?://[^"\']+)',

        # destination
        r'destination["\']?\s*[:=]\s*["\'](https?://[^"\']+)',

        # canonicalUrl
        r'canonicalUrl["\']?\s*[:=]\s*["\'](https?://[^"\']+)',

        # articleUrl
        r'articleUrl["\']?\s*[:=]\s*["\'](https?://[^"\']+)',

        # sourceUrl
        r'sourceUrl["\']?\s*[:=]\s*["\'](https?://[^"\']+)',

        # link
        r'["\']link["\']\s*:\s*["\'](https?://[^"\']+)',
    ]

    for pattern in patterns:

        try:

            matches = re.findall(
                pattern,
                text,
                flags=re.IGNORECASE
            )

        except Exception:
            continue

        for match in matches:

            url = normalize_url(
                match
            )

            if is_http_url(url):

                if url not in candidates:
                    candidates.append(url)

    return candidates


# ============================================================
# BASE64 / TOKEN ANALYSIS
# ============================================================

def analyze_google_token(
    google_url
):

    print()
    print(
        "      ANALYSE TOKEN GOOGLE"
    )

    match = re.search(
        r"/(?:rss/)?articles/([^?]+)",
        google_url
    )

    if not match:

        print(
            "      Aucun token détecté."
        )

        return []

    token = match.group(1)

    print(
        f"      Longueur token     : "
        f"{len(token)}"
    )

    candidates = []

    variants = [
        token,
        token.replace(
            "-",
            "+"
        ).replace(
            "_",
            "/"
        ),
    ]

    for index, candidate in enumerate(
        variants,
        start=1
    ):

        try:

            padding = "=" * (
                -len(candidate) % 4
            )

            decoded = base64.b64decode(
                candidate + padding,
                validate=False
            )

            print(
                f"      Variante {index}     : "
                f"{len(decoded)} bytes"
            )

            text = decoded.decode(
                "utf-8",
                errors="ignore"
            )

            print(
                f"      Texte décodé       : "
                f"{len(text)} caractères"
            )

            # Afficher les premiers caractères
            preview = text[:500]

            preview = (
                preview
                .replace("\n", " ")
                .replace("\r", " ")
            )

            print(
                f"      Aperçu             : "
                f"{preview}"
            )

            urls = extract_raw_urls(
                text
            )

            for url in urls:

                if url not in candidates:
                    candidates.append(url)

        except Exception as e:

            print(
                f"      Variante {index} "
                f"erreur : {type(e).__name__}"
            )

    return candidates


# ============================================================
# FILTRAGE / CLASSEMENT
# ============================================================

def classify_candidate(
    url,
    source
):

    hostname = urlparse(
        url
    ).netloc.lower()

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Non Google
    # --------------------------------------------------------

    if not is_google_domain(url):

        score += 10
        reasons.append(
            "DOMAINE_NON_GOOGLE"
        )

    # --------------------------------------------------------
    # Domaine source
    # --------------------------------------------------------

    source_normalized = (
        source
        .lower()
        .replace("www.", "")
        .strip()
    )

    if source_normalized:

        if source_normalized in hostname:

            score += 50

            reasons.append(
                "DOMAINE_SOURCE_MATCH"
            )

    # --------------------------------------------------------
    # URL article classique
    # --------------------------------------------------------

    article_words = [
        "/article/",
        "/articles/",
        "/actualite/",
        "/actualites/",
        "/news/",
        "/2025/",
        "/2024/",
        "/2023/",
        "/2022/",
        "/2021/",
        "/2020/",
        "/2019/",
        "/2018/",
        ".html",
        ".htm",
    ]

    for word in article_words:

        if word in url.lower():

            score += 5

            reasons.append(
                f"PATTERN_{word}"
            )

            break

    # --------------------------------------------------------
    # URLs inutiles
    # --------------------------------------------------------

    useless_patterns = [
        "/search",
        "/tag/",
        "/category/",
        "/author/",
        "/login",
        "/subscribe",
        "/contact",
        "/about",
        "/privacy",
        "/terms",
    ]

    for pattern in useless_patterns:

        if pattern in url.lower():

            score -= 20

            reasons.append(
                f"PATTERN_NON_ARTICLE_{pattern}"
            )

    return score, reasons


def rank_candidates(
    candidates,
    source
):

    unique = []

    for url in candidates:

        url = normalize_url(
            url
        )

        if not is_http_url(url):
            continue

        if url not in unique:

            unique.append(url)

    ranked = []

    for url in unique:

        score, reasons = classify_candidate(
            url,
            source
        )

        ranked.append({
            "url": url,
            "score": score,
            "reasons": " | ".join(
                reasons
            ),
        })

    ranked.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return ranked


# ============================================================
# TEST D'UNE PAGE GOOGLE NEWS
# ============================================================

def diagnose_google_page(
    google_url,
    source
):

    print()
    print(
        "      "
        + "-" * 64
    )

    print(
        "      TÉLÉCHARGEMENT GOOGLE NEWS"
    )

    print(
        "      "
        + "-" * 64
    )

    try:

        start = time.time()

        response = requests.get(
            google_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        elapsed = (
            time.time() - start
        )

    except Exception as e:

        print(
            f"      ❌ HTTP ERROR : "
            f"{type(e).__name__}: {e}"
        )

        return []

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
        f"      Taille HTML        : "
        f"{len(response.text):,} caractères"
    )

    # --------------------------------------------------------
    # BeautifulSoup
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    print()
    print(
        "      STRUCTURE"
    )

    print(
        f"      <a>                : "
        f"{len(soup.find_all('a'))}"
    )

    print(
        f"      <script>            : "
        f"{len(soup.find_all('script'))}"
    )

    print(
        f"      <meta>              : "
        f"{len(soup.find_all('meta'))}"
    )

    print(
        f"      <link>              : "
        f"{len(soup.find_all('link'))}"
    )

    # --------------------------------------------------------
    # Candidates par méthode
    # --------------------------------------------------------

    all_candidates = []

    # --------------------------------------------------------
    # 1. HTML brut
    # --------------------------------------------------------

    print()
    print(
        "      [1] URLS HTML BRUT"
    )

    raw_candidates = extract_raw_urls(
        response.text
    )

    print(
        f"      Trouvées            : "
        f"{len(raw_candidates)}"
    )

    for url in raw_candidates[:20]:

        print(
            f"        {url}"
        )

        all_candidates.append(
            ("RAW_HTML", url)
        )

    # --------------------------------------------------------
    # 2. HREF
    # --------------------------------------------------------

    print()
    print(
        "      [2] HREF"
    )

    href_candidates = extract_href_urls(
        soup
    )

    print(
        f"      Trouvées            : "
        f"{len(href_candidates)}"
    )

    for url in href_candidates[:20]:

        print(
            f"        {url}"
        )

        all_candidates.append(
            ("HREF", url)
        )

    # --------------------------------------------------------
    # 3. ATTRIBUTS
    # --------------------------------------------------------

    print()
    print(
        "      [3] ATTRIBUTS HTML"
    )

    attr_candidates = extract_attribute_urls(
        soup
    )

    print(
        f"      Trouvées            : "
        f"{len(attr_candidates)}"
    )

    for url in attr_candidates[:20]:

        print(
            f"        {url}"
        )

        all_candidates.append(
            ("ATTRIBUTE", url)
        )

    # --------------------------------------------------------
    # 4. JSON-LD
    # --------------------------------------------------------

    print()
    print(
        "      [4] JSON-LD"
    )

    json_candidates = extract_jsonld_urls(
        soup
    )

    print(
        f"      Trouvées            : "
        f"{len(json_candidates)}"
    )

    for url in json_candidates[:20]:

        print(
            f"        {url}"
        )

        all_candidates.append(
            ("JSON_LD", url)
        )

    # --------------------------------------------------------
    # 5. SCRIPTS
    # --------------------------------------------------------

    print()
    print(
        "      [5] JAVASCRIPT"
    )

    script_candidates = extract_script_urls(
        soup
    )

    print(
        f"      Trouvées            : "
        f"{len(script_candidates)}"
    )

    for url in script_candidates[:20]:

        print(
            f"        {url}"
        )

        all_candidates.append(
            ("SCRIPT", url)
        )

    # --------------------------------------------------------
    # 6. PATTERNS GOOGLE
    # --------------------------------------------------------

    print()
    print(
        "      [6] PATTERNS GOOGLE"
    )

    pattern_candidates = extract_google_patterns(
        response.text
    )

    print(
        f"      Trouvées            : "
        f"{len(pattern_candidates)}"
    )

    for url in pattern_candidates[:20]:

        print(
            f"        {url}"
        )

        all_candidates.append(
            ("GOOGLE_PATTERN", url)
        )

    # --------------------------------------------------------
    # 7. TOKEN
    # --------------------------------------------------------

    token_candidates = analyze_google_token(
        google_url
    )

    for url in token_candidates:

        all_candidates.append(
            ("TOKEN_DECODE", url)
        )

    # --------------------------------------------------------
    # DÉDUPLICATION
    # --------------------------------------------------------

    deduplicated = {}

    for method, url in all_candidates:

        url = normalize_url(
            url
        )

        if not is_http_url(url):
            continue

        if url not in deduplicated:

            deduplicated[url] = []

        if method not in deduplicated[url]:

            deduplicated[url].append(
                method
            )

    print()
    print(
        "=" * 64
    )

    print(
        "      CANDIDATS UNIQUES"
    )

    print(
        "=" * 64
    )

    print(
        f"      Total               : "
        f"{len(deduplicated)}"
    )

    # --------------------------------------------------------
    # Classement
    # --------------------------------------------------------

    ranked = []

    for url, methods in deduplicated.items():

        score, reasons = classify_candidate(
            url,
            source
        )

        ranked.append({
            "url": url,
            "methods": ", ".join(
                methods
            ),
            "score": score,
            "reasons": " | ".join(
                reasons
            ),
        })

    ranked.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # Affichage
    # --------------------------------------------------------

    if not ranked:

        print()
        print(
            "      ❌ AUCUNE URL CANDIDATE"
        )

    else:

        for i, item in enumerate(
            ranked[:30],
            start=1
        ):

            print()
            print(
                f"      [{i}] SCORE = "
                f"{item['score']}"
            )

            print(
                f"          URL     : "
                f"{item['url']}"
            )

            print(
                f"          Méthodes: "
                f"{item['methods']}"
            )

            print(
                f"          Raisons : "
                f"{item['reasons']}"
            )

    return ranked


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=" * 70
    )

    print(
        "GOOGLE NEWS V6 — RESOLVER DIAGNOSTIC"
    )

    print(
        "=" * 70
    )

    print()
    print(
        f"Fichier : {INPUT_FILE}"
    )

    try:

        rows = load_articles()

    except Exception as e:

        print()
        print(
            f"❌ Erreur CSV : "
            f"{type(e).__name__}: {e}"
        )

        return

    print(
        f"Articles V2 : "
        f"{len(rows)}"
    )

    relevant = [
        row
        for row in rows
        if is_relevant(row)
    ]

    print(
        f"Articles pertinents : "
        f"{len(relevant)}"
    )

    articles = relevant[
        :TEST_COUNT
    ]

    print()
    print(
        f"Articles testés : "
        f"{len(articles)}"
    )

    output_rows = []

    # ========================================================
    # TEST
    # ========================================================

    for index, row in enumerate(
        articles,
        start=1
    ):

        title = str(
            row.get(
                "title",
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

        google_url = str(
            row.get(
                "url",
                ""
            )
        )

        print()
        print()
        print(
            "#" * 70
        )

        print(
            f"ARTICLE {index}/{len(articles)}"
        )

        print(
            "#" * 70
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
            "GOOGLE NEWS URL"
        )

        print(
            google_url
        )

        ranked = diagnose_google_page(
            google_url,
            source
        )

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        for rank, item in enumerate(
            ranked,
            start=1
        ):

            output_rows.append({
                "article_index": index,
                "title": title,
                "source": source,
                "date": date,
                "google_news_url": google_url,
                "rank": rank,
                "score": item["score"],
                "candidate_url": item["url"],
                "methods": item["methods"],
                "reasons": item["reasons"],
            })

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    fieldnames = [
        "article_index",
        "title",
        "source",
        "date",
        "google_news_url",
        "rank",
        "score",
        "candidate_url",
        "methods",
        "reasons",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            output_rows
        )

    # ========================================================
    # FIN
    # ========================================================

    print()
    print()
    print(
        "=" * 70
    )

    print(
        "FIN GOOGLE NEWS V6"
    )

    print(
        "=" * 70
    )

    print()
    print(
        f"Candidats sauvegardés : "
        f"{len(output_rows)}"
    )

    print()
    print(
        f"Fichier : {OUTPUT_FILE}"
    )

    print()
    print(
        "SQLite : AUCUNE MODIFICATION"
    )

    print()
    print(
        "Envoie-moi la sortie complète."
    )

    print(
        "Le fichier google_news_v6_candidates.csv "
        "sera également utile."
    )


if __name__ == "__main__":
    main()