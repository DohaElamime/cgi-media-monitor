# -*- coding: utf-8 -*-
"""
CGI Media Monitor - RSS-first dry-run

Aucune modification SQLite.
Le scraping des pages médias est volontairement désactivé.

Flux:
RSS Google News
 -> title + summary + source + date + URL
 -> pré-filtre
 -> pertinence GPT
 -> sentiment GPT-OSS
 -> CSV
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from modules.rss_ingestion import (
    collect_rss_articles,
    is_usable_summary,
)

from modules.ai_classifier import is_relevant_ai
from modules.pre_filter import is_article_candidate
from modules.sentiment_analysis import analyze_cgi_sentiment


OUTPUT = Path("rss_first_dryrun_results.csv")
ERRORS = Path("rss_first_dryrun_errors.csv")

# Si config.py contient SEARCH_QUERIES, elles sont utilisées.
try:
    from config import SEARCH_QUERIES
    QUERIES = list(SEARCH_QUERIES)
except Exception:
    QUERIES = [
        '"Compagnie Générale Immobilière"',
        '"Compagnie Générale Immobilière Maroc"',
        '"CGI Maroc"',
        '"CGI immobilier"',
        '"CGI" promoteur immobilier',
        '"CGI" immobilier Maroc',
        '"CDG Développement" CGI',
    ]


def clean(value):
    return str(value or "").strip()


def safe_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower().strip() in {
            "true", "1", "yes", "oui", "vrai"
        }
    return bool(value)


def save_csv(rows, path):
    if not rows:
        return

    fields = [
        "index", "title", "source", "date", "url", "summary",
        "content_length", "input_mode", "relevant",
        "sentiment", "score", "confidence", "margin",
        "review", "content_mismatch", "reason",
        "model", "device", "timestamp",
    ]

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    print("=" * 80)
    print("CGI MEDIA MONITOR - RSS FIRST / DRY RUN")
    print("=" * 80)
    print("SQLite : AUCUNE MODIFICATION")
    print("Scraping média : DÉSACTIVÉ")
    print("Source primaire : GOOGLE NEWS RSS")
    print()

    articles = collect_rss_articles(
        queries=QUERIES,
        max_per_query=100,
    )

    print()
    print(f"Articles RSS après déduplication : {len(articles)}")

    rows = []
    errors = []

    summary_count = 0
    no_summary_count = 0
    relevant_count = 0
    analyzed_count = 0
    positive = 0
    negative = 0
    neutral = 0
    reviews = 0
    prefilter_rejected = 0
    relevance_errors = 0
    sentiment_errors = 0

    for index, article in enumerate(articles, start=1):
        title = clean(article.get("title"))
        summary = clean(article.get("summary"))
        source = clean(article.get("source"))
        date = clean(article.get("date"))
        url = clean(article.get("url"))

        if is_usable_summary(summary):
            summary_count += 1
        else:
            no_summary_count += 1

        # Le pré-filtre reste autorisé, mais aucune extraction web n'est appelée.
        try:
            if not is_article_candidate(article):
                prefilter_rejected += 1
                continue
        except Exception as exc:
            errors.append({
                "index": index,
                "title": title,
                "url": url,
                "error_type": "pre_filter",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            })
            continue

        # Entrée IA: résumé RSS si disponible, sinon titre.
        relevance_text = summary or title

        if not relevance_text:
            errors.append({
                "index": index,
                "title": title,
                "url": url,
                "error_type": "no_rss_metadata",
                "error": "Titre et résumé RSS absents.",
                "timestamp": datetime.now().isoformat(),
            })
            continue

        try:
            relevant = is_relevant_ai(
                content=relevance_text,
                title=title,
                summary=summary,
                url=url,
            )
        except Exception as exc:
            relevance_errors += 1
            errors.append({
                "index": index,
                "title": title,
                "url": url,
                "error_type": "relevance",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            })
            continue

        if not relevant:
            continue

        relevant_count += 1

        # IMPORTANT:
        # content reste vide. On ne transforme pas le résumé RSS en faux article.
        try:
            sentiment_result = analyze_cgi_sentiment(
                title=title,
                summary=summary,
                content="",
            )
        except Exception as exc:
            sentiment_errors += 1
            errors.append({
                "index": index,
                "title": title,
                "url": url,
                "error_type": "sentiment",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            })
            continue

        sentiment = clean(
            sentiment_result.get("sentiment", "REVIEW")
        )

        review = safe_bool(
            sentiment_result.get("review", False)
        )

        if review:
            reviews += 1

        if sentiment == "Positive":
            positive += 1
        elif sentiment == "Negative":
            negative += 1
        elif sentiment == "Neutral":
            neutral += 1

        analyzed_count += 1

        rows.append({
            "index": index,
            "title": title,
            "source": source,
            "date": date,
            "url": url,
            "summary": summary,
            "content_length": 0,
            "input_mode": "RSS_SUMMARY" if summary else "TITLE_ONLY",
            "relevant": True,
            "sentiment": sentiment,
            "score": sentiment_result.get("score", 0.0),
            "confidence": sentiment_result.get("confidence", 0.0),
            "margin": sentiment_result.get("margin", 0.0),
            "review": review,
            "content_mismatch": safe_bool(
                sentiment_result.get("content_mismatch", False)
            ),
            "reason": clean(sentiment_result.get("reason", "")),
            "model": clean(sentiment_result.get("model", "")),
            "device": clean(sentiment_result.get("device", "")),
            "timestamp": datetime.now().isoformat(),
        })

        print(
            f"[{index}/{len(articles)}] "
            f"{sentiment:8} | {source[:25]:25} | {title[:70]}"
        )

    save_csv(rows, OUTPUT)
    save_csv(errors, ERRORS)

    print()
    print("=" * 80)
    print("FIN DU DRY-RUN RSS-FIRST")
    print("=" * 80)
    print(f"Articles RSS                 : {len(articles)}")
    print(f"Résumé RSS utilisable        : {summary_count}")
    print(f"Sans résumé RSS              : {no_summary_count}")
    print(f"Rejetés pré-filtre           : {prefilter_rejected}")
    print(f"Articles pertinents          : {relevant_count}")
    print(f"Articles analysés            : {analyzed_count}")
    print()
    print(f"Positive                     : {positive}")
    print(f"Negative                     : {negative}")
    print(f"Neutral                      : {neutral}")
    print(f"REVIEW                       : {reviews}")
    print()
    print(f"Erreurs pertinence           : {relevance_errors}")
    print(f"Erreurs sentiment            : {sentiment_errors}")
    print()
    print(f"Résultats CSV                : {OUTPUT}")
    print(f"Erreurs CSV                  : {ERRORS}")
    print("SQLite                       : AUCUNE MODIFICATION")


if __name__ == "__main__":
    main()
