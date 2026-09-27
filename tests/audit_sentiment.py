"""
tests/audit_sentiment.py
----------------------------------------------------

Audit du sentiment des articles réellement pertinents CGI.

IMPORTANT :
    Ce script NE MODIFIE PAS la base SQLite.

Il sert uniquement à identifier les articles potentiellement
mal classés ou nécessitant une vérification manuelle.

Audit réalisé sur :
    relevant = 1

Catégories inspectées :

1. Positive avec score faible
2. Negative avec score faible
3. Neutral avec score faible
4. Titres contenant des termes sensibles
5. Résumé global

Usage :

    python -m tests.audit_sentiment
"""

from __future__ import annotations

import sqlite3
import re

from config import DATABASE_PATH


# ============================================================
# CONFIGURATION
# ============================================================

LOW_CONFIDENCE_THRESHOLD = 0.65
NEUTRAL_LOW_THRESHOLD = 0.60

SENSITIVE_TERMS = (
    "retrait",
    "retire",
    "quitte",
    "bourse",
    "affaire",
    "procès",
    "proces",
    "enquête",
    "enquete",
    "condamn",
    "jugement",
    "plainte",
    "contentieux",
    "retard",
    "retards",
    "mécontent",
    "mecontents",
    "mécontents",
    "blocage",
    "malaise",
    "difficile",
    "difficulté",
    "difficultes",
    "crise",
    "perte",
    "pertes",
    "déficit",
    "deficit",
    "irrégular",
    "irregular",
    "suspension",
    "licenci",
    "viré",
    "vire",
    "problème",
    "probleme",
    "danger",
)


# ============================================================
# UTILS
# ============================================================

def normalize(text: str) -> str:
    """
    Normalisation simple pour la recherche de termes sensibles.
    """

    if not text:
        return ""

    text = str(text).lower()

    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
        "’": "'",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def find_sensitive_terms(title: str) -> list[str]:
    """
    Retourne les termes sensibles présents dans le titre.
    """

    normalized = normalize(title)

    found = []

    for term in SENSITIVE_TERMS:

        normalized_term = normalize(term)

        # Recherche mot / début de mot.
        pattern = rf"\b{re.escape(normalized_term)}\w*\b"

        if re.search(pattern, normalized):
            found.append(term)

    return found


# ============================================================
# DATABASE
# ============================================================

def get_relevant_articles():

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            id,
            title,
            source,
            sentiment,
            sentiment_score
        FROM articles
        WHERE relevant = 1
        ORDER BY id ASC
        """
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# AUDIT
# ============================================================

def audit():

    rows = get_relevant_articles()

    if not rows:

        print(
            "Aucun article pertinent CGI trouvé."
        )

        return

    # ========================================================
    # CONTENEURS
    # ========================================================

    positive_low = []
    negative_low = []
    neutral_low = []
    sensitive = []

    sentiment_counts = {
        "Positive": 0,
        "Negative": 0,
        "Neutral": 0,
    }

    # ========================================================
    # ANALYSE
    # ========================================================

    for row in rows:

        article_id = row["id"]
        title = row["title"] or ""
        source = row["source"] or ""
        sentiment = row["sentiment"] or "Neutral"

        try:
            score = float(
                row["sentiment_score"]
                or 0.0
            )
        except (
            TypeError,
            ValueError,
        ):
            score = 0.0

        # ----------------------------------------------------
        # Compteurs
        # ----------------------------------------------------

        if sentiment not in sentiment_counts:
            sentiment = "Neutral"

        sentiment_counts[sentiment] += 1

        # ----------------------------------------------------
        # Positive faible
        # ----------------------------------------------------

        if (
            sentiment == "Positive"
            and score < LOW_CONFIDENCE_THRESHOLD
        ):
            positive_low.append(
                {
                    "id": article_id,
                    "title": title,
                    "source": source,
                    "score": score,
                }
            )

        # ----------------------------------------------------
        # Negative faible
        # ----------------------------------------------------

        if (
            sentiment == "Negative"
            and score < LOW_CONFIDENCE_THRESHOLD
        ):
            negative_low.append(
                {
                    "id": article_id,
                    "title": title,
                    "source": source,
                    "score": score,
                }
            )

        # ----------------------------------------------------
        # Neutral faible
        # ----------------------------------------------------

        if (
            sentiment == "Neutral"
            and score > 0
            and score < NEUTRAL_LOW_THRESHOLD
        ):
            neutral_low.append(
                {
                    "id": article_id,
                    "title": title,
                    "source": source,
                    "score": score,
                }
            )

        # ----------------------------------------------------
        # Termes sensibles
        # ----------------------------------------------------

        terms = find_sensitive_terms(title)

        if terms:

            sensitive.append(
                {
                    "id": article_id,
                    "title": title,
                    "source": source,
                    "sentiment": sentiment,
                    "score": score,
                    "terms": terms,
                }
            )

    # ========================================================
    # HEADER
    # ========================================================

    print()
    print("=" * 110)
    print("AUDIT SENTIMENT CGI")
    print("=" * 110)

    print(
        f"Articles pertinents analysés : {len(rows)}"
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 110)
    print("RÉSUMÉ")
    print("=" * 110)

    print(
        f"Positive : {sentiment_counts['Positive']}"
    )

    print(
        f"Negative : {sentiment_counts['Negative']}"
    )

    print(
        f"Neutral  : {sentiment_counts['Neutral']}"
    )

    # ========================================================
    # POSITIVE LOW CONFIDENCE
    # ========================================================

    print()
    print("=" * 110)
    print(
        f"POSITIVE AVEC SCORE < {LOW_CONFIDENCE_THRESHOLD:.0%}"
    )
    print("=" * 110)

    if not positive_low:

        print(
            "Aucun cas."
        )

    else:

        for item in positive_low:

            print()
            print("-" * 110)

            print(
                f"ID        : {item['id']}"
            )

            print(
                f"Score     : {item['score']:.2%}"
            )

            print(
                f"Source    : {item['source']}"
            )

            print(
                f"Titre     : {item['title']}"
            )

    # ========================================================
    # NEGATIVE LOW CONFIDENCE
    # ========================================================

    print()
    print("=" * 110)
    print(
        f"NEGATIVE AVEC SCORE < {LOW_CONFIDENCE_THRESHOLD:.0%}"
    )
    print("=" * 110)

    if not negative_low:

        print(
            "Aucun cas."
        )

    else:

        for item in negative_low:

            print()
            print("-" * 110)

            print(
                f"ID        : {item['id']}"
            )

            print(
                f"Score     : {item['score']:.2%}"
            )

            print(
                f"Source    : {item['source']}"
            )

            print(
                f"Titre     : {item['title']}"
            )

    # ========================================================
    # NEUTRAL LOW CONFIDENCE
    # ========================================================

    print()
    print("=" * 110)
    print(
        f"NEUTRAL AVEC SCORE < {NEUTRAL_LOW_THRESHOLD:.0%}"
    )
    print("=" * 110)

    if not neutral_low:

        print(
            "Aucun cas."
        )

    else:

        for item in neutral_low:

            print()
            print("-" * 110)

            print(
                f"ID        : {item['id']}"
            )

            print(
                f"Score     : {item['score']:.2%}"
            )

            print(
                f"Source    : {item['source']}"
            )

            print(
                f"Titre     : {item['title']}"
            )

    # ========================================================
    # SENSITIVE TITLES
    # ========================================================

    print()
    print("=" * 110)
    print("TITRES AVEC TERMES POTENTIELLEMENT SENSIBLES")
    print("=" * 110)

    if not sensitive:

        print(
            "Aucun cas."
        )

    else:

        for item in sensitive:

            print()
            print("-" * 110)

            print(
                f"ID        : {item['id']}"
            )

            print(
                f"Sentiment : {item['sentiment']}"
            )

            print(
                f"Score     : {item['score']:.2%}"
            )

            print(
                f"Source    : {item['source']}"
            )

            print(
                f"Termes    : {', '.join(item['terms'])}"
            )

            print(
                f"Titre     : {item['title']}"
            )

    # ========================================================
    # PRIORITY CASES
    # ========================================================

    priority_ids = {
        item["id"]
        for item in (
            positive_low
            + negative_low
            + neutral_low
        )
    }

    priority_ids.update(
        item["id"]
        for item in sensitive
    )

    print()
    print("=" * 110)
    print("PRIORITÉ DE VÉRIFICATION")
    print("=" * 110)

    if not priority_ids:

        print(
            "Aucun article prioritaire trouvé."
        )

    else:

        print(
            f"{len(priority_ids)} article(s) à vérifier."
        )

        print()

        for article_id in sorted(
            priority_ids
        ):

            print(
                f"- ID {article_id}"
            )

    # ========================================================
    # FINAL
    # ========================================================

    print()
    print("=" * 110)
    print("FIN DE L'AUDIT")
    print("=" * 110)

    print(
        "IMPORTANT : aucune donnée SQLite n'a été modifiée."
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    audit()