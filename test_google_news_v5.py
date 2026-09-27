# test_google_news_v5.py

import csv
import html
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None

from modules.google_news_resolver_v4 import (
    resolve_google_news_url,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR / "google_news_v2_results.csv"
)

RESOLUTION_FILE = (
    BASE_DIR / "google_news_v4_resolution.csv"
)

OUTPUT_FILE = (
    BASE_DIR / "google_news_v5_results.csv"
)

OUTPUT_ERRORS = (
    BASE_DIR / "google_news_v5_errors.csv"
)

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
    "Accept-Language": (
        "fr-FR,fr;q=0.9,en;q=0.7"
    ),
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

        return list(
            csv.DictReader(f)
        )


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

    fieldnames = []

    for row in rows:

        for key in row.keys():

            if key not in fieldnames:
                fieldnames.append(key)

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# TEXTE
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = html.unescape(
        str(text)
    )

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

    return len(
        text.split()
    )


def is_usable_content(text):

    text = clean_text(text)

    if len(text) < MIN_CONTENT_CHARS:
        return False

    if word_count(text) < MIN_CONTENT_WORDS:
        return False

    return True


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

    import json

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(
                raw
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

def extract_trafilatura(
    html_content
):

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

        text = clean_text(
            text
        )

        if is_usable_content(
            text
        ):

            return text

    except Exception:
        pass

    return ""


# ============================================================
# HTML ARTICLE
# ============================================================

def extract_html_article(
    soup
):

    # --------------------------------------------------------
    # <article>
    # --------------------------------------------------------

    article = soup.find(
        "article"
    )

    if article:

        paragraphs = article.find_all(
            "p"
        )

        texts = []

        for paragraph in paragraphs:

            text = clean_text(
                paragraph.get_text(
                    " ",
                    strip=True
                )
            )

            if text:

                texts.append(
                    text
                )

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

    paragraphs = soup.find_all(
        "p"
    )

    texts = []

    for paragraph in paragraphs:

        text = clean_text(
            paragraph.get_text(
                " ",
                strip=True
            )
        )

        if word_count(text) >= 5:

            texts.append(
                text
            )

    combined = clean_text(
        " ".join(texts)
    )

    if is_usable_content(
        combined
    ):

        return combined

    return ""


# ============================================================
# PAGE MEDIA
# ============================================================

def extract_media_page(
    resolved_url
):

    result = {
        "resolved_url": resolved_url,
        "content": "",
        "summary": "",
        "extraction_method": "",
        "extraction_status": "FAILED",
        "extraction_error": "",
        "http_status": "",
        "final_url": "",
    }

    if not resolved_url:

        result[
            "extraction_error"
        ] = "URL résolue vide"

        return result

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    try:

        response = requests.get(
            resolved_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        result[
            "http_status"
        ] = response.status_code

        result[
            "final_url"
        ] = response.url

        response.raise_for_status()

    except Exception as exc:

        result[
            "extraction_error"
        ] = str(exc)

        return result

    if not response.text:

        result[
            "extraction_error"
        ] = "HTML vide"

        return result

    html_content = response.text

    # --------------------------------------------------------
    # BeautifulSoup
    # --------------------------------------------------------

    soup = BeautifulSoup(
        html_content,
        "html.parser"
    )

    # Meta AVANT suppression des balises
    result[
        "summary"
    ] = extract_meta_description(
        soup
    )

    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    jsonld = extract_jsonld(
        soup
    )

    if jsonld:

        result[
            "content"
        ] = jsonld

        result[
            "extraction_method"
        ] = "JSON_LD"

        result[
            "extraction_status"
        ] = "SUCCESS"

        return result

    # --------------------------------------------------------
    # TRAFILATURA
    # --------------------------------------------------------

    trafilatura_text = (
        extract_trafilatura(
            html_content
        )
    )

    if trafilatura_text:

        result[
            "content"
        ] = trafilatura_text

        result[
            "extraction_method"
        ] = "TRAFILATURA"

        result[
            "extraction_status"
        ] = "SUCCESS"

        return result

    # --------------------------------------------------------
    # Nettoyage HTML
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
    # ARTICLE HTML
    # --------------------------------------------------------

    html_article = (
        extract_html_article(
            soup
        )
    )

    if html_article:

        result[
            "content"
        ] = html_article

        result[
            "extraction_method"
        ] = "HTML"

        result[
            "extraction_status"
        ] = "SUCCESS"

        return result

    # --------------------------------------------------------
    # META DESCRIPTION
    # --------------------------------------------------------

    if result["summary"]:

        result[
            "extraction_method"
        ] = "META_DESCRIPTION"

        result[
            "extraction_status"
        ] = "SUMMARY_ONLY"

        return result

    # --------------------------------------------------------
    # ÉCHEC
    # --------------------------------------------------------

    result[
        "extraction_error"
    ] = (
        "Aucun contenu article exploitable"
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("GOOGLE NEWS V5 - EXTRACTION DES ARTICLES")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # Vérification fichiers
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        print(
            "[ERREUR] Fichier introuvable :"
        )

        print(
            INPUT_FILE
        )

        return

    if not RESOLUTION_FILE.exists():

        print(
            "[ERREUR] Fichier introuvable :"
        )

        print(
            RESOLUTION_FILE
        )

        return

    # --------------------------------------------------------
    # Lecture
    # --------------------------------------------------------

    original_rows = read_csv(
        INPUT_FILE
    )

    resolution_rows = read_csv(
        RESOLUTION_FILE
    )

    print(
        f"Articles V2       : "
        f"{len(original_rows)}"
    )

    print(
        f"Résolutions V4    : "
        f"{len(resolution_rows)}"
    )

    print()

    # --------------------------------------------------------
    # Index des résolutions
    # --------------------------------------------------------

    resolution_by_url = {}

    for row in resolution_rows:

        original_url = str(
            row.get(
                "original_url",
                ""
            )
        ).strip()

        if original_url:

            resolution_by_url[
                original_url
            ] = row

    # --------------------------------------------------------
    # Résultats
    # --------------------------------------------------------

    results = []
    errors = []

    relevant_total = 0

    content_success = 0
    summary_only = 0
    failed = 0
    unresolved = 0

    methods = {}

    start_time = time.time()

    # ========================================================
    # TRAITEMENT
    # ========================================================

    for index, article in enumerate(
        original_rows,
        start=1
    ):

        title = str(
            article.get(
                "title",
                ""
            )
        ).strip()

        original_url = str(
            article.get(
                "url",
                ""
            )
        ).strip()

        relevant = str(
            article.get(
                "relevant",
                ""
            )
        ).strip().lower()

        print(
            f"[{index}/{len(original_rows)}] "
            f"{title[:90]}"
        )

        # ----------------------------------------------------
        # NON PERTINENT
        # ----------------------------------------------------

        if relevant not in {
            "true",
            "1",
            "yes",
            "oui",
        }:

            result = dict(
                article
            )

            result[
                "resolved_url"
            ] = ""

            result[
                "enrichment_source"
            ] = "NOT_RELEVANT"

            result[
                "extraction_status"
            ] = "SKIPPED"

            result[
                "extraction_method"
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

            results.append(
                result
            )

            print(
                "    -> SKIPPED"
            )

            continue

        relevant_total += 1

        # ----------------------------------------------------
        # URL RÉSOLUE
        # ----------------------------------------------------

        resolution = (
            resolution_by_url.get(
                original_url
            )
        )

        if not resolution:

            # Sécurité : résoudre à nouveau
            resolved_url, method = (
                resolve_google_news_url(
                    original_url
                )
            )

        else:

            resolved_url = str(
                resolution.get(
                    "resolved_url",
                    ""
                )
            ).strip()

            method = str(
                resolution.get(
                    "resolution_method",
                    ""
                )
            ).strip()

        # ----------------------------------------------------
        # URL NON RÉSOLUE
        # ----------------------------------------------------

        if not resolved_url:

            unresolved += 1

            result = dict(
                article
            )

            result[
                "resolved_url"
            ] = ""

            result[
                "resolution_method"
            ] = method

            result[
                "enrichment_source"
            ] = "GOOGLE_NEWS"

            result[
                "extraction_status"
            ] = "UNRESOLVED"

            result[
                "extraction_error"
            ] = "URL média non résolue"

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
                "    -> URL NON RÉSOLUE"
            )

            continue

        # ----------------------------------------------------
        # EXTRACTION
        # ----------------------------------------------------

        try:

            extraction = (
                extract_media_page(
                    resolved_url
                )
            )

            result = dict(
                article
            )

            result[
                "resolved_url"
            ] = resolved_url

            result[
                "resolution_method"
            ] = method

            result[
                "enrichment_source"
            ] = "ORIGINAL_MEDIA_PAGE"

            result[
                "final_url"
            ] = extraction.get(
                "final_url",
                ""
            )

            result[
                "http_status"
            ] = extraction.get(
                "http_status",
                ""
            )

            result[
                "content"
            ] = extraction.get(
                "content",
                ""
            )

            # ------------------------------------------------
            # Résumé
            # ------------------------------------------------

            existing_summary = str(
                article.get(
                    "summary",
                    ""
                )
            ).strip()

            extracted_summary = str(
                extraction.get(
                    "summary",
                    ""
                )
            ).strip()

            if existing_summary:
                result[
                    "summary"
                ] = existing_summary

            elif extracted_summary:
                result[
                    "summary"
                ] = extracted_summary

            # ------------------------------------------------
            # Métadonnées extraction
            # ------------------------------------------------

            result[
                "extraction_method"
            ] = extraction.get(
                "extraction_method",
                ""
            )

            result[
                "extraction_status"
            ] = extraction.get(
                "extraction_status",
                "FAILED"
            )

            result[
                "extraction_error"
            ] = extraction.get(
                "extraction_error",
                ""
            )

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

            results.append(
                result
            )

            status = result[
                "extraction_status"
            ]

            extraction_method = result[
                "extraction_method"
            ]

            if status == "SUCCESS":

                content_success += 1

                methods[
                    extraction_method
                ] = (
                    methods.get(
                        extraction_method,
                        0
                    ) + 1
                )

                print(
                    f"    -> SUCCESS | "
                    f"{extraction_method} | "
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

            else:

                failed += 1

                errors.append(
                    result
                )

                print(
                    "    -> FAILED | "
                    f"{result['extraction_error'][:160]}"
                )

        except Exception as exc:

            failed += 1

            result = dict(
                article
            )

            result[
                "resolved_url"
            ] = resolved_url

            result[
                "resolution_method"
            ] = method

            result[
                "enrichment_source"
            ] = "ORIGINAL_MEDIA_PAGE"

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
                f"{str(exc)[:160]}"
            )

        # ----------------------------------------------------
        # Pause
        # ----------------------------------------------------

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

    elapsed = (
        time.time()
        - start_time
    )

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
        f"{len(original_rows)}"
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

    if relevant_total > 0:

        success_rate = (
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
            f"{success_rate:.2f}%"
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

    print("MÉTHODES D'EXTRACTION")

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

        print(
            "Aucune"
        )

    print()

    print("TEMPS")

    print(
        f"Durée totale           : "
        f"{elapsed:.1f} secondes"
    )

    if relevant_total > 0:

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