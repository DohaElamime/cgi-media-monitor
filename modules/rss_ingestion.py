# modules/rss_ingestion.py
# ============================================================
# CGI MEDIA MONITOR - RSS FIRST
# Source primaire : Google News RSS
#
# IMPORTANT :
# - Aucun scraping des pages médias
# - Aucun accès SQLite
# - Le RSS fournit titre / résumé / source / date / URL
# - Le contenu complet est optionnel et n'est PAS nécessaire
# ============================================================

from __future__ import annotations

import re
import html
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests
import feedparser


# ============================================================
# CONFIGURATION
# ============================================================

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

REQUEST_TIMEOUT = 30

MIN_SUMMARY_CHARS = 80
MIN_SUMMARY_WORDS = 12
MIN_NEW_SUMMARY_WORDS = 5

GENERIC_GOOGLE_SUMMARY = (
    "Informations complètes et à jour, compilées par Google Actualités "
    "à partir de sources d'actualités du monde entier"
)


# ============================================================
# TEXTE
# ============================================================

def clean_text(value: Any) -> str:
    """
    Nettoie un texte RSS/XML/HTML.
    """
    if value is None:
        return ""

    text = str(value)

    # Décodage HTML
    text = html.unescape(text)

    # Suppression HTML
    text = re.sub(r"<[^>]+>", " ", text)

    # Espaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_for_comparison(text: str) -> str:
    """
    Normalisation utilisée uniquement pour comparer
    titre et résumé.
    """
    text = clean_text(text).lower()

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        c for c in text
        if not unicodedata.combining(c)
    )

    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text: str) -> List[str]:
    """
    Retourne les mots significatifs.
    """
    normalized = normalize_for_comparison(text)

    if not normalized:
        return []

    return [
        word
        for word in normalized.split()
        if len(word) >= 2
    ]


# ============================================================
# VALIDATION DU RÉSUMÉ RSS
# ============================================================

def is_generic_google_summary(summary: str) -> bool:
    """
    Détecte le faux résumé générique de Google News.
    """
    normalized = normalize_for_comparison(summary)
    generic = normalize_for_comparison(GENERIC_GOOGLE_SUMMARY)

    if not normalized:
        return False

    return (
        normalized == generic
        or generic in normalized
    )


def summary_contains_real_information(
    summary: str,
    title: str = "",
) -> bool:
    """
    Vérifie que le résumé contient réellement des informations
    qui ne sont pas simplement une répétition du titre.

    Ce n'est PAS une classification de sentiment.
    """

    summary_words = set(tokenize(summary))
    title_words = set(tokenize(title))

    if not summary_words:
        return False

    # Mots réellement nouveaux par rapport au titre
    new_words = summary_words - title_words

    if len(new_words) < MIN_NEW_SUMMARY_WORDS:
        return False

    # Si presque tout le résumé est déjà dans le titre,
    # ce n'est probablement pas un vrai résumé.
    overlap = len(summary_words & title_words) / len(summary_words)

    if overlap >= 0.95:
        return False

    return True


def is_usable_summary(
    summary: str,
    title: str = "",
    source: str = "",
) -> bool:
    """
    Détermine si le texte RSS peut être utilisé comme
    véritable résumé d'article.

    Compatible avec l'ancien appel :
        is_usable_summary(summary)
    """

    summary = clean_text(summary)
    title = clean_text(title)
    source = clean_text(source)

    if not summary:
        return False

    if is_generic_google_summary(summary):
        return False

    if len(summary) < MIN_SUMMARY_CHARS:
        return False

    if len(tokenize(summary)) < MIN_SUMMARY_WORDS:
        return False

    normalized_summary = normalize_for_comparison(summary)
    normalized_title = normalize_for_comparison(title)
    normalized_source = normalize_for_comparison(source)

    # --------------------------------------------------------
    # Cas 1 : résumé = exactement le titre
    # --------------------------------------------------------

    if normalized_title and normalized_summary == normalized_title:
        return False

    # --------------------------------------------------------
    # Cas 2 : "Titre - Source"
    # ou "Titre | Source"
    # ou "Titre — Source"
    # --------------------------------------------------------

    if normalized_title:
        without_source = normalized_summary

        if normalized_source:
            without_source = re.sub(
                rf"\s*[-|–—:]\s*{re.escape(normalized_source)}$",
                "",
                without_source,
            ).strip()

        if without_source == normalized_title:
            return False

    # --------------------------------------------------------
    # Cas 3 : résumé presque entièrement identique au titre
    # --------------------------------------------------------

    if normalized_title:
        summary_words = set(tokenize(summary))
        title_words = set(tokenize(title))

        if summary_words:
            overlap = len(summary_words & title_words) / len(summary_words)

            if overlap >= 0.95:
                return False

    # --------------------------------------------------------
    # Cas 4 : vérifier qu'il existe une vraie information
    # supplémentaire
    # --------------------------------------------------------

    if not summary_contains_real_information(
        summary,
        title=title,
    ):
        return False

    return True


# ============================================================
# EXTRACTION DES CHAMPS RSS
# ============================================================

def get_entry_title(entry: Any) -> str:
    """
    Titre RSS.
    """
    return clean_text(
        getattr(entry, "title", "")
        or entry.get("title", "")
    )


def get_entry_link(entry: Any) -> str:
    """
    URL RSS.
    """
    link = (
        getattr(entry, "link", "")
        or entry.get("link", "")
    )

    return clean_text(link)


def get_entry_source(entry: Any) -> str:
    """
    Source média.
    """

    # Google News expose généralement <source>
    source = entry.get("source")

    if isinstance(source, dict):
        return clean_text(
            source.get("title")
            or source.get("name")
            or ""
        )

    if source:
        return clean_text(source)

    # Certains flux peuvent avoir source.title
    try:
        source_obj = getattr(entry, "source", None)

        if source_obj:
            return clean_text(
                getattr(source_obj, "title", "")
                or ""
            )
    except Exception:
        pass

    return ""


def get_entry_date(entry: Any) -> str:
    """
    Date RSS.
    """

    value = (
        entry.get("published")
        or entry.get("updated")
        or ""
    )

    return clean_text(value)


def get_entry_summary(entry: Any) -> str:
    """
    Récupère le vrai contenu disponible dans le RSS.

    Priorité :
    1. content:encoded
    2. summary
    3. description
    """

    # --------------------------------------------------------
    # content:encoded
    # --------------------------------------------------------

    try:
        content = entry.get("content")

        if content and isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    value = item.get("value", "")

                    if value:
                        value = clean_text(value)

                        if value:
                            return value
    except Exception:
        pass

    # --------------------------------------------------------
    # summary
    # --------------------------------------------------------

    summary = entry.get("summary", "")

    if summary:
        summary = clean_text(summary)

        if summary:
            return summary

    # --------------------------------------------------------
    # description
    # --------------------------------------------------------

    description = entry.get("description", "")

    if description:
        description = clean_text(description)

        if description:
            return description

    return ""


# ============================================================
# DATE
# ============================================================

def parse_date(value: str) -> Optional[str]:
    """
    Normalise autant que possible la date RSS.

    On conserve la chaîne originale si le parsing échoue.
    """

    value = clean_text(value)

    if not value:
        return None

    try:
        parsed = feedparser._parse_date(value)

        if parsed:
            dt = datetime(*parsed[:6])
            return dt.isoformat(sep=" ")

    except Exception:
        pass

    return value


# ============================================================
# RSS
# ============================================================

def build_google_news_url(
    query: str,
    language: str = "fr",
    country: str = "MA",
) -> str:
    """
    Construit une URL Google News RSS.
    """

    encoded_query = quote_plus(query)

    return (
        f"{GOOGLE_NEWS_RSS_URL}"
        f"?q={encoded_query}"
        f"&hl={language}"
        f"&gl={country}"
        f"&ceid={country}:{language}"
    )


def fetch_rss(
    query: str,
    language: str = "fr",
    country: str = "MA",
) -> List[Dict[str, Any]]:
    """
    Télécharge et parse un flux Google News RSS.
    """

    url = build_google_news_url(
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
            "application/xml, text/xml;q=0.9, */*;q=0.8"
        ),
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    parsed = feedparser.parse(response.content)

    if getattr(parsed, "bozo", False):
        # On ne bloque pas systématiquement :
        # feedparser peut signaler des anomalies bénignes.
        pass

    return list(parsed.entries)


# ============================================================
# PARSING
# ============================================================

def parse_rss_entries(
    entries: List[Any],
    query: str = "",
) -> List[Dict[str, Any]]:
    """
    Transforme les entrées RSS en articles normalisés.
    """

    articles: List[Dict[str, Any]] = []

    for entry in entries:

        title = get_entry_title(entry)
        link = get_entry_link(entry)
        source = get_entry_source(entry)
        raw_summary = get_entry_summary(entry)
        date = parse_date(get_entry_date(entry))

        if not title or not link:
            continue

        # ----------------------------------------------------
        # IMPORTANT :
        # Le résumé brut est conservé.
        # La validation est faite ensuite.
        # ----------------------------------------------------

        usable_summary = ""

        if is_usable_summary(
            raw_summary,
            title=title,
            source=source,
        ):
            usable_summary = raw_summary

        article = {
            "title": title,
            "summary": usable_summary,
            "description": usable_summary,
            "source": source,
            "date": date,
            "url": link,
            "query": query,

            # Métadonnées utiles au dry-run
            "rss_summary_raw": raw_summary,
            "rss_summary_usable": bool(usable_summary),
            "input_mode": (
                "RSS_SUMMARY"
                if usable_summary
                else "TITLE_ONLY"
            ),
        }

        articles.append(article)

    return articles


# ============================================================
# DÉDOUBLONNAGE
# ============================================================

def deduplicate_articles(
    articles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Déduplication par URL puis par titre.
    """

    result = []

    seen_urls = set()
    seen_titles = set()

    for article in articles:

        url = clean_text(article.get("url", ""))
        title = normalize_for_comparison(
            article.get("title", "")
        )

        # URL
        if url:
            if url in seen_urls:
                continue

            seen_urls.add(url)

        # Titre
        if title:
            if title in seen_titles:
                continue

            seen_titles.add(title)

        result.append(article)

    return result


# ============================================================
# COLLECTE PRINCIPALE
# ============================================================

def collect_rss_articles(
    queries: Optional[List[str]] = None,
    query: Optional[str] = None,
    language: str = "fr",
    country: str = "MA",
    max_per_query: int = 100,
) -> List[Dict[str, Any]]:
    """
    Collecte les articles depuis Google News RSS.

    Compatible avec :

        collect_rss_articles(
            queries=[...]
        )

    et :

        collect_rss_articles(
            query="..."
        )
    """

    # --------------------------------------------------------
    # Compatibilité query / queries
    # --------------------------------------------------------

    if queries is None:
        queries = []

    if query:
        queries = list(queries) + [query]

    # Si aucun query n'est fourni
    if not queries:
        queries = [
            "CGI Maroc",
            '"CGI" immobilier Maroc',
            '"Compagnie Générale Immobilière" Maroc',
        ]

    # Évite les doublons de requêtes
    unique_queries = []

    for q in queries:
        q = clean_text(q)

        if q and q not in unique_queries:
            unique_queries.append(q)

    all_articles: List[Dict[str, Any]] = []

    for current_query in unique_queries:

        try:
            entries = fetch_rss(
                query=current_query,
                language=language,
                country=country,
            )

            # Limitation locale
            entries = entries[:max_per_query]

            parsed_articles = parse_rss_entries(
                entries,
                query=current_query,
            )

            all_articles.extend(parsed_articles)

        except Exception as exc:

            print(
                f"[RSS ERROR] "
                f"query={current_query!r} "
                f"error={exc}"
            )

    return deduplicate_articles(all_articles)


# ============================================================
# STATISTIQUES
# ============================================================

def get_rss_statistics(
    articles: List[Dict[str, Any]],
) -> Dict[str, int]:

    total = len(articles)

    usable_summary = sum(
        1
        for article in articles
        if article.get("rss_summary_usable")
    )

    without_summary = total - usable_summary

    return {
        "total": total,
        "usable_summary": usable_summary,
        "without_summary": without_summary,
    }


# ============================================================
# TEST DIRECT
# ============================================================

if __name__ == "__main__":

    print("=" * 80)
    print("TEST GOOGLE NEWS RSS")
    print("=" * 80)

    articles = collect_rss_articles(
        queries=[
            '"CGI" Maroc immobilier',
        ],
        max_per_query=20,
    )

    stats = get_rss_statistics(articles)

    print()
    print(f"Articles : {stats['total']}")
    print(f"Résumés utilisables : {stats['usable_summary']}")
    print(f"Sans résumé : {stats['without_summary']}")
    print()

    for i, article in enumerate(articles[:10], 1):

        print("-" * 80)
        print(f"{i}. {article['title']}")
        print(f"Source : {article['source']}")
        print(f"Mode   : {article['input_mode']}")
        print(
            f"Résumé : "
            f"{article['summary'][:300]}"
        )