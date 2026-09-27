"""
CGI Media Monitor
Test DRY-RUN des 15 cas litigieux

IMPORTANT :
- Aucune modification de SQLite.
- Utilise le nouveau sentiment_analysis.py.
- Analyse titre + résumé + contenu.
- Sauvegarde uniquement les résultats dans un CSV.
"""

from __future__ import annotations

import csv
import sqlite3
import time
from pathlib import Path

from modules.sentiment_analysis import analyze_cgi_sentiment


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = Path("database/articles.db")

OUTPUT_FILE = Path("test_15_results.csv")

# 15 cas litigieux à retester.
# Ils correspondent aux cas discutés lors de l'audit.
TEST_IDS = [
    196,
    231,
    271,
    314,
    316,
    318,
    321,
    322,
    323,
    325,
    326,
    336,
    337,
    340,
    344,
]


# Références indépendantes disponibles.
# Elles servent uniquement à la comparaison.
# Elles ne sont PAS envoyées au modèle.
REFERENCE = {
    196: "Neutral",
    231: "Neutral",
    271: "Neutral",
    314: "Neutral",
    316: "Positive",
    318: "Neutral",
    321: "Positive",
    322: "Neutral",
    323: "Positive",
    325: "Positive",
    326: "Neutral",
    336: "Negative",
    337: "Negative",
    340: "Negative",
    344: "Positive",
}


# ============================================================
# AFFICHAGE
# ============================================================

def print_separator():
    print("=" * 100)


# ============================================================
# LECTURE SQLITE — READ ONLY
# ============================================================

def get_articles():
    """
    Lit les articles sans aucune écriture SQLite.
    """

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Base SQLite introuvable : {DB_PATH.resolve()}"
        )

    # URI read-only SQLite
    db_uri = f"file:{DB_PATH.resolve().as_posix()}?mode=ro"

    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row

    try:
        placeholders = ",".join("?" for _ in TEST_IDS)

        query = f"""
            SELECT
                id,
                title,
                summary,
                content,
                sentiment,
                sentiment_score
            FROM articles
            WHERE id IN ({placeholders})
            ORDER BY id
        """

        rows = conn.execute(query, TEST_IDS).fetchall()

        return rows

    finally:
        conn.close()


# ============================================================
# ANALYSE
# ============================================================

def run_test():

    print_separator()
    print("CGI MEDIA MONITOR")
    print("TEST DES 15 CAS LITIGIEUX")
    print("GPT-OSS 120B CLOUD")
    print("DRY-RUN — SQLITE READ ONLY")
    print_separator()

    print(f"\nBase : {DB_PATH.resolve()}")
    print(f"Nombre de cas demandés : {len(TEST_IDS)}")

    print("\nIDs testés :")
    print(TEST_IDS)

    rows = get_articles()

    print(f"\nArticles trouvés dans SQLite : {len(rows)}")

    found_ids = {row["id"] for row in rows}

    missing_ids = [
        article_id
        for article_id in TEST_IDS
        if article_id not in found_ids
    ]

    if missing_ids:
        print("\n⚠️ IDs absents de SQLite :")
        print(missing_ids)

    results = []

    print("\n")
    print_separator()

    for index, row in enumerate(rows, start=1):

        article_id = row["id"]
        title = row["title"] or ""
        summary = row["summary"] or ""
        content = row["content"] or ""

        old_sentiment = row["sentiment"] or ""

        reference = REFERENCE.get(
            article_id,
            ""
        )

        print(
            f"\n[{index}/{len(rows)}] "
            f"ID={article_id}"
        )

        print(f"Titre : {title}")
        print(f"Ancien : {old_sentiment}")
        print(f"Référence : {reference or 'N/A'}")

        if not content.strip():
            print("⚠️ CONTENU VIDE")

        start = time.perf_counter()

        try:

            result = analyze_cgi_sentiment(
                title=title,
                summary=summary,
                content=content,
            )

            elapsed = time.perf_counter() - start

            new_sentiment = result.get(
                "sentiment",
                "ERROR"
            )

            score = result.get(
                "score",
                0.0
            )

            confidence = result.get(
                "confidence",
                0.0
            )

            review = result.get(
                "review",
                False
            )

            reason = result.get(
                "reason",
                ""
            )

            content_mismatch = result.get(
                "content_mismatch",
                False
            )

            print(
                f"Nouveau : {new_sentiment}"
            )

            print(
                f"Confidence : {confidence:.3f}"
            )

            print(
                f"Review : {review}"
            )

            print(
                f"Content mismatch : {content_mismatch}"
            )

            print(
                f"Temps : {elapsed:.2f}s"
            )

            print(
                f"Reason : {reason}"
            )

            # ------------------------------------------------
            # Comparaisons
            # ------------------------------------------------

            changed = (
                old_sentiment != new_sentiment
            )

            reference_match = (
                bool(reference)
                and new_sentiment == reference
            )

            results.append({
                "id": article_id,
                "title": title,
                "source": "",
                "old_sentiment": old_sentiment,
                "new_sentiment": new_sentiment,
                "reference_sentiment": reference,
                "changed": changed,
                "reference_match": reference_match,
                "score": score,
                "confidence": confidence,
                "review": review,
                "content_mismatch": content_mismatch,
                "reason": reason,
                "elapsed_seconds": round(
                    elapsed,
                    2
                ),
            })

        except Exception as error:

            elapsed = time.perf_counter() - start

            print(
                f"❌ ERREUR : {error}"
            )

            results.append({
                "id": article_id,
                "title": title,
                "source": "",
                "old_sentiment": old_sentiment,
                "new_sentiment": "ERROR",
                "reference_sentiment": reference,
                "changed": "",
                "reference_match": False,
                "score": 0.0,
                "confidence": 0.0,
                "review": True,
                "content_mismatch": False,
                "reason": str(error),
                "elapsed_seconds": round(
                    elapsed,
                    2
                ),
            })

    # ========================================================
    # CSV
    # ========================================================

    fieldnames = [
        "id",
        "title",
        "source",
        "old_sentiment",
        "new_sentiment",
        "reference_sentiment",
        "changed",
        "reference_match",
        "score",
        "confidence",
        "review",
        "content_mismatch",
        "reason",
        "elapsed_seconds",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)

    # ========================================================
    # STATISTIQUES
    # ========================================================

    print("\n")
    print_separator()
    print("RÉSULTATS")
    print_separator()

    total = len(results)

    errors = sum(
        r["new_sentiment"] == "ERROR"
        for r in results
    )

    changed = sum(
        r["changed"] is True
        for r in results
    )

    reviews = sum(
        r["review"] is True
        for r in results
    )

    mismatches = sum(
        r["content_mismatch"] is True
        for r in results
    )

    comparable = [
        r
        for r in results
        if r["reference_sentiment"]
        and r["new_sentiment"] != "ERROR"
    ]

    matches = sum(
        r["reference_match"]
        for r in comparable
    )

    print(f"Total testé       : {total}")
    print(f"Erreurs           : {errors}")
    print(f"Changements       : {changed}")
    print(f"Review            : {reviews}")
    print(f"Content mismatch  : {mismatches}")

    print(
        f"\nComparables référence : "
        f"{len(comparable)}"
    )

    print(
        f"Accords référence     : "
        f"{matches}"
    )

    if comparable:
        accuracy = (
            matches / len(comparable)
        ) * 100

        print(
            f"Accord avec référence : "
            f"{accuracy:.2f}%"
        )

    # ========================================================
    # TABLEAU FINAL
    # ========================================================

    print("\n")
    print_separator()
    print("COMPARAISON FINALE")
    print_separator()

    print(
        f"{'ID':<6}"
        f"{'ANCIEN':<12}"
        f"{'NOUVEAU':<12}"
        f"{'REFERENCE':<12}"
        f"{'CONF':<8}"
        f"{'REVIEW':<8}"
    )

    print("-" * 70)

    for r in results:

        print(
            f"{r['id']:<6}"
            f"{r['old_sentiment']:<12}"
            f"{r['new_sentiment']:<12}"
            f"{r['reference_sentiment'] or 'N/A':<12}"
            f"{r['confidence']:<8.3f}"
            f"{str(r['review']):<8}"
        )

    # ========================================================
    # RAPPEL SQLITE
    # ========================================================

    print("\n")
    print_separator()
    print("FIN DU TEST")
    print_separator()

    print(
        "\n⚠️ SQLITE : AUCUNE MODIFICATION"
    )

    print(
        f"📄 Résultats CSV : "
        f"{OUTPUT_FILE.resolve()}"
    )

    print_separator()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_test()