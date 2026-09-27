# modules/google_news_enricher_v3.py

import html
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None


# ============================================================
# CONFIGURATION
# ============================================================

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
        "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
    "Connection": "keep-alive",
}


# ============================================================
# UTILITAIRES
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
    return len(
        clean_text(text).split()
    )


def is_usable_content(text):
    text = clean_text(text)

    if len(text) < MIN_CONTENT_CHARS:
        return False

    if word_count(text) < MIN_CONTENT_WORDS:
        return False

    return True


# ============================================================
# GOOGLE NEWS URL
# ============================================================

def is_google_news_url(url):
    try:
        hostname = urlparse(url).netloc.lower()

        return (
            "news.google.com" in hostname
            or hostname.endswith("google.com")
        )

    except Exception:
        return False


def resolve_google_news_url(url):
    """
    Essaie de résoudre l'URL Google News vers l'URL réelle
    du média.

    Plusieurs mécanismes sont utilisés sans supposer que
    Google News possède toujours une redirection HTTP simple.
    """

    if not url:
        return url

    # --------------------------------------------------------
    # 1. Requête HEAD
    # --------------------------------------------------------

    try:

        response = requests.head(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        final_url = response.url

        if (
            final_url
            and not is_google_news_url(final_url)
        ):
            return final_url

    except Exception:
        pass

    # --------------------------------------------------------
    # 2. Requête GET
    # --------------------------------------------------------

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        final_url = response.url

        if (
            final_url
            and not is_google_news_url(final_url)
        ):
            return final_url

    except Exception:
        pass

    return url


# ============================================================
# EXTRACTION META
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

        if tag:

            content = clean_text(
                tag.get("content", "")
            )

            if content:
                return content

    return ""


# ============================================================
# EXTRACTION JSON-LD
# ============================================================

def extract_jsonld_article(soup):

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        raw = script.string

        if not raw:
            continue

        try:

            import json

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

            if article_body:

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

def extract_with_trafilatura(html_content):

    if not trafilatura:
        return ""

    try:

        extracted = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=False,
            include_links=False,
            favor_precision=True,
            favor_recall=False,
        )

        extracted = clean_text(
            extracted
        )

        if is_usable_content(
            extracted
        ):
            return extracted

    except Exception:
        pass

    return ""


# ============================================================
# HTML FALLBACK
# ============================================================

def extract_from_html(soup):

    # --------------------------------------------------------
    # 1. <article>
    # --------------------------------------------------------

    article = soup.find(
        "article"
    )

    if article:

        paragraphs = article.find_all(
            "p"
        )

        text = " ".join(
            clean_text(
                p.get_text(" ", strip=True)
            )
            for p in paragraphs
        )

        text = clean_text(
            text
        )

        if is_usable_content(
            text
        ):
            return text

    # --------------------------------------------------------
    # 2. Paragraphes principaux
    # --------------------------------------------------------

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
# EXTRACTION PAGE
# ============================================================

def extract_article_page(url):

    result = {
        "original_url": url,
        "resolved_url": "",
        "content": "",
        "summary": "",
        "extraction_method": "",
        "extraction_status": "FAILED",
        "extraction_error": "",
    }

    if not url:

        result["extraction_error"] = (
            "URL vide"
        )

        return result

    # --------------------------------------------------------
    # Résolution URL
    # --------------------------------------------------------

    resolved_url = resolve_google_news_url(
        url
    )

    result[
        "resolved_url"
    ] = resolved_url

    if is_google_news_url(
        resolved_url
    ):

        result[
            "extraction_error"
        ] = (
            "URL Google News non résolue"
        )

        return result

    # --------------------------------------------------------
    # GET page
    # --------------------------------------------------------

    try:

        response = requests.get(
            resolved_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        response.raise_for_status()

    except Exception as exc:

        result[
            "extraction_error"
        ] = str(exc)

        return result

    html_content = response.text

    if not html_content:

        result[
            "extraction_error"
        ] = (
            "HTML vide"
        )

        return result

    # --------------------------------------------------------
    # BeautifulSoup
    # --------------------------------------------------------

    soup = BeautifulSoup(
        html_content,
        "html.parser"
    )

    # Supprimer les éléments inutiles

    for tag in soup(
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
    # META DESCRIPTION
    # --------------------------------------------------------

    meta_description = (
        extract_meta_description(
            soup
        )
    )

    result[
        "summary"
    ] = meta_description

    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    jsonld_content = (
        extract_jsonld_article(
            soup
        )
    )

    if jsonld_content:

        result[
            "content"
        ] = jsonld_content

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

    trafilatura_content = (
        extract_with_trafilatura(
            html_content
        )
    )

    if trafilatura_content:

        result[
            "content"
        ] = trafilatura_content

        result[
            "extraction_method"
        ] = "TRAFILATURA"

        result[
            "extraction_status"
        ] = "SUCCESS"

        return result

    # --------------------------------------------------------
    # HTML FALLBACK
    # --------------------------------------------------------

    html_content_extracted = (
        extract_from_html(
            soup
        )
    )

    if html_content_extracted:

        result[
            "content"
        ] = html_content_extracted

        result[
            "extraction_method"
        ] = "HTML"

        result[
            "extraction_status"
        ] = "SUCCESS"

        return result

    # --------------------------------------------------------
    # SUMMARY FALLBACK
    # --------------------------------------------------------

    if meta_description:

        result[
            "extraction_status"
        ] = "SUMMARY_ONLY"

        result[
            "extraction_method"
        ] = "META_DESCRIPTION"

        return result

    result[
        "extraction_error"
    ] = (
        "Aucun contenu exploitable"
    )

    return result


# ============================================================
# ENRICHISSEMENT D'UN ARTICLE
# ============================================================

def enrich_article(article):

    result = dict(article)

    url = (
        article.get("url", "")
        or article.get("link", "")
    )

    extraction = extract_article_page(
        url
    )

    result[
        "original_url"
    ] = extraction[
        "original_url"
    ]

    result[
        "resolved_url"
    ] = extraction[
        "resolved_url"
    ]

    result[
        "content"
    ] = extraction[
        "content"
    ]

    # Garder le résumé RSS s'il existe.
    # Sinon utiliser le meta description.

    existing_summary = clean_text(
        article.get("summary", "")
    )

    extracted_summary = clean_text(
        extraction.get("summary", "")
    )

    if existing_summary:

        result[
            "summary"
        ] = existing_summary

    elif extracted_summary:

        result[
            "summary"
        ] = extracted_summary

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

    result[
        "enrichment_source"
    ] = "ORIGINAL_ARTICLE_PAGE"

    return result