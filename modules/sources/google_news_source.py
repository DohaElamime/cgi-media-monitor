# -*- coding: utf-8 -*-

"""
CGI Media Monitor
=================

Source Google News + résolution des vraies URLs.

Fonctions publiques utilisées par le projet :

    search_google_news()
    get_real_url()

Architecture :

    Google News RSS
        ↓
    URL news.google.com/rss/articles/CBMi...
        ↓
    Playwright
        ↓
    vraie URL du média
        ↓
    validation domaine + titre
        ↓
    article_extractor.py
"""


# ============================================================
# IMPORTS
# ============================================================

import json
import re
import time
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import (
    quote_plus,
    urlparse,
    urljoin,
)

import requests
from bs4 import BeautifulSoup

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from playwright.sync_api import (
        sync_playwright,
        TimeoutError as PlaywrightTimeoutError,
    )
except ImportError:
    sync_playwright = None
    PlaywrightTimeoutError = Exception


# ============================================================
# CONFIG
# ============================================================

try:
    from config import REQUEST_TIMEOUT
except Exception:
    REQUEST_TIMEOUT = 20

REQUEST_TIMEOUT = int(
    REQUEST_TIMEOUT or 20
)


# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive",
}


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ============================================================
# DOMAINES SUPPORTÉS
# ============================================================

DOMAIN_ALIASES = {
    "leseco.ma": [
        "leseco.ma",
        "www.leseco.ma",
    ],

    "fr.hespress.com": [
        "fr.hespress.com",
        "hespress.com",
        "www.hespress.com",
    ],

    "hespress.com": [
        "fr.hespress.com",
        "hespress.com",
        "www.hespress.com",
    ],

    "medias24.com": [
        "medias24.com",
        "www.medias24.com",
    ],

    "fr.le360.ma": [
        "fr.le360.ma",
        "le360.ma",
        "www.le360.ma",
    ],

    "le360.ma": [
        "fr.le360.ma",
        "le360.ma",
        "www.le360.ma",
    ],

    "challenge.ma": [
        "challenge.ma",
        "www.challenge.ma",
    ],

    "lavieeco.com": [
        "lavieeco.com",
        "www.lavieeco.com",
    ],

    "leconomiste.com": [
        "leconomiste.com",
        "www.leconomiste.com",
    ],

    "lematin.ma": [
        "lematin.ma",
        "www.lematin.ma",
    ],

    "mapnews.ma": [
        "mapnews.ma",
        "www.mapnews.ma",
    ],

    "boursenews.ma": [
        "boursenews.ma",
        "www.boursenews.ma",
    ],
}


# ============================================================
# STOPWORDS
# ============================================================

STOPWORDS = {
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "de",
    "dans",
    "sur",
    "pour",
    "avec",
    "sans",
    "par",
    "et",
    "ou",
    "au",
    "aux",
    "en",
    "a",
    "à",
    "ce",
    "cette",
    "ces",
    "son",
    "sa",
    "ses",
    "leur",
    "leurs",
    "est",
    "sont",
    "qui",
    "que",
    "dont",
    "plus",
    "moins",
    "très",
    "tres",
    "the",
    "and",
    "for",
    "with",
    "from",
}


# ============================================================
# TEXTE
# ============================================================

def normalize_text(text):
    if not text:
        return ""

    text = str(text)

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = text.lower()

    text = (
        text
        .replace("’", "'")
        .replace("œ", "oe")
        .replace("æ", "ae")
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def meaningful_tokens(text):
    return [
        token
        for token in normalize_text(text).split()
        if len(token) >= 3
        and token not in STOPWORDS
    ]


def clean_title(title):
    if not title:
        return ""

    value = str(title).strip()

    patterns = [
        r"\s*-\s*LesEco\.ma\s*$",
        r"\s*-\s*LesEco\s*$",
        r"\s*-\s*Le360\s*$",
        r"\s*-\s*Le360\.ma\s*$",
        r"\s*-\s*Medias24\s*$",
        r"\s*-\s*Médias24\s*$",
        r"\s*-\s*Challenge\.ma\s*$",
        r"\s*-\s*La Vie éco\s*$",
        r"\s*-\s*La Vie eco\s*$",
        r"\s*-\s*Le Matin\.ma\s*$",
        r"\s*-\s*L'Economiste\s*$",
        r"\s*-\s*L’Économiste\s*$",
        r"\s*-\s*Hespress.*$",
        r"\s*-\s*Numéro un de l'information économique marocaine\s*$",
        r"\s*-\s*Médias24.*$",
    ]

    for pattern in patterns:
        value = re.sub(
            pattern,
            "",
            value,
            flags=re.IGNORECASE,
        )

    return value.strip()


def title_similarity(title_a, title_b):
    a = normalize_text(title_a)
    b = normalize_text(title_b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    sequence_score = SequenceMatcher(
        None,
        a,
        b,
    ).ratio()

    tokens_a = set(
        meaningful_tokens(a)
    )

    tokens_b = set(
        meaningful_tokens(b)
    )

    if not tokens_a or not tokens_b:
        return sequence_score

    common = tokens_a & tokens_b
    union = tokens_a | tokens_b

    jaccard = (
        len(common) / len(union)
        if union
        else 0.0
    )

    coverage = (
        len(common) / len(tokens_a)
        if tokens_a
        else 0.0
    )

    return min(
        1.0,
        max(
            sequence_score,
            jaccard,
            coverage * 0.95,
        ),
    )


# ============================================================
# URL / SLUG
# ============================================================

def slug_to_title(url):
    if not url:
        return ""

    try:
        path = urlparse(url).path

        slug = (
            path
            .rstrip("/")
            .split("/")[-1]
        )

        slug = re.sub(
            r"\.(html?|php|aspx?)$",
            "",
            slug,
            flags=re.IGNORECASE,
        )

        # Hespress : 420967-titre
        slug = re.sub(
            r"^\d+[-_]+",
            "",
            slug,
        )

        # éventuel suffixe numérique
        slug = re.sub(
            r"-\d+$",
            "",
            slug,
        )

        return (
            slug
            .replace("-", " ")
            .replace("_", " ")
            .strip()
        )

    except Exception:
        return ""


def normalize_source(source):
    if not source:
        return ""

    source = str(
        source
    ).strip().lower()

    source = source.replace(
        "https://",
        "",
    )

    source = source.replace(
        "http://",
        "",
    )

    source = source.split("/")[0]

    return source


def get_allowed_domains(source):
    source = normalize_source(
        source
    )

    if source in DOMAIN_ALIASES:
        return DOMAIN_ALIASES[source]

    if source:
        return [source]

    return []


def domain_matches(url, source):
    if not url:
        return False

    try:
        host = (
            urlparse(url)
            .hostname
            or ""
        ).lower()
    except Exception:
        return False

    for domain in get_allowed_domains(
        source
    ):

        domain = domain.lower()

        if host == domain:
            return True

        if host.endswith(
            "." + domain
        ):
            return True

    return False


def is_google_news_url(url):
    if not url:
        return False

    try:
        host = (
            urlparse(url)
            .hostname
            or ""
        ).lower()
    except Exception:
        return False

    return (
        host == "news.google.com"
        or host.endswith(
            ".news.google.com"
        )
    )


# ============================================================
# DÉTECTION DES PAGES NON-ARTICLES
# ============================================================

def is_non_article_page(url, source="", title=""):
    """
    Détecte automatiquement les pages qui ne sont pas des
    articles de presse.

    Important :
    - une page sans date peut rester un vrai article ;
    - seules les pages clairement non éditoriales sont rejetées.
    """

    source = normalize_source(source)
    title_text = str(title or "").strip()
    title_norm = normalize_text(title_text)

    # --------------------------------------------------------
    # Titres connus de pages non-articles
    # --------------------------------------------------------

    bad_title_patterns = [
        r"^banniere corporate cgi$",
        r"^banniere corporate cgi cgi$",
        r"^www le360 ma$",
        r"^le360 le media des actualites du maroc$",
        r"^le360 morocco s news outlet$",
        r"^horaires? de prieres?",
        r"^rechercher annonce",
        r"^medias24 dadhboard",
        r"^general mapnews$",
        r"^general \| mapnews$",
        r"^fiche technique",
        r"^liste des fiche",
    ]

    for pattern in bad_title_patterns:
        if re.search(pattern, title_norm, flags=re.IGNORECASE):
            return True

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    if not url:
        return False

    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower().rstrip("/")
    except Exception:
        return True

    # Accueil d'un domaine
    if path in ("", "/"):
        return True

    # --------------------------------------------------------
    # Instit CGI
    # --------------------------------------------------------

    if host in ("instit.cgi.ma", "www.instit.cgi.ma"):
        return True

    # --------------------------------------------------------
    # Médias24 outils / annonces
    # --------------------------------------------------------

    if host in ("dash.medias24.com",):
        return True

    if host == "annoncesjudiciaires.medias24.com":
        return True

    # --------------------------------------------------------
    # Le360 langues : accueil / catégories
    # --------------------------------------------------------

    if host in (
        "fr.le360.ma",
        "le360.ma",
        "ar.le360.ma",
        "en.le360.ma",
    ):
        if path in (
            "",
            "/maroc",
            "/economie",
            "/politique",
            "/societe",
            "/sport",
            "/culture",
            "/monde",
            "/videos",
        ):
            return True

    # --------------------------------------------------------
    # Le Matin
    # --------------------------------------------------------

    if host in ("lematin.ma", "www.lematin.ma"):
        if path in (
            "",
            "/horaire-priere",
        ):
            return True

        if "/bourse-de-casablanca/" in path:
            return True

    # --------------------------------------------------------
    # MapNews
    # --------------------------------------------------------

    if host in ("mapnews.ma", "www.mapnews.ma"):
        if path.endswith("/general"):
            return True

    return False


# ============================================================
# VALIDATION URL
# ============================================================

def is_article_url(
    url,
    source="",
):
    if not url:
        return False

    if not str(url).startswith(
        (
            "http://",
            "https://",
        )
    ):
        return False

    if is_google_news_url(url):
        return False

    if source and not domain_matches(
        url,
        source,
    ):
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    path = (
        parsed.path
        or ""
    ).lower()

    normalized_path = (
        path.rstrip("/")
    )

    forbidden_exact = {
        "",
        "/",
        "/maroc",
        "/economie",
        "/business",
        "/politique",
        "/societe",
        "/nation",
        "/sport",
        "/culture",
        "/monde",
        "/actualite",
        "/actualites",
        "/a-la-une",
        "/contact",
        "/about",
        "/a-propos",
        "/mentions-legales",
        "/politique-de-confidentialite",
    }

    if normalized_path in forbidden_exact:
        return False

    forbidden_parts = [
        "/category/",
        "/categories/",
        "/categorie/",
        "/tag/",
        "/tags/",
        "/author/",
        "/auteur/",
        "/search/",
        "/page/",
        "/feed/",
        "/rss/",
        "/wp-json/",
        "/wp-admin/",
    ]

    for part in forbidden_parts:

        if part in path:
            return False

    # --------------------------------------------------------
    # HESPRESS
    # --------------------------------------------------------

    if source in (
        "fr.hespress.com",
        "hespress.com",
    ):

        if not re.search(
            r"/\d+-",
            path,
        ):
            return False

        blocked = (
            "politique-de-confidentialite",
            "contact",
            "a-propos",
            "mentions-legales",
            "equipe",
        )

        if any(
            item in path
            for item in blocked
        ):
            return False

    # --------------------------------------------------------
    # LESCO
    # --------------------------------------------------------

    if source == "leseco.ma":

        if not path.endswith(
            ".html"
        ):
            return False

    # --------------------------------------------------------
    # LE360
    # --------------------------------------------------------

    if source in (
        "fr.le360.ma",
        "le360.ma",
    ):

        last = (
            normalized_path
            .split("/")[-1]
        )

        if last in {
            "maroc",
            "economie",
            "politique",
            "societe",
            "sport",
            "culture",
            "monde",
            "videos",
        }:
            return False

    # --------------------------------------------------------
    # BOURSENEWS
    # --------------------------------------------------------

    if source == "boursenews.ma":
        # Les vrais articles Boursenews utilisent /article/...
        if not normalized_path.startswith("/article/"):
            return False

    return len(
        meaningful_tokens(
            slug_to_title(url)
        )
    ) >= 2


# ============================================================
# PAGE TITLE
# ============================================================

def get_page_title(url):
    response = http_get(url)

    if response is None:
        return ""

    if response.status_code != 200:
        return ""

    try:

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

    except Exception:
        return ""

    # og:title
    meta = soup.find(
        "meta",
        attrs={
            "property": "og:title",
        },
    )

    if meta:

        value = (
            meta.get("content")
            or ""
        ).strip()

        if value:
            return value

    # h1
    h1 = soup.find("h1")

    if h1:

        value = h1.get_text(
            " ",
            strip=True,
        )

        if value:
            return value

    # title
    if soup.title:

        return soup.title.get_text(
            " ",
            strip=True,
        )

    return ""


def validate_candidate(
    url,
    title,
    source,
    minimum_score=0.70,
):
    if not is_article_url(
        url,
        source,
    ):
        return (
            False,
            0.0,
        )

    if is_non_article_page(
        url,
        source,
        title,
    ):
        return (
            False,
            0.0,
        )

    page_title = get_page_title(
        url
    )

    if not page_title:
        return (
            False,
            0.0,
        )

    score = title_similarity(
        clean_title(title),
        clean_title(page_title),
    )

    print(
        f"[VALIDATION] "
        f"score={score:.2f} "
        f"title={clean_title(page_title)}"
    )

    return (
        score >= minimum_score,
        score,
    )


# ============================================================
# HTTP
# ============================================================

def http_get(url):
    if not url:
        return None

    try:

        return SESSION.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

    except requests.RequestException as exc:

        print(
            f"[HTTP ERROR] {url}"
        )

        print(exc)

        return None


# ============================================================
# PLAYWRIGHT
# ============================================================

def resolve_with_playwright(
    google_url,
    title,
    source,
):
    """
    Résout une URL Google News avec Chromium.

    C'est la méthode principale pour les liens :

        https://news.google.com/rss/articles/CBMi...
    """

    if not google_url:
        return ""

    if not google_url.startswith(
        ("http://", "https://")
    ):
        return ""

    if not is_google_news_url(
        google_url
    ):
        return ""

    if sync_playwright is None:

        print(
            "[PLAYWRIGHT] "
            "Playwright non installé."
        )

        return ""

    print(
        "[PLAYWRIGHT] "
        "Résolution Google News..."
    )

    discovered = []
    seen = set()

    try:

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=True,
            )

            context = browser.new_context(
                user_agent=HEADERS[
                    "User-Agent"
                ],
                locale="fr-FR",
                viewport={
                    "width": 1366,
                    "height": 768,
                },
            )

            page = context.new_page()

            # ------------------------------------------------
            # Capturer les URLs source
            # ------------------------------------------------

            def handle_response(response):

                try:

                    url = response.url

                    if not url:
                        return

                    if not domain_matches(
                        url,
                        source,
                    ):
                        return

                    if not is_article_url(
                        url,
                        source,
                    ):
                        return

                    if url in seen:
                        return

                    seen.add(url)
                    discovered.append(url)

                    print(
                        "[PLAYWRIGHT SOURCE] "
                        f"{url}"
                    )

                except Exception:
                    pass

            page.on(
                "response",
                handle_response,
            )

            # ------------------------------------------------
            # Navigation
            # ------------------------------------------------

            try:

                page.goto(
                    google_url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

            except PlaywrightTimeoutError:

                print(
                    "[PLAYWRIGHT] "
                    "Timeout navigation."
                )

            except Exception as exc:

                print(
                    "[PLAYWRIGHT NAV ERROR] "
                    f"{exc}"
                )

            # Donner le temps aux redirections JS
            page.wait_for_timeout(
                5000
            )

            # ------------------------------------------------
            # URL courante
            # ------------------------------------------------

            current_url = (
                page.url
                or ""
            ).strip()

            print(
                "[PLAYWRIGHT CURRENT] "
                f"{current_url}"
            )

            # Si on est directement sur la page source
            if is_article_url(
                current_url,
                source,
            ):

                valid, score = validate_candidate(
                    current_url,
                    title,
                    source,
                    minimum_score=0.65,
                )

                if valid:

                    print(
                        f"[PLAYWRIGHT OK] "
                        f"{current_url}"
                    )

                    browser.close()

                    return current_url

            # ------------------------------------------------
            # Chercher aussi dans les liens présents
            # ------------------------------------------------

            try:

                elements = page.locator(
                    "a"
                ).all()

                for element in elements:

                    try:

                        href = element.get_attribute(
                            "href"
                        )

                        if not href:
                            continue

                        href = href.strip()

                        if not href.startswith(
                            (
                                "http://",
                                "https://",
                            )
                        ):
                            continue

                        if not domain_matches(
                            href,
                            source,
                        ):
                            continue

                        if not is_article_url(
                            href,
                            source,
                        ):
                            continue

                        if href not in seen:

                            seen.add(href)
                            discovered.append(href)

                    except Exception:
                        continue

            except Exception:
                pass

            # ------------------------------------------------
            # Fermer navigateur
            # ------------------------------------------------

            browser.close()

        # ====================================================
        # Valider les URLs découvertes
        # ====================================================

        if discovered:

            print(
                f"[PLAYWRIGHT DISCOVERED] "
                f"{len(discovered)} URLs"
            )

        # Le premier candidat est généralement l'article
        # principal. Mais on valide avec le titre.
        for candidate in discovered:

            try:

                valid, score = validate_candidate(
                    candidate,
                    title,
                    source,
                    minimum_score=0.65,
                )

            except Exception:

                valid = False
                score = 0.0

            if valid:

                print(
                    f"[PLAYWRIGHT URL OK] "
                    f"score={score:.2f}"
                )

                return candidate

        # Si la validation stricte échoue mais qu'il n'y a
        # qu'une URL article du domaine, on ne la prend pas
        # automatiquement : éviter les faux positifs.

        return ""

    except Exception as exc:

        print(
            "[PLAYWRIGHT ERROR]"
        )

        print(
            str(exc)
        )

        return ""


# ============================================================
# RECHERCHE HESPRESS
# ============================================================

def search_hespress(title):

    clean = clean_title(
        title
    )

    tokens = meaningful_tokens(
        clean
    )

    queries = [
        clean,
    ]

    if len(tokens) >= 8:

        queries.append(
            " ".join(tokens[:8])
        )

    if len(tokens) >= 6:

        queries.append(
            " ".join(tokens[:6])
        )

    for query in queries:

        print(
            f"[RECHERCHE HESPRESS] "
            f"{query}"
        )

        search_url = (
            "https://fr.hespress.com/"
            "?s="
            + quote_plus(query)
        )

        response = http_get(
            search_url
        )

        if response is None:
            continue

        print(
            f"[HESPRESS STATUS] "
            f"{response.status_code} "
            f"HTML={len(response.text)}"
        )

        if response.status_code != 200:
            continue

        try:

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

        except Exception:
            continue

        candidates = []

        for anchor in soup.find_all(
            "a",
            href=True,
        ):

            href = (
                anchor.get("href")
                or ""
            ).strip()

            text = anchor.get_text(
                " ",
                strip=True,
            )

            if not is_article_url(
                href,
                "fr.hespress.com",
            ):
                continue

            score = max(
                title_similarity(
                    clean,
                    text,
                ),
                title_similarity(
                    clean,
                    slug_to_title(href),
                ),
            )

            candidates.append(
                (
                    score,
                    href,
                    text,
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        for (
            score,
            href,
            text,
        ) in candidates[:20]:

            print(
                f"[HESPRESS CANDIDAT] "
                f"score={score:.2f} "
                f"title={text}"
            )

            if score < 0.80:
                continue

            valid, _ = validate_candidate(
                href,
                clean,
                "fr.hespress.com",
                minimum_score=0.80,
            )

            if valid:

                print(
                    f"[REAL URL HESPRESS] "
                    f"{href}"
                )

                return href

    return None


# ============================================================
# RECHERCHE LES ECO
# ============================================================

def search_leseco(title):

    clean = clean_title(
        title
    )

    tokens = meaningful_tokens(
        clean
    )

    queries = [
        clean,
    ]

    if len(tokens) >= 8:

        queries.append(
            " ".join(tokens[:8])
        )

    if len(tokens) >= 6:

        queries.append(
            " ".join(tokens[:6])
        )

    for query in queries:

        print(
            f"[RECHERCHE LESCO] "
            f"{query}"
        )

        search_url = (
            "https://leseco.ma/"
            "?s="
            + quote_plus(query)
        )

        response = http_get(
            search_url
        )

        if response is None:
            continue

        print(
            f"[LES ECO STATUS] "
            f"{response.status_code} "
            f"HTML={len(response.text)}"
        )

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        candidates = []

        for anchor in soup.find_all(
            "a",
            href=True,
        ):

            href = (
                anchor.get("href")
                or ""
            ).strip()

            text = anchor.get_text(
                " ",
                strip=True,
            )

            if not is_article_url(
                href,
                "leseco.ma",
            ):
                continue

            score = max(
                title_similarity(
                    clean,
                    text,
                ),
                title_similarity(
                    clean,
                    slug_to_title(href),
                ),
            )

            candidates.append(
                (
                    score,
                    href,
                    text,
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        for (
            score,
            href,
            text,
        ) in candidates[:20]:

            print(
                f"[LES ECO CANDIDAT] "
                f"score={score:.2f} "
                f"title={text}"
            )

            if score < 0.75:
                continue

            valid, _ = validate_candidate(
                href,
                clean,
                "leseco.ma",
                minimum_score=0.80,
            )

            if valid:

                return href

    return None


# ============================================================
# RECHERCHE LE360
# ============================================================

def search_le360(title):

    clean = clean_title(
        title
    )

    tokens = meaningful_tokens(
        clean
    )

    queries = [
        clean,
    ]

    if len(tokens) >= 10:

        queries.append(
            " ".join(tokens[:10])
        )

    if len(tokens) >= 8:

        queries.append(
            " ".join(tokens[:8])
        )

    if len(tokens) >= 6:

        queries.append(
            " ".join(tokens[:6])
        )

    seen_queries = set()

    for query in queries:

        if query in seen_queries:
            continue

        seen_queries.add(query)

        search_url = (
            "https://fr.le360.ma/"
            "recherche/?q="
            + quote_plus(query)
        )

        print(
            f"[RECHERCHE LE360] "
            f"{query}"
        )

        print(
            f"[LE360 SEARCH URL] "
            f"{search_url}"
        )

        response = http_get(
            search_url
        )

        if response is None:
            continue

        print(
            f"[LE360 STATUS] "
            f"{response.status_code} "
            f"HTML={len(response.text)}"
        )

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        candidates = []
        seen_urls = set()

        for anchor in soup.find_all(
            "a",
            href=True,
        ):

            href = (
                anchor.get("href")
                or ""
            ).strip()

            text = anchor.get_text(
                " ",
                strip=True,
            )

            if href.startswith("/"):
                href = urljoin(
                    "https://fr.le360.ma",
                    href,
                )

            if not is_article_url(
                href,
                "fr.le360.ma",
            ):
                continue

            if href in seen_urls:
                continue

            seen_urls.add(href)

            score = max(
                title_similarity(
                    clean,
                    text,
                ),
                title_similarity(
                    clean,
                    slug_to_title(href),
                ),
            )

            candidates.append(
                (
                    score,
                    href,
                    text,
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        print(
            f"[LE360 CANDIDATS] "
            f"{len(candidates)}"
        )

        for (
            score,
            href,
            text,
        ) in candidates[:20]:

            print(
                f"[LE360 CANDIDAT] "
                f"score={score:.2f} "
                f"title={text}"
            )

            if score < 0.75:
                continue

            valid, validation_score = (
                validate_candidate(
                    href,
                    clean,
                    "fr.le360.ma",
                    minimum_score=0.75,
                )
            )

            if valid:

                print(
                    f"[REAL URL LE360] "
                    f"{href}"
                )

                return href

    return None


# ============================================================
# RECHERCHE MEDIAS24
# ============================================================

def search_medias24(title):

    clean = clean_title(
        title
    )

    print(
        f"[RECHERCHE MEDIAS24] "
        f"{clean}"
    )

    # Médias24 peut renvoyer 404 sur son ?s=
    # donc on utilise d'abord une recherche légère
    # sur son domaine via la page d'accueil / liens.
    #
    # Playwright Google News reste la méthode principale.
    #
    # Ici on tente uniquement quelques patterns
    # historiques d'URL Médias24.

    normalized = normalize_text(
        clean
    )

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        normalized,
    ).strip("-")

    candidates = []

    # Quelques structures historiques fréquentes.
    for date_prefix in (
        "2020/02/05",
        "2020/02",
    ):

        candidates.append(
            f"https://medias24.com/"
            f"{date_prefix}/"
            f"{slug}/"
        )

        candidates.append(
            f"https://medias24.com/"
            f"{date_prefix}/"
            f"{slug}-6588/"
        )

    # Tester les URL candidates.
    for candidate in candidates:

        print(
            f"[MEDIAS24 URL TEST] "
            f"{candidate}"
        )

        response = http_get(
            candidate
        )

        if response is None:
            continue

        print(
            f"[MEDIAS24 STATUS] "
            f"{response.status_code} "
            f"HTML={len(response.text)}"
        )

        if response.status_code != 200:
            continue

        page_title = get_page_title(
            response.url
        )

        score = title_similarity(
            clean,
            clean_title(page_title),
        )

        print(
            f"[MEDIAS24 VALIDATION] "
            f"score={score:.2f} "
            f"title={clean_title(page_title)}"
        )

        if (
            score >= 0.70
            and is_article_url(
                response.url,
                "medias24.com",
            )
        ):

            return response.url

    return None


# ============================================================
# GOOGLE NEWS
# ============================================================

def build_google_news_url(query):

    return (
        "https://news.google.com/rss/search?"
        "q="
        + quote_plus(query)
        + "&hl=fr"
        + "&gl=MA"
        + "&ceid=MA:fr"
    )


def get_google_news_feed(query):

    url = build_google_news_url(
        query
    )

    print(
        f"[GOOGLE RSS] "
        f"{query}"
    )

    response = http_get(
        url
    )

    if response is None:
        return []

    print(
        f"[GOOGLE RSS STATUS] "
        f"{response.status_code} "
        f"HTML={len(response.text)}"
    )

    if response.status_code != 200:
        return []

    if feedparser is not None:

        try:

            feed = feedparser.parse(
                response.content
            )

            if feed.entries:
                return feed.entries

        except Exception:
            pass

    # Fallback XML
    try:

        soup = BeautifulSoup(
            response.text,
            "xml",
        )

        return soup.find_all(
            "item"
        )

    except Exception:
        return []


def get_entry_title(entry):

    if isinstance(
        entry,
        dict,
    ):

        return str(
            entry.get(
                "title",
                "",
            )
            or ""
        ).strip()

    node = entry.find(
        "title"
    )

    if node:
        return node.get_text(
            " ",
            strip=True,
        )

    return ""


def get_entry_link(entry):

    if isinstance(
        entry,
        dict,
    ):

        return str(
            entry.get(
                "link",
                "",
            )
            or ""
        ).strip()

    node = entry.find(
        "link"
    )

    if node:

        href = (
            node.get("href")
            or ""
        ).strip()

        if href:
            return href

        return node.get_text(
            " ",
            strip=True,
        )

    return ""


def _datetime_to_iso(value):
    """Convertit un struct_time/datetime en ISO."""
    if value is None:
        return ""

    try:
        if hasattr(value, "tm_year"):
            return datetime(
                value.tm_year,
                value.tm_mon,
                value.tm_mday,
                value.tm_hour,
                value.tm_min,
                value.tm_sec,
            ).isoformat()

        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            return value.isoformat()
    except Exception:
        pass

    return ""


def _parse_date_string(value):
    """Convertit les formats RSS/ISO et les dates françaises courantes en ISO."""
    if value is None:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    # --------------------------------------------------------
    # ISO / RFC classiques
    # --------------------------------------------------------
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed.isoformat()
    except Exception:
        pass

    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S",
        "%d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed.isoformat()
        except Exception:
            continue

    # --------------------------------------------------------
    # DATES EN FRANCAIS
    # Exemples :
    #   19 août 2014
    #   27 Septembre 2021
    #   Mardi 29 Mars 2016
    #   29 mars 2016 à 14:32
    # --------------------------------------------------------
    months = {
        "janvier": 1,
        "fevrier": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "aout": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "decembre": 12,
    }

    cleaned = unicodedata.normalize("NFKD", value)
    cleaned = "".join(
        char
        for char in cleaned
        if not unicodedata.combining(char)
    ).lower()
    cleaned = cleaned.replace("’", "'")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    french_match = re.search(
        r"(?:\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b\s+)?"
        r"(\d{1,2})\s+"
        r"(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)"
        r"\s+(\d{4})"
        r"(?:\s+(?:a|à)\s+(\d{1,2}):?(\d{2})?(?::(\d{2}))?)?",
        cleaned,
        flags=re.IGNORECASE,
    )

    if french_match:
        day = int(french_match.group(1))
        month = months[french_match.group(2)]
        year = int(french_match.group(3))
        hour = int(french_match.group(4) or 0)
        minute = int(french_match.group(5) or 0)
        second = int(french_match.group(6) or 0)

        try:
            return datetime(
                year,
                month,
                day,
                hour,
                minute,
                second,
            ).isoformat()
        except ValueError:
            return ""

    # Anglais avec jour éventuel : 27 September 2021
    english_match = re.search(
        r"(?:\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b\s+)?"
        r"(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})",
        value,
        flags=re.IGNORECASE,
    )

    if english_match:
        try:
            parsed = datetime.strptime(
                english_match.group(0),
                "%d %B %Y",
            )
            return parsed.isoformat()
        except Exception:
            try:
                parsed = datetime.strptime(
                    re.sub(
                        r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+",
                        "",
                        english_match.group(0),
                        flags=re.IGNORECASE,
                    ),
                    "%d %B %Y",
                )
                return parsed.isoformat()
            except Exception:
                pass

    return ""


def get_entry_date(entry):
    """
    Récupère la meilleure date d'une entrée Google News/RSS.
    """
    if isinstance(entry, dict):
        value = _datetime_to_iso(entry.get("published_parsed"))
        if value:
            return value

        value = _parse_date_string(entry.get("published", ""))
        if value:
            return value

        value = _datetime_to_iso(entry.get("updated_parsed"))
        if value:
            return value

        value = _parse_date_string(entry.get("updated", ""))
        if value:
            return value

        for key in ("dc_date", "date"):
            value = _parse_date_string(entry.get(key, ""))
            if value:
                return value

        return ""

    try:
        for tag_name in ("pubDate", "published", "updated", "date"):
            node = entry.find(tag_name)
            if not node:
                continue

            value = (
                node.get("value")
                or node.get("datetime")
                or node.get_text(" ", strip=True)
            )

            parsed = _parse_date_string(value)
            if parsed:
                return parsed
    except Exception:
        pass

    return ""


def extract_boursenews_date(url):
    """Extraction robuste de la date Boursenews, y compris dates textuelles françaises."""
    if not url:
        return ""

    print(f"[BOURSENEWS DATE] {url}")

    response = http_get(url)
    if response is None or response.status_code != 200:
        return ""

    html = response.text or ""

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return ""

    # --------------------------------------------------------
    # 1. JSON-LD
    # --------------------------------------------------------
    for script in soup.find_all(
        "script",
        type=re.compile(
            r"application/ld\+json",
            re.IGNORECASE,
        ),
    ):
        raw = (
            script.string
            or script.get_text()
            or ""
        ).strip()

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        objects = (
            data
            if isinstance(data, list)
            else [data]
        )

        if (
            isinstance(data, dict)
            and isinstance(
                data.get("@graph"),
                list,
            )
        ):
            objects.extend(
                data["@graph"]
            )

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            for key in (
                "datePublished",
                "dateCreated",
                "uploadDate",
            ):
                parsed = _parse_date_string(
                    obj.get(key)
                )

                if parsed:
                    print(
                        f"[BOURSENEWS JSON-LD] {parsed}"
                    )
                    return parsed

    # --------------------------------------------------------
    # 2. META
    # --------------------------------------------------------
    selectors = [
        {"property": "article:published_time"},
        {"property": "og:published_time"},
        {"name": "date"},
        {"name": "pubdate"},
        {"name": "publishdate"},
        {"name": "published"},
        {"name": "datepublished"},
        {"itemprop": "datePublished"},
        {"itemprop": "datecreated"},
    ]

    for attrs in selectors:

        tag = soup.find(
            "meta",
            attrs=attrs,
        )

        if not tag:
            continue

        value = (
            tag.get("content")
            or tag.get("datetime")
            or tag.get("value")
            or ""
        )

        parsed = _parse_date_string(
            value
        )

        if parsed:
            print(
                f"[BOURSENEWS META] {parsed}"
            )
            return parsed

    # --------------------------------------------------------
    # 3. TIME / DATE ATTRIBUTES
    # --------------------------------------------------------
    for tag in soup.find_all("time"):

        candidates = [
            tag.get("datetime"),
            tag.get("data-datetime"),
            tag.get("data-date"),
            tag.get("data-published"),
            tag.get_text(
                " ",
                strip=True,
            ),
        ]

        for value in candidates:

            parsed = _parse_date_string(
                value
            )

            if parsed:
                print(
                    f"[BOURSENEWS TIME] {parsed}"
                )
                return parsed

    # --------------------------------------------------------
    # 4. CLASSES / ATTRIBUTS
    # --------------------------------------------------------
    date_pattern = re.compile(
        r"date|published|publication|post-date|article-date|created",
        re.IGNORECASE,
    )

    for tag in soup.find_all(
        class_=date_pattern
    ):

        candidates = [
            tag.get("datetime"),
            tag.get("data-datetime"),
            tag.get("data-date"),
            tag.get("data-published"),
            tag.get_text(
                " ",
                strip=True,
            ),
        ]

        for value in candidates:

            parsed = _parse_date_string(
                value
            )

            if parsed:
                print(
                    f"[BOURSENEWS CLASS] {parsed}"
                )
                return parsed

    # --------------------------------------------------------
    # 5. TEXTE VISIBLE DE LA PAGE
    # --------------------------------------------------------
    visible_text = soup.get_text(
        " ",
        strip=True,
    )

    # Éviter des correspondances sur trop de texte :
    # tester d'abord les expressions proches des mots date.
    contextual_patterns = [
        r"(?:date de publication|publication|publié le|publie le|publi[ée]|actualisé le|actualise le|mis à jour le|mis a jour le)\D{0,40}((?:(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+)?\d{1,2}\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+\d{4}(?:\s+(?:à|a)\s+\d{1,2}:?\d{2})?)",
        r"(?:date|publication|publié|publie)\D{0,60}(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    ]

    for pattern in contextual_patterns:

        match = re.search(
            pattern,
            visible_text,
            flags=re.IGNORECASE,
        )

        if match:

            candidate = (
                match.group(1)
                or match.group(0)
            )

            parsed = _parse_date_string(
                candidate
            )

            if parsed:
                print(
                    f"[BOURSENEWS TEXT CONTEXT] {parsed}"
                )
                return parsed

    # Dernier recours : une date française brute dans le texte.
    raw_date_pattern = re.compile(
        r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*"
        r"\d{1,2}\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+\d{4}",
        re.IGNORECASE,
    )

    for match in raw_date_pattern.finditer(
        visible_text
    ):

        parsed = _parse_date_string(
            match.group(0)
        )

        if parsed:
            print(
                f"[BOURSENEWS TEXT] {parsed}"
            )
            return parsed

    print(
        "[BOURSENEWS DATE] Aucune date trouvée"
    )

    return ""


def extract_published_date_from_page(url):
    """Extrait la date de publication depuis la page originale du média."""
    if not url:
        return ""

    host = (urlparse(url).hostname or "").lower()

    if host in ("boursenews.ma", "www.boursenews.ma"):
        return extract_boursenews_date(url)

    response = http_get(url)
    if response is None or response.status_code != 200:
        return ""

    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception:
        return ""

    # JSON-LD
    for script in soup.find_all("script", type=re.compile(r"application/ld\+json", re.IGNORECASE)):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        objects = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            objects.extend(data["@graph"])

        for obj in objects:
            if not isinstance(obj, dict):
                continue
            for key in ("datePublished", "dateCreated"):
                parsed = _parse_date_string(obj.get(key))
                if parsed:
                    print(f"[DATE JSON-LD] {parsed}")
                    return parsed

    # Meta
    selectors = [
        {"property": "article:published_time"},
        {"property": "og:published_time"},
        {"name": "date"},
        {"name": "pubdate"},
        {"name": "publishdate"},
        {"itemprop": "datePublished"},
    ]

    for attrs in selectors:
        tag = soup.find("meta", attrs=attrs)
        if not tag:
            continue

        value = tag.get("content") or tag.get("datetime") or tag.get("value") or ""
        parsed = _parse_date_string(value)
        if parsed:
            print(f"[DATE META] {parsed}")
            return parsed

    # time
    for tag in soup.find_all("time"):
        value = tag.get("datetime") or tag.get("data-datetime") or tag.get_text(" ", strip=True) or ""
        parsed = _parse_date_string(value)
        if parsed:
            print(f"[DATE TIME] {parsed}")
            return parsed

    return ""


def get_entry_source(entry):

    if isinstance(
        entry,
        dict,
    ):

        source_data = (
            entry.get(
                "source",
                {}
            )
            or {}
        )

        if isinstance(
            source_data,
            dict,
        ):

            href = (
                source_data.get(
                    "href",
                    ""
                )
                or ""
            )

            if href:

                try:
                    return (
                        urlparse(
                            href
                        ).hostname
                        or ""
                    )
                except Exception:
                    pass

            return (
                source_data.get(
                    "title",
                    ""
                )
                or ""
            )

        return str(
            source_data
        )

    node = entry.find(
        "source"
    )

    if node:
        return node.get_text(
            " ",
            strip=True,
        )

    return ""


# ============================================================
# search_google_news
# ============================================================

def search_google_news(
    query=None,
    source=None,
    max_results=100,
):
    """
    Fonction utilisée par aggregator.py.

    Retour :

        {
            title,
            source,
            date,
            url
        }

    url = URL Google News.
    """

    if query:

        queries = [
            str(query).strip()
        ]

    else:

        try:

            from config import SEARCH_QUERIES

            queries = list(
                SEARCH_QUERIES
            )

        except Exception:

            queries = [
                '"Compagnie Générale Immobilière"',
                '"Compagnie Générale Immobilière Maroc"',
                '"CGI Maroc"',
                '"CGI immobilier"',
                '"CGI" promoteur immobilier',
                '"CGI" immobilier Maroc',
                '"CDG Développement" CGI',
            ]

    results = []

    seen_urls = set()
    seen_titles = set()

    print()
    print("=" * 70)
    print("GOOGLE NEWS")
    print("=" * 70)

    for current_query in queries:

        if not current_query:
            continue

        search_query = current_query

        if source:
            search_query += (
                f" {source}"
            )

        print()
        print(
            f"Google News : "
            f"{search_query}"
        )

        entries = get_google_news_feed(
            search_query
        )

        print(
            f"[GOOGLE NEWS ITEMS] "
            f"{len(entries)}"
        )

        for entry in entries:

            title = get_entry_title(
                entry
            )

            link = get_entry_link(
                entry
            )

            date_value = get_entry_date(
                entry
            )

            source_value = get_entry_source(
                entry
            )

            if not title or not link:
                continue

            effective_source = (
                normalize_source(source_value)
                or normalize_source(source)
            )

            if is_non_article_page(
                link,
                effective_source,
                title,
            ):
                print(
                    "[GOOGLE SKIP NON-ARTICLE] "
                    f"{title}"
                )
                continue

            if link in seen_urls:
                continue

            cleaned = clean_title(
                title
            )

            normalized = normalize_text(
                cleaned
            )

            if normalized in seen_titles:
                continue

            seen_urls.add(
                link
            )

            seen_titles.add(
                normalized
            )

            parsed_date = (
                _parse_date_string(date_value)
                or date_value
            )

            results.append(
                {
                    "title": title,
                    "source": (
                        source_value
                        or source
                        or ""
                    ),
                    "date": parsed_date,
                    "url": link,
                }
            )

            if len(results) >= max_results:
                break

        if len(results) >= max_results:
            break

    print()
    print(
        f"Google News : "
        f"{len(results)} articles"
    )

    return results


# ============================================================
# GET REAL URL
# ============================================================

def get_real_url(
    google_url,
    title,
    source,
):
    """
    Résout une URL Google News vers la vraie URL.

    Priorité :

        1. URL déjà réelle
        2. Playwright Google News
        3. recherche spécifique du média
        4. échec
    """

    if not title:
        print(
            "[REAL URL ECHEC] "
            "Titre absent"
        )
        return ""

    if not source:
        print(
            "[REAL URL ECHEC] "
            "Source absente"
        )
        return ""

    source = normalize_source(
        source
    )

    clean = clean_title(
        title
    )

    print()
    print(
        f"[RECHERCHE SOURCE] "
        f"{source} : {clean}"
    )

    # ========================================================
    # 1. URL DÉJÀ RÉELLE
    # ========================================================

    if (
        google_url
        and str(google_url).startswith(
            (
                "http://",
                "https://",
            )
        )
        and not is_google_news_url(
            google_url
        )
        and is_article_url(
            google_url,
            source,
        )
        and not is_non_article_page(
            google_url,
            source,
            title,
        )
    ):

        print(
            f"[URL DIRECTE] "
            f"{google_url}"
        )

        return google_url

    # ========================================================
    # 2. PLAYWRIGHT
    # ========================================================

    if google_url:

        print(
            "[1/2] "
            "Résolution Google News avec Playwright..."
        )

        resolved = resolve_with_playwright(
            google_url,
            clean,
            source,
        )

        if resolved:

            print(
                f"[REAL URL PLAYWRIGHT] "
                f"{resolved}"
            )

            return resolved

    # ========================================================
    # 3. RECHERCHE SPÉCIFIQUE SOURCE
    # ========================================================

    print(
        "[2/2] "
        "Recherche spécifique du média..."
    )

    if source in (
        "fr.le360.ma",
        "le360.ma",
    ):

        resolved = search_le360(
            clean
        )

        if resolved:

            print(
                f"[REAL URL LE360] "
                f"{resolved}"
            )

            return resolved

    elif source in (
        "fr.hespress.com",
        "hespress.com",
    ):

        resolved = search_hespress(
            clean
        )

        if resolved:

            print(
                f"[REAL URL HESPRESS] "
                f"{resolved}"
            )

            return resolved

    elif source == "leseco.ma":

        resolved = search_leseco(
            clean
        )

        if resolved:

            print(
                f"[REAL URL LESCO] "
                f"{resolved}"
            )

            return resolved

    elif source == "medias24.com":

        resolved = search_medias24(
            clean
        )

        if resolved:

            print(
                f"[REAL URL MEDIAS24] "
                f"{resolved}"
            )

            return resolved

    # ========================================================
    # 4. ÉCHEC
    # ========================================================

    print(
        f"[REAL URL ECHEC] "
        f"{clean}"
    )

    return ""


# ============================================================
# TESTS
# ============================================================

if __name__ == "__main__":

    tests = [
        {
            "name": "LE360",
            "title": (
                "Immobilier: la CGI lance sa plateforme "
                "de réservation en ligne - Le360"
            ),
            "source": "fr.le360.ma",
        },

        {
            "name": "MEDIAS24",
            "title": (
                "La CGI est de nouveau bénéficiaire "
                "à fin juin 2019 - Médias24"
            ),
            "source": "medias24.com",
        },

        {
            "name": "HESPRESS",
            "title": (
                "Abderrahmane Ifrassen nommé DGA de CDG "
                "développement et DG de la CGI - Hespress"
            ),
            "source": "fr.hespress.com",
        },

        {
            "name": "LES ECO",
            "title": (
                "Azur Valley : quand le quotidien prend "
                "des airs de vacances à Dar Bouazza - LesEco.ma"
            ),
            "source": "leseco.ma",
        },
    ]

    print()
    print("=" * 70)
    print("TESTS get_real_url")
    print("=" * 70)

    success = 0
    failure = 0

    for index, test in enumerate(
        tests,
        start=1,
    ):

        print()
        print("=" * 70)
        print(
            f"TEST {index} - "
            f"{test['name']}"
        )
        print("=" * 70)

        result = get_real_url(
            "",
            test["title"],
            test["source"],
        )

        print()
        print(
            "RESULTAT =",
            result,
        )

        if result:
            success += 1
        else:
            failure += 1

        time.sleep(1)

    print()
    print("=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)

    print(
        f"Succès : {success}"
    )

    print(
        f"Échecs : {failure}"
    )

    print(
        f"Total  : {success + failure}"
    )