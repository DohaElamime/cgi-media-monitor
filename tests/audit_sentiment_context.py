from __future__ import annotations

import sqlite3

from config import DATABASE_PATH


# Cas déjà identifiés comme potentiellement problématiques.
SUSPECT_IDS = [
    157,
    158,
    159,
    163,
    170,
    173,
    181,
    183,
    193,
    196,
    208,
    210,
    213,
    217,
    219,
    238,
    250,
    256,
    258,
    268,
    279,
    280,
    282,
    283,
    294,
    295,
    302,
    314,
    325,
    340,
    341,
    337,
    328,
    345,
    346,
    347,
]


def main() -> None:

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    placeholders = ",".join(
        "?" for _ in SUSPECT_IDS
    )

    query = f"""
        SELECT
            id,
            title,
            source,
            sentiment,
            sentiment_score,
            content
        FROM articles
        WHERE id IN ({placeholders})
        ORDER BY id ASC
    """

    rows = conn.execute(
        query,
        SUSPECT_IDS,
    ).fetchall()

    print()
    print("=" * 120)
    print("AUDIT SENTIMENT V2 — CONTEXTE RÉEL")
    print("=" * 120)

    for row in rows:

        article_id = row["id"]
        title = row["title"] or ""
        source = row["source"] or ""
        sentiment = row["sentiment"] or "Neutral"

        try:
            score = float(
                row["sentiment_score"] or 0.0
            )
        except (TypeError, ValueError):
            score = 0.0

        content = (
            row["content"]
            or ""
        ).strip()

        # On affiche suffisamment de contenu pour comprendre
        # le contexte sans produire une sortie énorme.
        preview = content[:2500]

        print()
        print("=" * 120)
        print(f"ID        : {article_id}")
        print(f"Titre     : {title}")
        print(f"Source    : {source}")
        print(f"Sentiment : {sentiment}")
        print(f"Score     : {score:.2%}")
        print("-" * 120)
        print("CONTENU :")
        print(preview)

        if len(content) > 2500:
            print("\n...[CONTENU TRONQUÉ]...")

    conn.close()

    print()
    print("=" * 120)
    print("FIN DE L'AUDIT V2")
    print("=" * 120)
    print("Aucune modification de la base de données.")


if __name__ == "__main__":
    main()