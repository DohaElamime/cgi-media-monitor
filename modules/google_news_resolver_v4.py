# modules/google_news_resolver_v4.py

import base64
import html
import re
import struct
from urllib.parse import urlparse, unquote

import requests


TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


# ============================================================
# UTILITAIRES
# ============================================================

def clean_url(url):

    if not url:
        return ""

    url = html.unescape(
        str(url).strip()
    )

    url = unquote(url)

    return url


def is_valid_external_url(url):

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
            parsed.netloc
            or ""
        ).lower()

        if not hostname:
            return False

        if (
            "news.google.com"
            in hostname
        ):
            return False

        if (
            "google.com"
            in hostname
            and hostname.endswith(
                ".google.com"
            )
        ):
            return False

        return True

    except Exception:

        return False


# ============================================================
# MÉTHODE 1
# Google News /articles/<token>
# ============================================================

def decode_google_news_token(url):

    """
    Décode les tokens Google News modernes
    lorsque le format permet d'extraire directement
    l'URL originale.
    """

    if not url:
        return None

    match = re.search(
        r"/rss/articles/([^?]+)",
        url
    )

    if not match:
        return None

    token = match.group(1)

    try:

        # Base64 URL-safe
        padded = token + (
            "="
            * (-len(token) % 4)
        )

        raw = base64.urlsafe_b64decode(
            padded
        )

        text = raw.decode(
            "utf-8",
            errors="ignore"
        )

        # Chercher directement une URL
        urls = re.findall(
            r"https?://[^\s\"'<>]+",
            text
        )

        for candidate in urls:

            candidate = clean_url(
                candidate
            )

            if is_valid_external_url(
                candidate
            ):
                return candidate

    except Exception:
        pass

    return None


# ============================================================
# MÉTHODE 2
# Extraction de chaînes ASCII du token
# ============================================================

def extract_urls_from_binary_token(url):

    match = re.search(
        r"/rss/articles/([^?]+)",
        url
    )

    if not match:
        return []

    token = match.group(1)

    try:

        padded = token + (
            "="
            * (-len(token) % 4)
        )

        raw = base64.urlsafe_b64decode(
            padded
        )

    except Exception:

        return []

    candidates = []

    # ASCII lisible
    ascii_parts = re.findall(
        rb"https?://[ -~]+",
        raw
    )

    for part in ascii_parts:

        try:
            candidate = part.decode(
                "utf-8",
                errors="ignore"
            )

        except Exception:
            continue

        candidate = clean_url(
            candidate
        )

        if is_valid_external_url(
            candidate
        ):
            candidates.append(
                candidate
            )

    # UTF-16 / structures binaires éventuelles
    for encoding in (
        "utf-16-le",
        "utf-16-be"
    ):

        try:

            text = raw.decode(
                encoding,
                errors="ignore"
            )

            urls = re.findall(
                r"https?://[^\s\"'<>]+",
                text
            )

            for candidate in urls:

                candidate = clean_url(
                    candidate
                )

                if is_valid_external_url(
                    candidate
                ):
                    candidates.append(
                        candidate
                    )

        except Exception:
            pass

    # déduplication
    unique = []

    for candidate in candidates:

        if candidate not in unique:
            unique.append(candidate)

    return unique


# ============================================================
# MÉTHODE 3
# Page Google News
# ============================================================

def extract_external_links_from_google_page(
    google_url
):

    try:

        response = requests.get(
            google_url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        if response.status_code != 200:
            return []

        content = response.text

        candidates = []

        # ----------------------------------------------------
        # href classiques
        # ----------------------------------------------------

        hrefs = re.findall(
            r'href=["\']([^"\']+)["\']',
            content,
            flags=re.IGNORECASE
        )

        candidates.extend(
            hrefs
        )

        # ----------------------------------------------------
        # URLs absolues présentes
        # ----------------------------------------------------

        absolute_urls = re.findall(
            r'https?://[^\s"\'<>]+',
            content
        )

        candidates.extend(
            absolute_urls
        )

        result = []

        for candidate in candidates:

            candidate = html.unescape(
                candidate
            )

            candidate = clean_url(
                candidate
            )

            if is_valid_external_url(
                candidate
            ):

                if candidate not in result:

                    result.append(
                        candidate
                    )

        return result

    except Exception:

        return []


# ============================================================
# MÉTHODE PRINCIPALE
# ============================================================

def resolve_google_news_url(url):

    url = clean_url(url)

    if not url:
        return None, "EMPTY"

    # Déjà URL média
    if is_valid_external_url(
        url
    ):
        return url, "ALREADY_EXTERNAL"

    # --------------------------------------------------------
    # Méthode 1
    # --------------------------------------------------------

    decoded = decode_google_news_token(
        url
    )

    if decoded:

        return decoded, "TOKEN_BASE64"

    # --------------------------------------------------------
    # Méthode 2
    # --------------------------------------------------------

    candidates = (
        extract_urls_from_binary_token(
            url
        )
    )

    if candidates:

        # Choisir le premier domaine externe
        return (
            candidates[0],
            "TOKEN_BINARY"
        )

    # --------------------------------------------------------
    # Méthode 3
    # --------------------------------------------------------

    candidates = (
        extract_external_links_from_google_page(
            url
        )
    )

    if candidates:

        return (
            candidates[0],
            "GOOGLE_PAGE"
        )

    return None, "UNRESOLVED"