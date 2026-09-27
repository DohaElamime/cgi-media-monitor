# ============================================================
# CGI MEDIA MONITOR - GOOGLE NEWS SOURCE V2
#
# RSS = SOURCE DE DECOUVERTE
# Pas de SQLite
# Pas de sentiment
# Pas de dépendance au résumé RSS
#
# Le collecteur récupère :
#   - titre
#   - URL
#   - source
#   - date
#   - résumé RSS s'il existe
#
# L'extraction du média est volontairement séparée.
# ============================================================

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import feedparser
import requests


GOOGLE_NEWS_URL = "https://news.google.com/rss/search"

REQUEST_TIMEOUT = 30

DEFAULT_LANGUAGE = "fr"
DEFAULT_COUNTRY = "MA"

# Requêtes de découverte.
#
# On évite de mettre seulement "CGI", car CGI peut désigner
# beaucoup d'autres choses.
QUERIES = [
    '"Compagnie Générale Immobilière"',
    '"Compagnie Générale Immobilière" Maroc',
    '"CGI" immobilier Maroc',
    '"CGI" CDG Maroc',
    '"CGI" Bourse Casablanca',
    '"CGI" Bouskoura',
    '"CGI" Rabat',
    '"CGI" Casablanca immobilier',
]


# ============================================================
# NETTOYAGE
# ============================================================

def clean_text(value: Any) -> str:
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


def normalize_title(title: str) -> str:
    title = clean_text(title).lower()

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


def normalize_url(url: str) -> str:
    return clean_text(url).lower().rstrip("/")


# ============================================================
# DATE
# ============================================================

def parse_date(value: Any) -> Optional[str]:
    value = clean_text(value)

    if not value:
        return None

    try:
        parsed = feedparser._parse_date(value)

        if parsed:
            dt = datetime(*parsed[:6])

            return dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    except Exception:
        pass

    return value


# ============================================================
# RSS
# ============================================================

def build_rss_url(
    query: str,
    language: str = DEFAULT_LANGUAGE,
    country: str = DEFAULT_COUNTRY,
) -> str:

    return (
        f"{GOOGLE_NEWS_URL}"
        f"?q={quote_plus(query)}"
        f"&hl={language}"
        f"&gl={country}"
        f"&ceid={country}:{language}"
    )


def fetch_feed(
    query: str,
    language: str = DEFAULT_LANGUAGE,
    country: str = DEFAULT_COUNTRY,
):

    url = build_rss_url(
        query=query,
        language=language,
        country=country,
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/153 Safari/537.36"
        ),
        "Accept": (
            "application/rss+xml, "
            "application/xml, "
            "text/xml, */*"
        ),
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return feedparser.parse(
        response.content
    )


# ============================================================
# RSS FIELDS
# ============================================================

def get_title(entry: Any) -> str:
    return clean_text(
        entry.get("title", "")
    )


def get_link(entry: Any) -> str:
    return clean_text(
        entry.get("link", "")
    )


def get_source(entry: Any) -> str:

    source = entry.get("source")

    if isinstance(source, dict):

        return clean_text(
            source.get("title")
            or source.get("name")
            or ""
        )

    if source:
        return clean_text(source)

    return ""


def get_date(entry: Any) -> Optional[str]:

    return parse_date(
        entry.get("published")
        or entry.get("updated")
        or ""
    )


def get_summary(entry: Any) -> str:

    # content:encoded
    content = entry.get("content")

    if isinstance(content, list):

        for item in content:

            if isinstance(item, dict):

                value = clean_text(
                    item.get(
                        "value",
                        "",
                    )
                )

                if value:
                    return value

    # summary
    summary = clean_text(
        entry.get(
            "summary",
            "",
        )
    )

    if summary:
        return summary

    # description
    return clean_text(
        entry.get(
            "description",
            "",
        )
    )


# ============================================================
# ARTICLE
# ============================================================

def normalize_entry(
    entry: Any,
    query: str,
) -> Optional[Dict[str, Any]]:

    title = get_title(entry)
    url = get_link(entry)

    if not title or not url:
        return None

    source = get_source(entry)
    date = get_date(entry)
    summary = get_summary(entry)

    return {

        "title": title,

        "url": url,

        "source": source,

        "date": date,

        "published_at": date,

        # Le résumé RSS est optionnel.
        "summary": summary,

        "description": summary,

        # Pas de contenu média à ce stade.
        "content": "",

        "query": query,

        "collection_source":
            "GOOGLE_NEWS_RSS",

        "input_mode":
            "RSS_DISCOVERY",

        "rss_summary_available":
            bool(summary),

    }


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate(
    articles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    result = []

    seen_urls = set()
    seen_titles = set()

    for article in articles:

        url = normalize_url(
            article.get(
                "url",
                "",
            )
        )

        title = normalize_title(
            article.get(
                "title",
                "",
            )
        )

        if url:

            if url in seen_urls:
                continue

            seen_urls.add(url)

        if title:

            if title in seen_titles:
                continue

            seen_titles.add(title)

        result.append(article)

    return result


# ============================================================
# COLLECTE
# ============================================================

def collect_google_news_v2(
    queries: Optional[List[str]] = None,
    language: str = DEFAULT_LANGUAGE,
    country: str = DEFAULT_COUNTRY,
    max_per_query: int = 100,
) -> List[Dict[str, Any]]:

    if queries is None:
        queries = QUERIES

    all_articles = []

    print()
    print("=" * 80)
    print("GOOGLE NEWS V2 - DISCOVERY")
    print("=" * 80)

    for index, query in enumerate(
        queries,
        1,
    ):

        print(
            f"[{index}/{len(queries)}] "
            f"{query}"
        )

        try:

            feed = fetch_feed(
                query=query,
                language=language,
                country=country,
            )

            entries = list(
                feed.entries[
                    :max_per_query
                ]
            )

            print(
                f"    RSS : {len(entries)}"
            )

            for entry in entries:

                article = normalize_entry(
                    entry,
                    query=query,
                )

                if article:
                    all_articles.append(
                        article
                    )

        except Exception as exc:

            print(
                f"    ERREUR : {exc}"
            )

    before = len(
        all_articles
    )

    articles = deduplicate(
        all_articles
    )

    after = len(articles)

    with_summary = sum(
        1
        for article in articles
        if article.get(
            "rss_summary_available"
        )
    )

    print()
    print(
        f"Avant déduplication : {before}"
    )

    print(
        f"Après déduplication : {after}"
    )

    print(
        f"Avec résumé RSS    : {with_summary}"
    )

    print(
        f"Sans résumé RSS    : "
        f"{after - with_summary}"
    )

    print("=" * 80)

    return articles


# ============================================================
# TEST DIRECT
# ============================================================

if __name__ == "__main__":

    articles = collect_google_news_v2()

    print()

    for index, article in enumerate(
        articles[:20],
        1,
    ):

        print("-" * 80)

        print(
            f"{index}. "
            f"{article['title']}"
        )

        print(
            "Source :",
            article["source"],
        )

        print(
            "Date :",
            article["date"],
        )

        print(
            "Résumé RSS :",
            article["rss_summary_available"],
        )

        print(
            "URL :",
            article["url"],
        )