# ============================================================
# CGI MEDIA MONITOR
# NEWSDATA.IO SOURCE
#
# Source primaire :
#     NewsData.io
#
# IMPORTANT :
# - Aucun scraping média
# - Aucun accès SQLite
# - Aucun sentiment ici
# - GPT-OSS reste responsable de la pertinence/sentiment
# ============================================================

from __future__ import annotations

import html
import os
import re
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


# ============================================================
# ENV
# ============================================================

load_dotenv()

API_KEY = os.getenv("NEWSDATA_API_KEY")

API_URL = "https://newsdata.io/api/1/latest"

REQUEST_TIMEOUT = 30


# ============================================================
# REQUÊTES CGI
# ============================================================

CGI_QUERIES = [
    '"Compagnie Générale Immobilière"',
    '"Compagnie Générale Immobilière" Maroc',
    '"CGI" immobilier Maroc',
    '"CGI" CDG Maroc',
    '"CGI" "Bourse de Casablanca"',
    '"CGI" Bouskoura',
    '"CGI" Rabat',
    '"CGI" Casablanca immobilier',
]


# ============================================================
# NETTOYAGE
# ============================================================

def clean_text(value: Any) -> str:
    """
    Nettoie un texte provenant de NewsData.io.
    """

    if value is None:
        return ""

    text = str(value)

    text = html.unescape(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# CONFIGURATION
# ============================================================

def check_api_key() -> None:
    """
    Vérifie que la clé API existe.
    """

    if not API_KEY:

        raise RuntimeError(
            "NEWSDATA_API_KEY introuvable. "
            "Vérifie le fichier .env."
        )


# ============================================================
# REQUÊTE
# ============================================================

def fetch_newsdata(
    query: str,
    language: str = "fr",
    country: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Interroge NewsData.io.

    country est volontairement optionnel.
    Le premier test avec country=ma ne retournait pas
    les résultats CGI attendus.
    """

    check_api_key()

    params = {
        "apikey": API_KEY,
        "q": query,
        "language": language,
    }

    if country:
        params["country"] = country

    headers = {
        "User-Agent": (
            "CGI-Media-Monitor/1.0"
        ),
        "Accept": "application/json",
    }

    response = requests.get(
        API_URL,
        params=params,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    # --------------------------------------------------------
    # Erreur HTTP
    # --------------------------------------------------------

    if response.status_code != 200:

        try:
            error_data = response.json()
        except Exception:
            error_data = response.text[:1000]

        raise RuntimeError(
            f"NewsData HTTP {response.status_code}: "
            f"{error_data}"
        )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    try:

        data = response.json()

    except Exception as exc:

        raise RuntimeError(
            "NewsData.io n'a pas retourné un JSON valide."
        ) from exc

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if data.get("status") != "success":

        raise RuntimeError(
            f"Réponse NewsData inattendue : {data}"
        )

    return data


# ============================================================
# EXTRACTION
# ============================================================

def normalize_article(
    item: Dict[str, Any],
    query: str,
) -> Optional[Dict[str, Any]]:
    """
    Convertit un article NewsData.io
    vers le format CGI Media Monitor.
    """

    title = clean_text(
        item.get("title")
        or ""
    )

    url = clean_text(
        item.get("link")
        or ""
    )

    description = clean_text(
        item.get("description")
        or ""
    )

    source = clean_text(
        item.get("source_name")
        or item.get("source_id")
        or ""
    )

    pub_date = clean_text(
        item.get("pubDate")
        or ""
    )

    creator = item.get("creator")

    if isinstance(
        creator,
        list,
    ):

        creator = ", ".join(
            clean_text(x)
            for x in creator
            if clean_text(x)
        )

    else:

        creator = clean_text(
            creator or ""
        )

    if not title or not url:
        return None

    return {

        # ----------------------------------------------------
        # Champs standards du projet
        # ----------------------------------------------------

        "title": title,

        "summary": description,

        "description": description,

        "content": "",

        "source": source,

        "date": pub_date,

        "published_at": pub_date,

        "url": url,

        "query": query,

        # ----------------------------------------------------
        # Métadonnées
        # ----------------------------------------------------

        "input_mode": (
            "NEWSDATA_DESCRIPTION"
            if description
            else "NEWSDATA_TITLE"
        ),

        "collection_source": "NEWSDATA",

        "creator": creator,

        "image_url": clean_text(
            item.get("image_url")
            or ""
        ),

        "category": clean_text(
            item.get("category")
            or ""
        ),

        "language": clean_text(
            item.get("language")
            or ""
        ),

        "country": clean_text(
            item.get("country")
            or ""
        ),

        "keywords": item.get(
            "keywords"
            or []
        ),

        "video_url": clean_text(
            item.get("video_url")
            or ""
        ),

        # Article original conservé
        "newsdata_raw": item,
    }


# ============================================================
# DÉDUPLICATION
# ============================================================

def normalize_url(
    url: str,
) -> str:

    url = clean_text(url)

    if not url:
        return ""

    return url.lower().rstrip("/")


def normalize_title(
    title: str,
) -> str:

    title = clean_text(title)

    title = title.lower()

    title = re.sub(
        r"[^\w\s]",
        " ",
        title,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


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

        title = normalize_title(
            article.get("title", "")
        )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        if url:

            if url in seen_urls:
                continue

            seen_urls.add(url)

        # ----------------------------------------------------
        # Titre
        # ----------------------------------------------------

        if title:

            if title in seen_titles:
                continue

            seen_titles.add(title)

        result.append(article)

    return result


# ============================================================
# COLLECTE
# ============================================================

def collect_newsdata_articles(
    queries: Optional[List[str]] = None,
    language: str = "fr",
) -> List[Dict[str, Any]]:
    """
    Collecte les articles avec plusieurs requêtes ciblées.
    """

    if queries is None:

        queries = CGI_QUERIES

    all_articles = []

    print()
    print("=" * 80)
    print("NEWSDATA.IO - COLLECTE")
    print("=" * 80)

    for index, query in enumerate(
        queries,
        1,
    ):

        print()
        print(
            f"[{index}/{len(queries)}] "
            f"Recherche : {query}"
        )

        try:

            data = fetch_newsdata(
                query=query,
                language=language,
            )

            results = data.get(
                "results",
                [],
            )

            print(
                f"    Résultats : "
                f"{len(results)}"
            )

            for item in results:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                article = normalize_article(
                    item,
                    query=query,
                )

                if article:
                    all_articles.append(
                        article
                    )

        except Exception as exc:

            print(
                f"    [ERREUR] {exc}"
            )

    # --------------------------------------------------------
    # Déduplication
    # --------------------------------------------------------

    before = len(
        all_articles
    )

    articles = deduplicate_articles(
        all_articles
    )

    after = len(articles)

    print()
    print(
        f"Articles avant déduplication : "
        f"{before}"
    )

    print(
        f"Articles après déduplication : "
        f"{after}"
    )

    print("=" * 80)

    return articles


# ============================================================
# STATISTIQUES
# ============================================================

def get_newsdata_statistics(
    articles: List[Dict[str, Any]],
) -> Dict[str, int]:

    total = len(articles)

    with_description = sum(
        1
        for article in articles
        if clean_text(
            article.get(
                "description",
                "",
            )
        )
    )

    without_description = (
        total - with_description
    )

    return {

        "total": total,

        "with_description":
            with_description,

        "without_description":
            without_description,

    }


# ============================================================
# TEST DIRECT
# ============================================================

if __name__ == "__main__":

    print(
        "Test NewsData.io"
    )

    articles = (
        collect_newsdata_articles()
    )

    stats = (
        get_newsdata_statistics(
            articles
        )
    )

    print()

    print(
        "Articles :",
        stats["total"],
    )

    print(
        "Avec description :",
        stats["with_description"],
    )

    print(
        "Sans description :",
        stats["without_description"],
    )

    print()

    for index, article in enumerate(
        articles[:10],
        1,
    ):

        print("-" * 80)

        print(
            index,
            article["title"],
        )

        print(
            "Source :",
            article["source"],
        )

        print(
            "Description :",
            article["description"][:300],
        )

        print(
            "URL :",
            article["url"],
        )