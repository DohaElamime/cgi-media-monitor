# google_news_v5.py

import base64
import csv
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

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

OUTPUT_FILE = BASE_DIR / "google_news_v5_results.csv"

OUTPUT_ERRORS = BASE_DIR / "google_news_v5_errors.csv"

REQUEST_TIMEOUT = 20

MIN_CONTENT_CHARS = 250
MIN_CONTENT_WORDS = 45

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
    "Connection": "keep-alive",
}


# ============================================================
# CSV
# ============================================================

def read_csv(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):

    if not rows:
        with open(
            path,
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as f:
            f.write("")
        return

    fields = []

    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# TEXTE
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = html.unescape(str(text))

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def word_count(text):

    text = clean_text(text)

    if not text:
        return 0

    return len(text.split())


def is_usable_content(text):

    text = clean_text(text)

    return (
        len(text) >= MIN_CONTENT_CHARS
        and word_count(text) >= MIN_CONTENT_WORDS
    )


# ============================================================
# URL GOOGLE NEWS
# ============================================================

def is_external_url(url):

    if not url:
        return False

    try:

        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https"
        }:
            return False

        hostname = (
            parsed.netloc or ""
        ).lower()

        if not hostname:
            return False

        if "news.google.com" in hostname:
            return False

        if (
            hostname == "google.com"
            or hostname.endswith(".google.com")
        ):
            return False

        return True

    except Exception:
        return False


def clean_url(url):

    if not url:
        return ""

    url = html.unescape(
        str(url).strip()
    )

    url = unquote(url)

    return url


def decode_token_directly(url):

    """
    Tentative de décodage direct du token Google News.
    """

    match = re.search(
        r"/rss/articles/([^?]+)",
        url
    )

    if not match:
        return None

    token = match.group(1)

    try:

        padded = token + (
            "=" * (-len(token) % 4)
        )

        raw = base64.urlsafe_b64decode(
            padded
        )

    except Exception:
        return None

    # --------------------------------------------------------
    # Recherche URL ASCII
    # --------------------------------------------------------

    candidates = re.findall(
        rb"https?://[^\s\"'<>]+",
        raw
    )

    for candidate in candidates:

        try:

            candidate = candidate.decode(
                "utf-8",
                errors="ignore"
            )

        except Exception:
            continue

        candidate = clean_url(
            candidate
        )

        if is_external_url(candidate):
            return candidate

    # --------------------------------------------------------
    # Recherche UTF-16
    # --------------------------------------------------------

    for encoding in (
        "utf-16-le",
        "utf-16-be"
    ):

        try:

            text = raw.decode(
                encoding,
                errors="ignore"
            )

            candidates = re.findall(
                r"https?://[^\s\"'<>]+",
                text
            )

            for candidate in candidates:

                candidate = clean_url(
                    candidate
                )

                if is_external_url(
                    candidate
                ):
                    return candidate

        except Exception:
            pass

    return None


def extract_google_page_links(url):

    """
    Méthode qui a fonctionné dans ton test V4 :
    ouverture de la page Google News puis extraction
    des liens externes présents dans la page.
    """

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        response.raise_for_status()

    except Exception:
        return []

    content = response.text

    candidates = []

    # href="..."
    candidates.extend(
        re.findall(
            r'href=["\']([^"\']+)["\']',
            content,
            flags=re.IGNORECASE
        )
    )

    # URLs absolues
    candidates.extend(
        re.findall(
            r'https?://[^\s"\'<>]+',
            content
        )
    )

    results = []

    for candidate in candidates:

        candidate = clean_url(
            candidate
        )

        if not is_external_url(
            candidate
        ):
            continue

        # Éviter certains liens Google parasites
        hostname = (
            urlparse(candidate)
            .netloc
            .lower()
        )

        if (
            "accounts.google.com" in hostname
            or "support.google.com" in hostname
            or "policies.google.com" in hostname
        ):
            continue

        if candidate not in results:

            results.append(candidate)

    return results


def resolve_google_news_url(url):

    url = clean_url(url)

    if not url:
        return "", "EMPTY"

    # Déjà une URL externe
    if is_external_url(url):
        return url, "ALREADY_EXTERNAL"

    # Méthode directe
    decoded = decode_token_directly(url)

    if decoded:
        return decoded, "TOKEN"

    # Méthode Google Page
    candidates = extract_google_page_links(url)

    if candidates:

        return (
            candidates[0],
            "GOOGLE_PAGE"
        )

    return "", "UNRESOLVED"


# ============================================================
# META DESCRIPTION
# ============================================================

def extract_meta_description(soup):

    selectors = [
        ("meta", {"name": "description"}),
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "twitter:description"}),
    ]

    for tag_name, attrs in selectors:

        tag = soup.find(
            tag_name,
            attrs=attrs
        )

        if not tag:
            continue

        value = clean_text(
            tag.get(
                "content",
                ""
            )
        )

        if value:
            return value

    return ""


# ============================================================
# JSON-LD
# ============================================================

def extract_jsonld(soup):

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(raw)

        except Exception:
            continue

        objects = []

        if isinstance(data, dict):

            objects.append(data)

            graph = data.get("@graph")

            if isinstance(graph, list):
                objects.extend(graph)

        elif isinstance(data, list):

            objects.extend(data)

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            article_body = obj.get(
                "articleBody"
            )

            if not article_body:
                continue

            article_body = clean_text(
                article_body
            )

            if is_usable_content(
                article_body
            ):

                return article_body

    return ""


# ============================================================
# TRAFILATURA
# ============================================================

def extract_trafilatura(html_content):

    if trafilatura is None:
        return ""

    try:

        text = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=False,
            include_links=False,
            favor_precision=True,
            favor_recall=False,
        )

        text = clean_text(text)

        if is_usable_content(text):
            return text

    except Exception:
        pass

    return ""


# ============================================================
# EXTRACTION HTML
# ============================================================

def extract_html_article(soup):

    # --------------------------------------------------------
    # Article
    # --------------------------------------------------------

    article = soup.find("article")

    if article:

        paragraphs = article.find_all("p")

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

        combined = clean_text(
            " ".join(texts)
        )

        if is_usable_content(
            combined
        ):
            return combined

    # --------------------------------------------------------
    # Paragraphes
    # --------------------------------------------------------

    paragraphs = soup.find_all("p")

    texts = []

    for p in paragraphs:

        text = clean_text(
            p.get_text(
                " ",
                strip=True
            )
        )

        if word_count(text) >= 5:
            texts.append(text)

    combined = clean_text(
        " ".join(texts)
    )

    if is_usable_content(
        combined
    ):
        return combined

    return ""


# ============================================================
# EXTRACTION D'UNE PAGE MÉDIA
# ============================================================

def extract_media_page(url):

    result = {
        "final_url": "",
        "http_status": "",
        "summary": "",
        "content": "",
        "extraction_method": "",
        "extraction_status": "FAILED",
        "extraction_error": "",
    }

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        result["http_status"] = (
            response.status_code
        )

        result["final_url"] = (
            response.url
        )

        response.raise_for_status()

    except Exception as exc:

        result["extraction_error"] = str(
            exc
        )

        return result

    if not response.text:

        result[
            "extraction_error"
        ] = "HTML vide"

        return result

    html_content = response.text

    soup = BeautifulSoup(
        html_content,
        "html.parser"
    )

    # Meta avant nettoyage
    result[
        "summary"
    ] = extract_meta_description(
        soup
    )

    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    content = extract_jsonld(
        soup
    )

    if content:

        result[
            "content"
        ] = content

        result[
            "extraction_method"
        ] = "JSON_LD"

        result[
            "extraction_status"
        ] = "SUCCESS"

        return result

    # --------------------------------------------------------
    # Trafilatura
    # --------------------------------------------------------

    content = extract_trafilatura(
        html_content
    )

    if content:

        result[
            "content"
        ] = content

        result[
            "extraction_method"
        ] = "TRAFILATURA"

        result[
            "extraction_status"
        ] = "SUCCESS"

        return result

    # --------------------------------------------------------
    # Nettoyage
    # --------------------------------------------------------

    for tag in soup.find_all(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "footer",
            "header",
            "form",
        ]
    ):
        tag.decompose()

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    content = extract_html_article(
        soup
    )

    if content:

        result[
            "content"
        ] = content

        result[
            "extraction_method"
        ] = "HTML"

        result[
            "extraction_status"
        ] = "SUCCESS"

        return result

    # --------------------------------------------------------
    # Summary fallback
    # --------------------------------------------------------

    if result["summary"]:

        result[
            "extraction_method"
        ] = "META_DESCRIPTION"

        result[
            "extraction_status"
        ] = "SUMMARY_ONLY"

        return result

    result[
        "extraction_error"
    ] = (
        "Aucun contenu article exploitable"
    )

    return result


# ============================================================
# TRAITEMENT
# ============================================================

def process_article(article):

    result = dict(article)

    original_url = clean_text(
        article.get(
            "url",
            ""
        )
    )

    result[
        "resolved_url"
    ] = ""

    result[
        "resolution_method"
    ] = ""

    result[
        "final_url"
    ] = ""

    result[
        "http_status"
    ] = ""

    result[
        "content"
    ] = ""

    result[
        "content_chars"
    ] = 0

    result[
        "content_words"
    ] = 0

    result[
        "extraction_method"
    ] = ""

    result[
        "extraction_status"
    ] = ""

    result[
        "extraction_error"
    ] = ""

    result[
        "enrichment_source"
    ] = "ORIGINAL_MEDIA_PAGE"

    # --------------------------------------------------------
    # Résolution
    # --------------------------------------------------------

    resolved_url, resolution_method = (
        resolve_google_news_url(
            original_url
        )
    )

    result[
        "resolved_url"
    ] = resolved_url

    result[
        "resolution_method"
    ] = resolution_method

    if not resolved_url:

        result[
            "extraction_status"
        ] = "UNRESOLVED"

        result[
            "extraction_error"
        ] = (
            "Impossible de résoudre "
            "l'URL Google News"
        )

        return result

    # --------------------------------------------------------
    # Extraction
    # --------------------------------------------------------

    extraction = extract_media_page(
        resolved_url
    )

    result[
        "final_url"
    ] = extraction[
        "final_url"
    ]

    result[
        "http_status"
    ] = extraction[
        "http_status"
    ]

    result[
        "content"
    ] = extraction[
        "content"
    ]

    result[
        "extraction_method"
    ] = extraction[
        "extraction_method"
    ]

    result[
        "extraction_status"
    ] = extraction[
        "extraction_status"
    ]

    result[
        "extraction_error"
    ] = extraction[
        "extraction_error"
    ]

    # --------------------------------------------------------
    # Résumé
    # --------------------------------------------------------

    original_summary = clean_text(
        article.get(
            "summary",
            ""
        )
    )

    extracted_summary = clean_text(
        extraction.get(
            "summary",
            ""
        )
    )

    if not original_summary and extracted_summary:

        result[
            "summary"
        ] = extracted_summary

    # --------------------------------------------------------
    # Statistiques contenu
    # --------------------------------------------------------

    result[
        "content_chars"
    ] = len(
        clean_text(
            result["content"]
        )
    )

    result[
        "content_words"
    ] = word_count(
        result["content"]
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("GOOGLE NEWS V5")
    print("RÉSOLUTION + EXTRACTION DES ARTICLES")
    print("=" * 70)
    print()

    if not INPUT_FILE.exists():

        print(
            "[ERREUR] Fichier introuvable :"
        )
        print(INPUT_FILE)
        return

    rows = read_csv(
        INPUT_FILE
    )

    print(
        f"Articles V2 : {len(rows)}"
    )

    print()

    results = []
    errors = []

    relevant_total = 0

    content_success = 0
    summary_only = 0
    failed = 0
    unresolved = 0

    methods = {}

    start = time.time()

    # ========================================================
    # ARTICLES
    # ========================================================

    for index, article in enumerate(
        rows,
        start=1
    ):

        title = clean_text(
            article.get(
                "title",
                ""
            )
        )

        relevant = clean_text(
            article.get(
                "relevant",
                ""
            )
        ).lower()

        print(
            f"[{index}/{len(rows)}] "
            f"{title[:90]}"
        )

        # ----------------------------------------------------
        # Non pertinent
        # ----------------------------------------------------

        if relevant not in {
            "true",
            "1",
            "yes",
            "oui"
        }:

            result = dict(article)

            result[
                "resolved_url"
            ] = ""

            result[
                "resolution_method"
            ] = ""

            result[
                "extraction_status"
            ] = "SKIPPED"

            result[
                "enrichment_source"
            ] = "NOT_RELEVANT"

            result[
                "content"
            ] = ""

            result[
                "content_chars"
            ] = 0

            result[
                "content_words"
            ] = 0

            results.append(
                result
            )

            print(
                "    -> SKIPPED"
            )

            continue

        relevant_total += 1

        # ----------------------------------------------------
        # Traitement
        # ----------------------------------------------------

        try:

            result = process_article(
                article
            )

            results.append(
                result
            )

            status = result[
                "extraction_status"
            ]

            method = result[
                "extraction_method"
            ]

            if status == "SUCCESS":

                content_success += 1

                methods[method] = (
                    methods.get(
                        method,
                        0
                    ) + 1
                )

                print(
                    f"    -> SUCCESS | "
                    f"{method} | "
                    f"{result['content_words']} mots"
                )

            elif status == "SUMMARY_ONLY":

                summary_only += 1

                methods[
                    "SUMMARY_ONLY"
                ] = (
                    methods.get(
                        "SUMMARY_ONLY",
                        0
                    ) + 1
                )

                print(
                    "    -> SUMMARY_ONLY"
                )

            elif status == "UNRESOLVED":

                unresolved += 1

                errors.append(
                    result
                )

                print(
                    "    -> UNRESOLVED"
                )

            else:

                failed += 1

                errors.append(
                    result
                )

                print(
                    "    -> FAILED | "
                    f"{result['extraction_error'][:150]}"
                )

        except Exception as exc:

            failed += 1

            result = dict(article)

            result[
                "resolved_url"
            ] = ""

            result[
                "resolution_method"
            ] = ""

            result[
                "extraction_status"
            ] = "ERROR"

            result[
                "extraction_method"
            ] = ""

            result[
                "extraction_error"
            ] = str(exc)

            result[
                "content"
            ] = ""

            result[
                "content_chars"
            ] = 0

            result[
                "content_words"
            ] = 0

            results.append(
                result
            )

            errors.append(
                result
            )

            print(
                "    -> ERROR | "
                f"{str(exc)[:150]}"
            )

        time.sleep(0.25)

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    write_csv(
        OUTPUT_FILE,
        results
    )

    write_csv(
        OUTPUT_ERRORS,
        errors
    )

    elapsed = time.time() - start

    # ========================================================
    # RAPPORT
    # ========================================================

    print()
    print("=" * 70)
    print("FIN DE GOOGLE NEWS V5")
    print("=" * 70)
    print()

    print("ARTICLES")
    print(
        f"Articles V2            : "
        f"{len(rows)}"
    )

    print(
        f"Articles pertinents    : "
        f"{relevant_total}"
    )

    print()

    print("RÉSOLUTION")

    print(
        f"URLs non résolues      : "
        f"{unresolved}"
    )

    print()

    print("EXTRACTION")

    print(
        f"Contenu complet        : "
        f"{content_success}"
    )

    print(
        f"Résumé seulement       : "
        f"{summary_only}"
    )

    print(
        f"Échecs                 : "
        f"{failed}"
    )

    print()

    print("TAUX")

    if relevant_total:

        content_rate = (
            content_success
            / relevant_total
        ) * 100

        usable_rate = (
            (
                content_success
                + summary_only
            )
            / relevant_total
        ) * 100

        print(
            f"Contenu complet        : "
            f"{content_rate:.2f}%"
        )

        print(
            f"Données exploitables  : "
            f"{usable_rate:.2f}%"
        )

    else:

        print(
            "Contenu complet        : N/A"
        )

    print()

    print("MÉTHODES")

    if methods:

        for method, count in sorted(
            methods.items(),
            key=lambda x: x[1],
            reverse=True
        ):

            print(
                f"{method:<25} : {count}"
            )

    else:

        print("Aucune")

    print()

    print("TEMPS")

    print(
        f"Durée totale           : "
        f"{elapsed:.1f} secondes"
    )

    if relevant_total:

        print(
            f"Temps moyen/article    : "
            f"{elapsed / relevant_total:.2f} secondes"
        )

    print()

    print("FICHIERS CRÉÉS")

    print(
        f"  {OUTPUT_FILE.name}"
    )

    print(
        f"  {OUTPUT_ERRORS.name}"
    )

    print()

    print("SQLITE")
    print(
        "AUCUNE MODIFICATION"
    )

    print()

    print("=" * 70)


if __name__ == "__main__":
    main()