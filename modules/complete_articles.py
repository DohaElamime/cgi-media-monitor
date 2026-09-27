# -*- coding: utf-8 -*-

import os
import sys
import sqlite3
import traceback


# ============================================================
# RACINE PROJET
# ============================================================

ROOT_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# ============================================================
# IMPORTS
# ============================================================

from config import DATABASE_PATH

from modules.article_extractor import extract_article
from modules.sources.google_news_source import get_real_url
from modules.ai_classifier import is_relevant_ai
from modules.sentiment_analysis import analyze_sentiment


# ============================================================
# HELPERS
# ============================================================

def has_value(value):
    return value is not None and str(value).strip() != ""


def article_complete(row):
    """
    0 et 0.0 sont des valeurs valides.
    On teste uniquement NULL / vide.
    """

    return (
        has_value(row["content"])
        and row["relevant"] is not None
        and row["confidence"] is not None
        and has_value(row["sentiment"])
        and row["sentiment_score"] is not None
    )


# ============================================================
# MAIN
# ============================================================

def complete_articles():

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM articles
        WHERE
            content IS NULL
            OR TRIM(content) = ''
            OR relevant IS NULL
            OR confidence IS NULL
            OR sentiment IS NULL
            OR TRIM(sentiment) = ''
            OR sentiment_score IS NULL
        ORDER BY id ASC
        """
    )

    articles = cursor.fetchall()

    print()
    print("=" * 70)
    print("RÉPARATION DES ARTICLES INCOMPLETS")
    print("=" * 70)
    print(
        "Articles à traiter :",
        len(articles)
    )

    completed = 0
    failed = 0
    extracted = 0
    relevance_done = 0
    sentiment_done = 0

    for index, article in enumerate(
        articles,
        1
    ):

        article_id = article["id"]
        title = article["title"] or ""
        source = article["source"] or ""
        google_url = article["url"] or ""

        print()
        print("-" * 70)
        print(
            f"[{index}/{len(articles)}] "
            f"ID={article_id}"
        )
        print(title)

        try:

            # ==================================================
            # 1. CONTENT
            # ==================================================

            content = (
                article["content"]
                if has_value(article["content"])
                else ""
            )

            if not content:

                print("[1] Contenu absent")

                real_url = get_real_url(
                    google_url,
                    title,
                    source
                )

                if not real_url:

                    print(
                        "[X] URL réelle introuvable"
                    )

                    failed += 1
                    continue

                print(
                    "[URL]",
                    real_url
                )

                content = extract_article(
                    real_url
                )

                if not content:

                    print(
                        "[X] Extraction impossible"
                    )

                    failed += 1
                    continue

                content = content.strip()

                cursor.execute(
                    """
                    UPDATE articles
                    SET content = ?
                    WHERE id = ?
                    """,
                    (
                        content,
                        article_id
                    )
                )

                conn.commit()

                extracted += 1

                print(
                    "[OK] Contenu :",
                    len(content),
                    "caractères"
                )

            else:

                content = content.strip()

                print(
                    "[1] Contenu déjà présent :",
                    len(content),
                    "caractères"
                )

            # ==================================================
            # 2. PERTINENCE + CONFIANCE
            # ==================================================

            relevant = article["relevant"]
            confidence = article["confidence"]

            if (
                relevant is None
                or confidence is None
            ):

                print(
                    "[2] Analyse pertinence..."
                )

                result = is_relevant_ai(
                    content
                )

                if not isinstance(
                    result,
                    tuple
                ):

                    raise ValueError(
                        "is_relevant_ai() doit retourner "
                        "(relevant, confidence, label)"
                    )

                if len(result) < 2:

                    raise ValueError(
                        "Résultat IA invalide"
                    )

                relevant = bool(
                    result[0]
                )

                confidence = float(
                    result[1]
                )

                label = (
                    result[2]
                    if len(result) >= 3
                    else ""
                )

                cursor.execute(
                    """
                    UPDATE articles
                    SET
                        relevant = ?,
                        confidence = ?
                    WHERE id = ?
                    """,
                    (
                        int(relevant),
                        confidence,
                        article_id
                    )
                )

                conn.commit()

                relevance_done += 1

                print(
                    "[OK] Pertinence =",
                    label
                )

                print(
                    "[OK] Confiance =",
                    f"{confidence:.2%}"
                )

            else:

                relevant = bool(
                    relevant
                )

                confidence = float(
                    confidence
                )

                print(
                    "[2] Pertinence déjà présente"
                )

            # ==================================================
            # 3. SENTIMENT
            # ==================================================

            sentiment = article["sentiment"]
            sentiment_score = article[
                "sentiment_score"
            ]

            if (
                not has_value(sentiment)
                or sentiment_score is None
            ):

                print(
                    "[3] Analyse sentiment..."
                )

                result = analyze_sentiment(
                    content
                )

                if not isinstance(
                    result,
                    dict
                ):

                    raise ValueError(
                        "analyze_sentiment() "
                        "doit retourner un dict"
                    )

                sentiment = str(
                    result.get(
                        "sentiment",
                        ""
                    )
                ).strip()

                sentiment_score = float(
                    result.get(
                        "score",
                        0.0
                    )
                )

                if not sentiment:

                    raise ValueError(
                        "Sentiment vide"
                    )

                cursor.execute(
                    """
                    UPDATE articles
                    SET
                        sentiment = ?,
                        sentiment_score = ?
                    WHERE id = ?
                    """,
                    (
                        sentiment,
                        sentiment_score,
                        article_id
                    )
                )

                conn.commit()

                sentiment_done += 1

                print(
                    "[OK] Sentiment =",
                    sentiment
                )

                print(
                    "[OK] Score =",
                    f"{sentiment_score:.2%}"
                )

            else:

                sentiment = str(
                    sentiment
                ).strip()

                sentiment_score = float(
                    sentiment_score
                )

                print(
                    "[3] Sentiment déjà présent"
                )

            # ==================================================
            # 4. VÉRIFICATION FINALE
            # ==================================================

            cursor.execute(
                """
                SELECT
                    content,
                    relevant,
                    confidence,
                    sentiment,
                    sentiment_score
                FROM articles
                WHERE id = ?
                """,
                (article_id,)
            )

            updated = cursor.fetchone()

            if updated and article_complete(
                updated
            ):

                completed += 1

                print(
                    "[OK] ARTICLE COMPLÈTEMENT ANALYSÉ"
                )

            else:

                failed += 1

                print(
                    "[X] ARTICLE ENCORE INCOMPLET"
                )

        except Exception as exc:

            failed += 1

            print()
            print(
                "[X] ERREUR :",
                exc
            )

            traceback.print_exc()

            # Continuer avec l'article suivant
            continue

    # ========================================================
    # STATISTIQUES RÉELLES
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        """
    )

    total = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE content IS NOT NULL
          AND TRIM(content) != ''
        """
    )

    with_content = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE relevant IS NOT NULL
        """
    )

    with_relevance = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE confidence IS NOT NULL
        """
    )

    with_confidence = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE sentiment IS NOT NULL
          AND TRIM(sentiment) != ''
        """
    )

    with_sentiment = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE content IS NOT NULL
          AND TRIM(content) != ''
          AND relevant IS NOT NULL
          AND confidence IS NOT NULL
          AND sentiment IS NOT NULL
          AND TRIM(sentiment) != ''
          AND sentiment_score IS NOT NULL
        """
    )

    fully_analyzed = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE relevant = 1
        """
    )

    relevant_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT sentiment, COUNT(*) AS total
        FROM articles
        GROUP BY sentiment
        ORDER BY total DESC
        """
    )

    sentiments = cursor.fetchall()

    conn.close()

    # ========================================================
    # RAPPORT
    # ========================================================

    print()
    print("=" * 70)
    print("RÉSULTAT")
    print("=" * 70)

    print(
        "Articles traités       :",
        len(articles)
    )

    print(
        "Contenus extraits      :",
        extracted
    )

    print(
        "Analyses pertinence    :",
        relevance_done
    )

    print(
        "Analyses sentiment     :",
        sentiment_done
    )

    print(
        "Complètement terminés  :",
        completed
    )

    print(
        "Échecs                 :",
        failed
    )

    print()
    print("=" * 70)
    print("ÉTAT RÉEL DE LA BASE")
    print("=" * 70)

    print(
        "Total                  :",
        total
    )

    print(
        "Avec contenu           :",
        with_content
    )

    print(
        "Avec pertinence        :",
        with_relevance
    )

    print(
        "Avec confiance         :",
        with_confidence
    )

    print(
        "Avec sentiment         :",
        with_sentiment
    )

    print(
        "Complètement analysés  :",
        fully_analyzed
    )

    print(
        "Articles pertinents    :",
        relevant_count
    )

    print()
    print("Sentiments :")

    for row in sentiments:

        value = row["sentiment"]

        if not has_value(value):
            value = "(vide)"

        print(
            f"  {value} : {row['total']}"
        )

    print()
    print("=" * 70)
    print("TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    complete_articles()