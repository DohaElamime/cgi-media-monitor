# ============================================================
# CGI MEDIA MONITOR
# GDELT DOC 2.0 SOURCE
#
# Source de collecte :
#     GDELT DOC 2.0 API
#
# IMPORTANT :
# - aucune écriture SQLite
# - aucun scraping des sites médias
# - aucune classification de sentiment ici
# - GPT-OSS reste responsable de la pertinence et du sentiment
# ============================================================

from __future__ import annotations

import re
import html
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests


# ============================================================
# CONFIGURATION
# ============================================================

GDELT_URL = (
    "https://api.gdeltproject.org/api/v2/doc/doc"
)

REQUEST_TIMEOUT = 30

DEFAULT_TIMESPAN = "30d"

DEFAULT_MAX_RECORDS = 250


# ============================================================
# NETTOYAGE
# ============================================================

def clean_text(value: Any) -> str:
    """
    Nettoie un texte provenant de GDELT.
    """

    if value is None:
        return ""

    text = str(value)

    text = html.unescape(text)

    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# DATE
# ============================================================

def parse_gdelt_date(value: Any) -> Optional[str]:
    """
    GDELT retourne généralement :
        YYYYMMDDHHMMSS

    On transforme en :
        YYYY-MM-DD HH:MM:SS
    """

    value = clean_text(value)

    if not value:
        return None

    # Format GDELT standard
    if re.fullmatch(r"\d{14}", value):

        try:
            dt = datetime.strptime(
                value,
                "%Y%m%d%H%M%S",
            )

            return dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        except ValueError:
            pass

    # Si jamais l'API fournit déjà une date ISO
    try:
        value_iso = value.replace("Z", "+00:00")

        dt = datetime.fromisoformat(
            value_iso
        )

        return dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception:
        pass

    return value


# ============================================================
# CONSTRUCTION DE L'URL
# ============================================================

def build_gdelt_url(
    query: str,
    timespan: str = DEFAULT_TIMESPAN,
    max_records: int = DEFAULT_MAX_RECORDS,
    sort: str = "datedesc",
) -> str:
    """
    Construit l'URL GDELT DOC 2.0.

    Exemple :

    query = "CGI Maroc"

    mode = artlist
    format = json
    """

    params = (
        f"query={quote(query)}"
        f"&mode=artlist"
        f"&format=json"
        f"&maxrecords={max_records}"
        f"&timespan={timespan}"
        f"&sort={sort}"
    )

    return f"{GDELT_URL}?{params}"


# ============================================================
# APPEL API
# ============================================================

def fetch_gdelt(
    query: str,
    timespan: str = DEFAULT_TIMESPAN,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> Dict[str, Any]:

    url = build_gdelt_url(
        query=query,
        timespan=timespan,
        max_records=max_records,
    )

    headers = {
        "User-Agent": (
            "CGI-Media-Monitor/2.0 "
            "(research project)"
        ),
        "Accept": "application/json",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    try:
        data = response.json()

    except Exception as exc:

        raise RuntimeError(
            "GDELT n'a pas retourné un JSON valide."
        ) from exc

    if not isinstance(data, dict):

        raise RuntimeError(
            "Réponse GDELT inattendue."
        )

    return data


# ============================================================
# EXTRACTION DES ARTICLES
# ============================================================

def normalize_gdelt_article(
    item: Dict[str, Any],
    query: str,
) -> Optional[Dict[str, Any]]:
    """
    Transforme un résultat GDELT en article
    compatible avec CGI Media Monitor.
    """

    title = clean_text(
        item.get("title")
        or item.get("Title")
        or ""
    )

    url = clean_text(
        item.get("url")
        or item.get("URL")
        or ""
    )

    if not title or not url:
        return None

    source = clean_text(
        item.get("domain")
        or item.get("sourcecountry")
        or item.get("source")
        or ""
    )

    date_value = (
        item.get("seendate")
        or item.get("seenDate")
        or item.get("date")
        or ""
    )

    published_at = parse_gdelt_date(
        date_value
    )

    # --------------------------------------------------------
    # GDELT ArtList ne fournit pas nécessairement
    # un véritable résumé éditorial.
    #
    # On ne fabrique PAS de faux résumé.
    # --------------------------------------------------------

    return {
        "title": title,

        "summary": "",

        "description": "",

        "content": "",

        "source": source,

        "date": published_at,

        "published_at": published_at,

        "url": url,

        "query": query,

        "input_mode": "GDELT_TITLE",

        "collection_source": "GDELT",

        # Métadonnées GDELT conservées
        "gdelt_domain": clean_text(
            item.get("domain", "")
        ),

        "gdelt_source_country": clean_text(
            item.get("sourcecountry", "")
        ),

        "gdelt_language": clean_text(
            item.get("language", "")
        ),

        "gdelt_tone": item.get("tone"),

        "gdelt_raw": item,
    }


# ============================================================
# PARSING
# ============================================================

def parse_gdelt_response(
    data: Dict[str, Any],
    query: str,
) -> List[Dict[str, Any]]:

    articles = []

    items = (
        data.get("articles")
        or data.get("Articles")
        or []
    )

    if not isinstance(items, list):
        return articles

    for item in items:

        if not isinstance(item, dict):
            continue

        article = normalize_gdelt_article(
            item,
            query=query,
        )

        if article:
            articles.append(article)

    return articles


# ============================================================
# DÉDUPLICATION
# ============================================================

def normalize_url(url: str) -> str:
    """
    Normalisation légère d'URL pour déduplication.
    """

    url = clean_text(url)

    if not url:
        return ""

    url = url.lower()

    # Supprimer slash final
    url = url.rstrip("/")

    return url


def deduplicate_articles(
    articles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    result = []

    seen_urls = set()

    seen_titles = set()

    for article in articles:

        url = normalize_url(
            article.get("url", "")
        )

        title = clean_text(
            article.get("title", "")
        ).lower()

        title = re.sub(
            r"\s+",
            " ",
            title,
        ).strip()

        # URL prioritaire
        if url:

            if url in seen_urls:
                continue

            seen_urls.add(url)

        # Titre secondaire
        if title:

            if title in seen_titles:
                continue

            seen_titles.add(title)

        result.append(article)

    return result


# ============================================================
# COLLECTE
# ============================================================

def collect_gdelt_articles(
    queries: Optional[List[str]] = None,
    query: Optional[str] = None,
    timespan: str = DEFAULT_TIMESPAN,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> List[Dict[str, Any]]:
    """
    Collecte les articles depuis GDELT.

    Compatible avec :

        collect_gdelt_articles(
            queries=[...]
        )

    ou :

        collect_gdelt_articles(
            query="..."
        )
    """

    if queries is None:
        queries = []

    if query:
        queries = list(queries) + [query]

    if not queries:

        queries = [
            '"CGI" Maroc',
            '"Compagnie Générale Immobilière"',
            '"CGI Maroc" immobilier',
        ]

    # Déduplication des requêtes
    unique_queries = []

    for q in queries:

        q = clean_text(q)

        if q and q not in unique_queries:
            unique_queries.append(q)

    all_articles = []

    for current_query in unique_queries:

        print(
            f"[GDELT] Recherche : "
            f"{current_query}"
        )

        try:

            data = fetch_gdelt(
                query=current_query,
                timespan=timespan,
                max_records=max_records,
            )

            articles = parse_gdelt_response(
                data,
                query=current_query,
            )

            print(
                f"[GDELT] Résultats : "
                f"{len(articles)}"
            )

            all_articles.extend(articles)

        except Exception as exc:

            print(
                f"[GDELT ERROR] "
                f"{current_query} : {exc}"
            )

    return deduplicate_articles(
        all_articles
    )


# ============================================================
# STATISTIQUES
# ============================================================

def get_gdelt_statistics(
    articles: List[Dict[str, Any]],
) -> Dict[str, int]:

    return {
        "total": len(articles),

        "with_title": sum(
            1
            for a in articles
            if a.get("title")
        ),

        "with_url": sum(
            1
            for a in articles
            if a.get("url")
        ),

        "with_source": sum(
            1
            for a in articles
            if a.get("source")
        ),

        "with_date": sum(
            1
            for a in articles
            if a.get("date")
        ),
    }


# ============================================================
# TEST DIRECT
# ============================================================

if __name__ == "__main__":

    print("=" * 80)
    print("CGI MEDIA MONITOR - GDELT TEST")
    print("=" * 80)

    articles = collect_gdelt_articles(
        queries=[
            '"CGI" Maroc',
        ],
        timespan="30d",
        max_records=20,
    )

    stats = get_gdelt_statistics(
        articles
    )

    print()
    print(
        f"Articles      : {stats['total']}"
    )

    print(
        f"Avec titre    : {stats['with_title']}"
    )

    print(
        f"Avec URL      : {stats['with_url']}"
    )

    print(
        f"Avec source   : {stats['with_source']}"
    )

    print(
        f"Avec date     : {stats['with_date']}"
    )

    print()

    for i, article in enumerate(
        articles[:10],
        1,
    ):

        print("-" * 80)

        print(
            f"{i}. "
            f"{article['title']}"
        )

        print(
            f"Source : "
            f"{article['source']}"
        )

        print(
            f"Date   : "
            f"{article['date']}"
        )

        print(
            f"URL    : "
            f"{article['url']}"
        )