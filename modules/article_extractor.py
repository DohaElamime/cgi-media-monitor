# ============================================================
# CGI MEDIA MONITOR
# ARTICLE EXTRACTOR V9 - COOKIE PRIVACY FIX
# ============================================================
#
# OBJECTIF
# --------
# Extraire proprement le contenu des articles CGI Maroc.
#
# PIPELINE
# --------
#
# Google News URL
#       ↓
# Google News Decoder
#       ↓
# URL originale
#       ↓
# HTTP download
#       ↓
# JSON-LD
#       ↓
# Trafilatura
#       ↓
# BeautifulSoup
#       ↓
# Meta description
#       ↓
# Summary fallback
#
# IMPORTANT
# ---------
# - Aucun accès SQLite
# - Aucun sentiment
# - Aucun classement par mots-clés
# - Aucun contenu inventé
# - Le résumé peut servir de fallback
# - extract_article() retourne un DICT
# ============================================================


from __future__ import annotations


# ============================================================
# IMPORTS
# ============================================================

import json
import re
import time

from typing import Any, Dict, Optional


import requests

from bs4 import BeautifulSoup


# ============================================================
# OPTIONAL DEPENDENCIES
# ============================================================

try:

    import trafilatura

    TRAFILATURA_AVAILABLE = True

except ImportError:

    trafilatura = None

    TRAFILATURA_AVAILABLE = False


try:

    import pymupdf

    PDF_AVAILABLE = True

except ImportError:

    pymupdf = None

    PDF_AVAILABLE = False


try:

    from googlenewsdecoder import gnewsdecoder

    GOOGLE_NEWS_DECODER_AVAILABLE = True

except ImportError:

    gnewsdecoder = None

    GOOGLE_NEWS_DECODER_AVAILABLE = False


# ============================================================
# CONFIGURATION
# ============================================================

DOWNLOAD_TIMEOUT = 15

MAX_ARTICLE_CHARS = 120_000

MIN_ARTICLE_CHARS = 250

MIN_ARTICLE_WORDS = 45

MIN_SUMMARY_CHARS = 80

MIN_SUMMARY_WORDS = 12


HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 "
        "Safari/537.36"
    ),

    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,"
        "image/webp,"
        "*/*;q=0.8"
    ),

    "Accept-Language": (
        "fr-FR,fr;q=0.9,"
        "en-US;q=0.8,"
        "en;q=0.7"
    ),

    "Connection": "keep-alive",

}


# ============================================================
# GOOGLE NEWS GENERIC SUMMARY
# ============================================================

GOOGLE_NEWS_GENERIC_SUMMARY = (
    "les informations complètes et à jour sont compilées "
    "par google actualités"
)


# ============================================================
# COOKIE / PRIVACY CONTENT DETECTION
# ============================================================

COOKIE_PRIVACY_PATTERNS = [
    "nous utilisons des cookies",
    "nous utilisons les cookies",
    "vos préférences des cookies",
    "préférences des cookies",
    "politique de confidentialité",
    "politique de vie privée",
    "politique de vie privee",
    "mémoire locale",
    "memoire locale",
    "accepter ou refuser",
    "accepter les cookies",
    "refuser les cookies",
    "contenu personnalisé",
    "contenu personnalise",
    "cookies permettant d'afficher",
    "cookies nécessaires",
    "cookies necessaires",
    "consentement",
    "privacy policy",
    "cookie policy",
    "cookie preferences",
]

def cookie_privacy_match_count(text: str) -> int:
    normalized = clean_text(text).lower()
    return sum(1 for p in COOKIE_PRIVACY_PATTERNS if p in normalized)

def is_cookie_privacy_content(text: str) -> bool:
    normalized = clean_text(text).lower()
    if not normalized:
        return False

    matches = cookie_privacy_match_count(normalized)

    if matches >= 2:
        return True

    if (
        "cookies" in normalized
        and ("préférences" in normalized or "preferences" in normalized)
        and (
            "mémoire locale" in normalized
            or "memoire locale" in normalized
            or "navigateur" in normalized
        )
    ):
        return True

    return False


# ============================================================
# URL HELPERS
# ============================================================

def clean_text(value: Any) -> str:

    """
    Nettoyage général du texte.
    """

    if value is None:

        return ""

    text = str(value)

    text = text.replace("\xa0", " ")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def word_count(text: str) -> int:

    """
    Nombre approximatif de mots.
    """

    text = clean_text(text)

    if not text:

        return 0

    return len(
        text.split()
    )


def is_google_news_url(url: str) -> bool:

    """
    Vérifie si l'URL appartient à Google News.
    """

    url = clean_text(url).lower()

    if not url:

        return False

    return (
        "news.google.com" in url
        or
        "google.com/rss/articles/" in url
    )


def is_valid_http_url(url: str) -> bool:

    """
    Vérifie une URL HTTP/HTTPS basique.
    """

    url = clean_text(url)

    if not url:

        return False

    return bool(
        re.match(
            r"^https?://",
            url,
            flags=re.IGNORECASE,
        )
    )


def is_valid_article_url(url: str) -> bool:

    """
    Vérifie qu'une URL semble correspondre
    à une page web exploitable.
    """

    url = clean_text(url)

    if not is_valid_http_url(url):

        return False

    lowered = url.lower()

    blocked_domains = [

        "facebook.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "youtu.be",
        "linkedin.com",
        "tiktok.com",

    ]

    for domain in blocked_domains:

        if domain in lowered:

            return False

    return True


# ============================================================
# SUMMARY VALIDATION
# ============================================================

def is_generic_google_news_summary(
    summary: str,
) -> bool:

    """
    Détecte le texte générique Google News.
    """

    summary = clean_text(
        summary
    ).lower()

    if not summary:

        return False

    summary = (
        summary
        .replace("’", "'")
        .strip()
    )

    generic = (
        GOOGLE_NEWS_GENERIC_SUMMARY
        .lower()
        .replace("’", "'")
        .strip()
    )

    if summary == generic:

        return True

    # Variante légèrement différente
    if (
        "informations complètes et à jour"
        in summary
        and
        "compilées par google actualités"
        in summary
    ):

        return True

    return False


def is_usable_summary(
    summary: str,
) -> bool:

    """
    Un résumé utilisable doit être :

    - non vide
    - non générique Google News
    - suffisamment long
    - suffisamment riche en mots
    """

    summary = clean_text(
        summary
    )

    if not summary:

        return False

    if is_generic_google_news_summary(
        summary
    ):

        return False

    if is_cookie_privacy_content(summary):

        return False

    if len(summary) < MIN_SUMMARY_CHARS:

        return False

    if word_count(summary) < MIN_SUMMARY_WORDS:

        return False

    return True


# ============================================================
# ARTICLE TEXT VALIDATION
# ============================================================

def is_probably_article(
    text: str,
) -> bool:

    """
    Vérifie si un texte possède suffisamment
    de contenu pour être considéré comme article.
    """

    text = clean_text(
        text
    )

    if not text:

        return False

    if is_cookie_privacy_content(text):

        return False

    if len(text) < MIN_ARTICLE_CHARS:

        return False

    if word_count(text) < MIN_ARTICLE_WORDS:

        return False

    return True


# ============================================================
# BLOCKED PAGE DETECTION
# ============================================================

def is_blocked(
    response: requests.Response,
) -> bool:

    """
    Détecte les blocages évidents.

    Certains sites retournent HTTP 200 tout en
    affichant une page de protection.
    """

    if response is None:

        return True

    status = response.status_code

    if status in {
        401,
        403,
        429,
        451,
        503,
    }:

        return True

    html = (
        response.text
        or ""
    ).lower()

    if not html:

        return True

    blocked_patterns = [

        "access denied",

        "403 forbidden",

        "captcha",

        "verify you are human",

        "verify that you are human",

        "cloudflare",

        "checking your browser",

        "enable javascript and cookies",

        "attention required",

        "bot detection",

        "security check",

        "too many requests",

    ]

    # On ne rejette pas automatiquement
    # une page uniquement parce qu'elle contient
    # "cloudflare" dans un script.
    #
    # On cherche plutôt des indicateurs visibles.

    visible_text = BeautifulSoup(
        html,
        "html.parser",
    ).get_text(
        " ",
        strip=True,
    ).lower()

    for pattern in blocked_patterns:

        if pattern in visible_text:

            return True

    return False


# ============================================================
# GOOGLE NEWS DECODER
# ============================================================

def decode_google_news(
    url: str,
) -> str:

    """
    Transforme une URL Google News
    en URL de l'article original.
    """

    url = clean_text(url)

    if not is_google_news_url(url):

        return url

    if not GOOGLE_NEWS_DECODER_AVAILABLE:

        return ""

    try:

        result = gnewsdecoder(
            url,
            interval=1,
        )

        if not result:

            return ""

        if isinstance(
            result,
            dict,
        ):

            decoded = (
                result.get(
                    "decoded_url"
                )
                or
                result.get(
                    "url"
                )
                or
                ""
            )

        else:

            decoded = str(
                result
            )

        decoded = clean_text(
            decoded
        )

        if is_valid_http_url(
            decoded
        ):

            return decoded

    except Exception:

        pass

    return ""


# ============================================================
# GOOGLE NEWS RSS SUMMARY
# ============================================================

def extract_google_news_summary(
    url: str,
) -> str:

    """
    Tente de récupérer un résumé depuis
    la page Google News.

    Ce résumé est uniquement un fallback.
    """

    if not is_google_news_url(url):

        return ""

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=DOWNLOAD_TIMEOUT,
            allow_redirects=True,
        )

        if response.status_code >= 400:

            return ""

        html = (
            response.text
            or ""
        )

        if not html:

            return ""

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        # ----------------------------------------------------
        # RSS item
        # ----------------------------------------------------

        item = soup.find(
            "item"
        )

        if item:

            # description
            description = item.find(
                "description"
            )

            if description:

                value = clean_text(
                    description.get_text(
                        " ",
                        strip=True,
                    )
                )

                if is_usable_summary(
                    value
                ):

                    return value

            # content:encoded
            encoded = item.find(
                lambda tag:
                getattr(
                    tag,
                    "name",
                    "",
                )
                == "content:encoded"
            )

            if encoded:

                value = clean_text(
                    encoded.get_text(
                        " ",
                        strip=True,
                    )
                )

                if is_usable_summary(
                    value
                ):

                    return value

        # ----------------------------------------------------
        # meta description
        # ----------------------------------------------------

        meta = soup.find(
            "meta",
            attrs={
                "name": "description",
            },
        )

        if meta:

            value = clean_text(
                meta.get(
                    "content",
                    "",
                )
            )

            if is_usable_summary(
                value
            ):

                return value

        # ----------------------------------------------------
        # og:description
        # ----------------------------------------------------

        meta = soup.find(
            "meta",
            attrs={
                "property": "og:description",
            },
        )

        if meta:

            value = clean_text(
                meta.get(
                    "content",
                    "",
                )
            )

            if is_usable_summary(
                value
            ):

                return value

    except Exception:

        pass

    return ""


# ============================================================
# JSON-LD
# ============================================================

def _json_ld_objects(
    soup: BeautifulSoup,
) -> list:

    """
    Récupère les objets JSON-LD.
    """

    objects = []

    for script in soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json"
        },
    ):

        raw = script.string

        if not raw:

            raw = script.get_text(
                strip=True
            )

        if not raw:

            continue

        try:

            data = json.loads(
                raw
            )

        except Exception:

            continue

        if isinstance(
            data,
            list,
        ):

            objects.extend(
                data
            )

        else:

            objects.append(
                data
            )

    return objects


def extract_json_ld_article(
    html: str,
) -> str:

    """
    Extrait articleBody depuis JSON-LD.
    """

    if not html:

        return ""

    try:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        objects = _json_ld_objects(
            soup
        )

        candidates = []

        for obj in objects:

            if not isinstance(
                obj,
                dict,
            ):

                continue

            article_body = obj.get(
                "articleBody"
            )

            if isinstance(
                article_body,
                str,
            ):

                text = clean_text(
                    article_body
                )

                if is_probably_article(
                    text
                ):

                    candidates.append(
                        text
                    )

            # @graph
            graph = obj.get(
                "@graph"
            )

            if isinstance(
                graph,
                list,
            ):

                for node in graph:

                    if not isinstance(
                        node,
                        dict,
                    ):

                        continue

                    article_body = node.get(
                        "articleBody"
                    )

                    if isinstance(
                        article_body,
                        str,
                    ):

                        text = clean_text(
                            article_body
                        )

                        if is_probably_article(
                            text
                        ):

                            candidates.append(
                                text
                            )

        if candidates:

            candidates.sort(
                key=len,
                reverse=True,
            )

            return candidates[0][
                :MAX_ARTICLE_CHARS
            ]

    except Exception:

        pass

    return ""


# ============================================================
# TRAFILATURA
# ============================================================

def extract_with_trafilatura(
    html: str,
) -> str:

    """
    Extraction principale avec Trafilatura.
    """

    if not html:

        return ""

    if not TRAFILATURA_AVAILABLE:

        return ""

    # --------------------------------------------------------
    # Tentative 1 : précision
    # --------------------------------------------------------

    try:

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            include_links=False,
            favor_precision=True,
            deduplicate=True,
        )

        text = clean_text(
            text
        )

        if is_probably_article(
            text
        ):

            return text[
                :MAX_ARTICLE_CHARS
            ]

    except Exception:

        pass

    # --------------------------------------------------------
    # Tentative 2 : rappel
    # --------------------------------------------------------

    try:

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            include_links=False,
            favor_precision=False,
            deduplicate=True,
        )

        text = clean_text(
            text
        )

        if is_probably_article(
            text
        ):

            return text[
                :MAX_ARTICLE_CHARS
            ]

    except Exception:

        pass

    return ""


# ============================================================
# BEAUTIFULSOUP
# ============================================================

def extract_with_bs4(
    html: str,
) -> str:

    """
    Fallback BeautifulSoup.

    On privilégie les zones correspondant
    à un article avant d'utiliser main.
    """

    if not html:

        return ""

    try:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        # ----------------------------------------------------
        # Supprimer éléments inutiles
        # ----------------------------------------------------

        for tag in soup([
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "header",
            "footer",
            "form",
            "aside",
        ]):

            tag.decompose()

        # ----------------------------------------------------
        # Sélecteurs prioritaires
        # ----------------------------------------------------

        selectors = [

            "article",

            "[itemprop='articleBody']",

            ".article-content",

            ".article-body",

            ".article__content",

            ".article-content-body",

            ".post-content",

            ".post-body",

            ".entry-content",

            ".content-article",

            ".single-content",

            ".story-content",

        ]

        candidates = []

        for selector in selectors:

            for element in soup.select(
                selector
            ):

                text = clean_text(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )

                if is_probably_article(
                    text
                ):

                    candidates.append(
                        text
                    )

        if candidates:

            candidates.sort(
                key=len,
                reverse=True,
            )

            return candidates[0][
                :MAX_ARTICLE_CHARS
            ]

        # ----------------------------------------------------
        # main comme fallback
        # ----------------------------------------------------

        for element in soup.select(
            "main"
        ):

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if is_probably_article(
                text
            ):

                return text[
                    :MAX_ARTICLE_CHARS
                ]

        # ----------------------------------------------------
        # Dernier recours contrôlé
        # ----------------------------------------------------

        body = soup.find(
            "body"
        )

        if body:

            text = clean_text(
                body.get_text(
                    " ",
                    strip=True,
                )
            )

            # On accepte body uniquement
            # s'il est suffisamment substantiel.

            if (
                len(text)
                >= MIN_ARTICLE_CHARS * 3
                and
                word_count(text)
                >= MIN_ARTICLE_WORDS * 3
            ):

                return text[
                    :MAX_ARTICLE_CHARS
                ]

    except Exception:

        pass

    return ""


# ============================================================
# META DESCRIPTION
# ============================================================

def extract_meta_description(
    html: str,
) -> str:

    """
    Extrait une description meta utilisable.
    """

    if not html:

        return ""

    try:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        selectors = [

            (
                "name",
                "description",
            ),

            (
                "property",
                "og:description",
            ),

            (
                "name",
                "twitter:description",
            ),

        ]

        for attr, value in selectors:

            tag = soup.find(
                "meta",
                attrs={
                    attr: value,
                },
            )

            if not tag:

                continue

            content = clean_text(
                tag.get(
                    "content",
                    "",
                )
            )

            if is_usable_summary(
                content
            ):

                return content

    except Exception:

        pass

    return ""


# ============================================================
# PDF
# ============================================================

def extract_pdf(
    data: bytes,
) -> str:

    """
    Extraction PDF.
    """

    if not PDF_AVAILABLE:

        return ""

    if not data:

        return ""

    try:

        document = pymupdf.open(
            stream=data,
            filetype="pdf",
        )

        pages = []

        for page in document:

            text = page.get_text(
                "text"
            )

            if text:

                pages.append(
                    text
                )

        document.close()

        content = clean_text(
            "\n".join(
                pages
            )
        )

        if is_probably_article(
            content
        ):

            return content[
                :MAX_ARTICLE_CHARS
            ]

    except Exception:

        pass

    return ""


# ============================================================
# HTTP REQUEST
# ============================================================

def _request(
    url: str,
) -> Optional[requests.Response]:

    """
    Téléchargement HTTP avec retry léger.
    """

    if not url:

        return None

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    for attempt in range(2):

        try:

            response = session.get(
                url,
                timeout=DOWNLOAD_TIMEOUT,
                allow_redirects=True,
            )

            return response

        except requests.RequestException:

            if attempt == 0:

                time.sleep(1)

    return None


# ============================================================
# DOWNLOAD RESULT
# ============================================================

def download_url(
    url: str,
) -> Dict[str, Any]:

    """
    Télécharge une URL et retourne
    toutes les informations nécessaires.
    """

    result = {

        "success": False,

        "html": "",

        "data": b"",

        "final_url": url,

        "status_code": 0,

        "content_type": "",

        "error": "",

        "blocked": False,

    }

    response = _request(
        url
    )

    if response is None:

        result["error"] = (
            "Échec de la requête HTTP"
        )

        return result

    result["final_url"] = (
        clean_text(
            response.url
        )
        or
        url
    )

    result["status_code"] = (
        response.status_code
    )

    result["content_type"] = (
        response.headers.get(
            "Content-Type",
            "",
        )
    )

    result["data"] = (
        response.content
        or
        b""
    )

    # --------------------------------------------------------
    # Blocage
    # --------------------------------------------------------

    if is_blocked(
        response
    ):

        result["blocked"] = True

        result["error"] = (
            f"Page bloquée "
            f"(HTTP {response.status_code})"
        )

        return result

    # --------------------------------------------------------
    # HTTP error
    # --------------------------------------------------------

    if response.status_code >= 400:

        result["error"] = (
            f"HTTP {response.status_code}"
        )

        return result

    # --------------------------------------------------------
    # Content
    # --------------------------------------------------------

    result["html"] = (
        response.text
        or
        ""
    )

    if not result["html"]:

        result["error"] = (
            "Réponse HTML vide"
        )

        return result

    result["success"] = True

    return result


# ============================================================
# MAIN EXTRACTION
# ============================================================

def extract_article(
    url: str,
    title: str = "",
    summary: str = "",
) -> Dict[str, Any]:

    """
    Extraction complète.

    Retour :

    {
        "url": ...,
        "final_url": ...,
        "title": ...,
        "summary": ...,
        "content": ...,
        "content_length": ...,
        "extraction_failed": ...,
        "content_mismatch": ...,
        "review": ...,
        "error": ...,
        "method": ...
    }

    IMPORTANT :
    - aucun accès SQLite
    - aucune classification sentiment
    - aucun contenu inventé
    """

    start_time = time.time()

    # --------------------------------------------------------
    # Nettoyage entrée
    # --------------------------------------------------------

    original_url = clean_text(
        url
    )

    title = clean_text(
        title
    )

    provided_summary = clean_text(
        summary
    )

    # --------------------------------------------------------
    # Résumé fourni
    # --------------------------------------------------------

    usable_summary = ""

    if is_usable_summary(
        provided_summary
    ):

        usable_summary = (
            provided_summary
        )

    # --------------------------------------------------------
    # Résultat standard
    # --------------------------------------------------------

    result = {

        "url": original_url,

        "final_url": original_url,

        "title": title,

        "summary": usable_summary,

        "content": "",

        "content_length": 0,

        "extraction_failed": False,

        "content_mismatch": False,

        "review": False,

        "error": "",

        "error_type": "",

        "method": "",

        "elapsed_seconds": 0.0,

    }

    # ========================================================
    # URL VIDE
    # ========================================================

    if not original_url:

        result["extraction_failed"] = True

        result["review"] = True

        result["error"] = (
            "URL vide"
        )

        result["elapsed_seconds"] = round(
            time.time() - start_time,
            3,
        )

        return result

    # ========================================================
    # GOOGLE NEWS
    # ========================================================

    target_url = original_url

    if is_google_news_url(
        original_url
    ):

        # ----------------------------------------------------
        # Summary Google News fallback
        # ----------------------------------------------------

        if not usable_summary:

            google_summary = (
                extract_google_news_summary(
                    original_url
                )
            )

            if is_usable_summary(
                google_summary
            ):

                usable_summary = (
                    google_summary
                )

                result["summary"] = (
                    usable_summary
                )

        # ----------------------------------------------------
        # Décodage
        # ----------------------------------------------------

        decoded_url = (
            decode_google_news(
                original_url
            )
        )

        if decoded_url:

            target_url = decoded_url

            result["final_url"] = (
                decoded_url
            )

        else:

            # Google News non décodable.
            #
            # Si un résumé réel existe,
            # on peut quand même continuer
            # avec summary_only.

            if usable_summary:

                result["content"] = ""

                result["content_length"] = 0

                result["extraction_failed"] = False

                result["review"] = False

                result["method"] = (
                    "summary_only_google_news"
                )

                result["elapsed_seconds"] = round(
                    time.time() - start_time,
                    3,
                )

                return result

            result["extraction_failed"] = True

            result["review"] = True

            result["error"] = (
                "URL Google News non décodable "
                "et aucun résumé utilisable"
            )

            result["elapsed_seconds"] = round(
                time.time() - start_time,
                3,
            )

            return result

    # ========================================================
    # VALIDATION URL
    # ========================================================

    if not is_valid_article_url(
        target_url
    ):

        # Résumé fallback
        if usable_summary:

            result["final_url"] = (
                target_url
            )

            result["content"] = ""

            result["content_length"] = 0

            result["extraction_failed"] = False

            result["review"] = True

            result["method"] = (
                "summary_only_invalid_url"
            )

            result["error"] = (
                "URL non exploitable "
                "mais résumé conservé"
            )

            result["elapsed_seconds"] = round(
                time.time() - start_time,
                3,
            )

            return result

        result["extraction_failed"] = True

        result["review"] = True

        result["error"] = (
            "URL non valide"
        )

        result["elapsed_seconds"] = round(
            time.time() - start_time,
            3,
        )

        return result

    # ========================================================
    # DOWNLOAD
    # ========================================================

    downloaded = download_url(
        target_url
    )

    final_url = clean_text(
        downloaded.get(
            "final_url",
            target_url,
        )
    )

    result["final_url"] = (
        final_url
        or
        target_url
    )

    # ========================================================
    # DOWNLOAD FAILURE
    # ========================================================

    if not downloaded.get(
        "success",
        False,
    ):

        # ----------------------------------------------------
        # Résumé disponible
        # ----------------------------------------------------

        if usable_summary:

            result["content"] = ""

            result["content_length"] = 0

            result["extraction_failed"] = False

            result["review"] = False

            result["method"] = (
                "summary_only"
            )

            result["error"] = (
                downloaded.get(
                    "error",
                    "",
                )
            )

            result["elapsed_seconds"] = round(
                time.time() - start_time,
                3,
            )

            return result

        # ----------------------------------------------------
        # Aucun fallback
        # ----------------------------------------------------

        result["extraction_failed"] = True

        result["review"] = True

        result["error"] = (
            downloaded.get(
                "error",
                "Échec téléchargement",
            )
        )

        result["elapsed_seconds"] = round(
            time.time() - start_time,
            3,
        )

        return result

    # ========================================================
    # HTML / PDF
    # ========================================================

    html = downloaded.get(
        "html",
        "",
    )

    data = downloaded.get(
        "data",
        b"",
    )

    content_type = clean_text(
        downloaded.get(
            "content_type",
            "",
        )
    ).lower()

    content = ""

    method = ""

    # ========================================================
    # PDF
    # ========================================================

    if (
        "application/pdf"
        in content_type
    ):

        content = extract_pdf(
            data
        )

        if content:

            method = "pdf"

    # ========================================================
    # HTML
    # ========================================================

    elif html:

        # ----------------------------------------------------
        # 1. JSON-LD
        # ----------------------------------------------------

        content = extract_json_ld_article(
            html
        )

        if content:

            method = "json_ld"

        # ----------------------------------------------------
        # 2. Trafilatura
        # ----------------------------------------------------

        if not content:

            content = extract_with_trafilatura(
                html
            )

            if content:

                method = "trafilatura"

        # ----------------------------------------------------
        # 3. BeautifulSoup
        # ----------------------------------------------------

        if not content:

            content = extract_with_bs4(
                html
            )

            if content:

                method = "beautifulsoup"

    # ========================================================
    # VALIDATION CONTENT
    # ========================================================

    content = clean_text(
        content
    )

    if is_probably_article(
        content
    ):

        # ----------------------------------------------------
        # Limite
        # ----------------------------------------------------

        content = content[
            :MAX_ARTICLE_CHARS
        ]

        result["content"] = (
            content
        )

        result["content_length"] = (
            len(content)
        )

        result["extraction_failed"] = False

        result["review"] = False

        result["method"] = (
            method
            or
            "unknown"
        )

        result["elapsed_seconds"] = round(
            time.time() - start_time,
            3,
        )

        return result

    # ========================================================
    # COOKIE / PRIVACY GUARD
    # ========================================================

    if content and is_cookie_privacy_content(content):

        result["content"] = ""
        result["content_length"] = 0
        result["extraction_failed"] = True
        result["review"] = True
        result["summary"] = ""
        result["error"] = (
            "Contenu extrait correspondant à une bannière "
            "cookies/privacy"
        )
        result["error_type"] = "cookie_banner"
        result["method"] = ""

        result["elapsed_seconds"] = round(
            time.time() - start_time,
            3,
        )

        return result

    # ========================================================
    # META DESCRIPTION FALLBACK
    # ========================================================

    if html and not usable_summary:

        meta_summary = (
            extract_meta_description(
                html
            )
        )

        if is_usable_summary(
            meta_summary
        ):

            usable_summary = (
                meta_summary
            )

            result["summary"] = (
                usable_summary
            )

    # ========================================================
    # SUMMARY ONLY
    # ========================================================

    if usable_summary:

        if is_cookie_privacy_content(usable_summary):
            result["content"] = ""
            result["content_length"] = 0
            result["extraction_failed"] = True
            result["review"] = True
            result["summary"] = ""
            result["error"] = (
                "Résumé rejeté : bannière cookies/privacy"
            )
            result["error_type"] = "cookie_banner"
            result["method"] = ""

            result["elapsed_seconds"] = round(
                time.time() - start_time,
                3,
            )

            return result

        result["content"] = ""

        result["content_length"] = 0

        result["extraction_failed"] = False

        result["review"] = False

        result["method"] = (
            "summary_only"
        )

        result["elapsed_seconds"] = round(
            time.time() - start_time,
            3,
        )

        return result

    # ========================================================
    # NOTHING USABLE
    # ========================================================

    result["content"] = ""

    result["content_length"] = 0

    result["extraction_failed"] = True

    result["review"] = True

    result["error"] = (
        "Contenu vide et résumé inutilisable"
    )

    result["error_type"] = "no_usable_content"

    result["method"] = ""

    result["elapsed_seconds"] = round(
        time.time() - start_time,
        3,
    )

    return result


# ============================================================
# COMPATIBILITY
# ============================================================

def extract_article_text(
    url: str,
    title: str = "",
    summary: str = "",
) -> str:

    """
    Compatibilité avec l'ancien pipeline.

    Retourne uniquement le contenu intégral.
    """

    result = extract_article(
        url=url,
        title=title,
        summary=summary,
    )

    return result.get(
        "content",
        "",
    )


def extract_content(
    url: str,
    title: str = "",
    summary: str = "",
) -> str:

    """
    Alias de compatibilité.
    """

    return extract_article_text(
        url=url,
        title=title,
        summary=summary,
    )


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    TEST_URL = (
        "https://www.cgi.ma/fr/landing/les-cgi"
    )

    TEST_TITLE = (
        "La CGI"
    )

    TEST_SUMMARY = ""

    print()
    print("=" * 70)
    print("TEST ARTICLE EXTRACTOR V8")
    print("=" * 70)

    print()
    print(
        "Google News decoder : "
        f"{GOOGLE_NEWS_DECODER_AVAILABLE}"
    )

    print(
        "Trafilatura         : "
        f"{TRAFILATURA_AVAILABLE}"
    )

    print(
        "PyMuPDF             : "
        f"{PDF_AVAILABLE}"
    )

    print()
    print(
        "URL test :"
    )

    print(
        TEST_URL
    )

    print()
    print(
        "Extraction..."
    )

    result = extract_article(
        url=TEST_URL,
        title=TEST_TITLE,
        summary=TEST_SUMMARY,
    )

    print()
    print("-" * 70)

    print(
        f"Méthode           : "
        f"{result.get('method', '')}"
    )

    print(
        f"URL finale        : "
        f"{result.get('final_url', '')}"
    )

    print(
        f"Longueur contenu  : "
        f"{result.get('content_length', 0)}"
    )

    print(
        f"Mots contenu      : "
        f"{word_count(result.get('content', ''))}"
    )

    print(
        f"Résumé utilisable : "
        f"{is_usable_summary(result.get('summary', ''))}"
    )

    print(
        f"Extraction failed : "
        f"{result.get('extraction_failed')}"
    )

    print(
        f"Review            : "
        f"{result.get('review')}"
    )

    print(
        f"Mismatch          : "
        f"{result.get('content_mismatch')}"
    )

    print(
        f"Erreur            : "
        f"{result.get('error', '')}"
    )

    print(
        f"Temps             : "
        f"{result.get('elapsed_seconds', 0)} sec"
    )

    if result.get(
        "summary"
    ):

        print()
        print(
            "Résumé :"
        )

        print(
            result["summary"]
        )

    if result.get(
        "content"
    ):

        print()
        print(
            "Début du contenu :"
        )

        print(
            result["content"][:1000]
        )

    print()
    print("=" * 70)