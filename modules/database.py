import sqlite3
from typing import List, Dict, Optional

import pandas as pd

from config import DATABASE_PATH


# ============================================================
# CONNEXION
# ============================================================

def get_connection() -> sqlite3.Connection:
    """
    Ouvre une connexion SQLite.
    """

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# NORMALISATION DATE
# ============================================================

def normalize_date(value):
    """
    Convertit une date vers un format ISO :

        YYYY-MM-DD HH:MM:SS

    Retourne une chaîne vide si la date est invalide.

    IMPORTANT :
    on n'invente jamais une date.
    """

    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    try:

        parsed = pd.to_datetime(
            value,
            errors="coerce",
            utc=True,
        )

        if pd.isna(parsed):
            return ""

        parsed = parsed.tz_localize(
            None
        )

        return parsed.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception:

        return ""


# ============================================================
# NORMALISATION CONFIANCE
# ============================================================

def normalize_confidence(value):
    """
    Normalise la confiance IA.

    Retourne :
        - float entre 0 et 1 si la valeur est valide
        - None si la confiance est absente ou invalide

    IMPORTANT :
    une confiance absente ne devient PAS 0.0.
    """

    if value is None:
        return None

    try:

        if pd.isna(value):
            return None

    except (TypeError, ValueError):
        return None

    try:

        if isinstance(value, str):

            value = value.strip()

            if not value:
                return None

            # Exemple : "94%"
            if value.endswith("%"):

                value = float(
                    value[:-1].strip()
                ) / 100.0

            else:

                value = float(value)

        else:

            value = float(value)

    except (
        TypeError,
        ValueError,
    ):

        return None

    # Si une valeur 94 est fournie au lieu de 0.94
    if value > 1.0 and value <= 100.0:

        value = value / 100.0

    # Une confiance doit être comprise entre 0 et 1
    if value < 0.0 or value > 1.0:

        return None

    return value


# ============================================================
# EXISTENCE ARTICLE
# ============================================================

def article_exists(url: str) -> bool:
    """
    Vérifie si un article existe déjà.
    """

    if not url:
        return False

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM articles
            WHERE url = ?
            LIMIT 1
            """,
            (url,),
        )

        return cursor.fetchone() is not None

    finally:

        conn.close()


# ============================================================
# SAUVEGARDE ARTICLE
# ============================================================

def save_article(article: Dict) -> bool:
    """
    Enregistre ou met à jour un article.

    La date est normalisée avant sauvegarde.

    La confiance IA absente reste NULL.
    Elle n'est jamais remplacée automatiquement par 0.0.
    """

    url = (
        article.get("url", "")
        or ""
    ).strip()

    if not url:
        return False


    # ========================================================
    # DATE
    # ========================================================

    date_value = normalize_date(
        article.get("date", "")
    )


    # ========================================================
    # PERTINENCE
    # ========================================================

    relevant = int(
        bool(
            article.get(
                "relevant",
                False,
            )
        )
    )


    # ========================================================
    # SENTIMENT
    # ========================================================

    sentiment = (
        article.get(
            "sentiment",
            "",
        )
        or ""
    )


    # ========================================================
    # SENTIMENT SCORE
    # ========================================================

    try:

        raw_sentiment_score = article.get(
            "sentiment_score"
        )

        if (
            raw_sentiment_score is None
            or str(raw_sentiment_score).strip() == ""
        ):

            sentiment_score = None

        else:

            sentiment_score = float(
                raw_sentiment_score
            )

    except (
        TypeError,
        ValueError,
    ):

        sentiment_score = None


    # ========================================================
    # CONFIANCE IA
    # ========================================================

    confidence = normalize_confidence(
        article.get("confidence")
    )


    # ========================================================
    # ARTICLE EXISTANT
    # ========================================================

    if article_exists(url):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE articles
                SET
                    date = CASE
                        WHEN ? != ''
                        THEN ?
                        ELSE date
                    END,
                    relevant = ?,
                    sentiment = ?,
                    sentiment_score = ?,
                    confidence = ?
                WHERE url = ?
                """,
                (
                    date_value,
                    date_value,
                    relevant,
                    sentiment,
                    sentiment_score,
                    confidence,
                    url,
                ),
            )

            conn.commit()

        finally:

            conn.close()

        return False


    # ========================================================
    # NOUVEL ARTICLE
    # ========================================================

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO articles
            (
                title,
                url,
                source,
                date,
                summary,
                content,
                relevant,
                sentiment,
                sentiment_score,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.get(
                    "title",
                    "",
                ),
                url,
                article.get(
                    "source",
                    "",
                ),
                date_value,
                article.get(
                    "body",
                    "",
                ),
                article.get(
                    "content",
                    "",
                ),
                relevant,
                sentiment,
                sentiment_score,
                confidence,
            ),
        )

        conn.commit()

    finally:

        conn.close()

    return True


# ============================================================
# TOUS LES ARTICLES
# ============================================================

def get_articles() -> List[Dict]:
    """
    Retourne tous les articles.

    Les dates sont normalisées lors de la lecture.
    """

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM articles
            ORDER BY created_at DESC
            """
        )

        rows = cursor.fetchall()

    finally:

        conn.close()


    articles = []

    for row in rows:

        article = dict(row)

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        if "date" in article:

            article["date"] = normalize_date(
                article.get("date")
            )

        # ----------------------------------------------------
        # CONFIANCE
        # ----------------------------------------------------
        #
        # On conserve None si la valeur est absente.
        #

        if "confidence" in article:

            article["confidence"] = (
                normalize_confidence(
                    article.get("confidence")
                )
            )

        articles.append(
            article
        )

    return articles


# ============================================================
# ARTICLE PAR URL
# ============================================================

def get_article_by_url(
    url: str,
) -> Optional[Dict]:
    """
    Retourne un article selon son URL.
    """

    if not url:
        return None

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM articles
            WHERE url = ?
            """,
            (url,),
        )

        row = cursor.fetchone()

    finally:

        conn.close()

    if row is None:
        return None

    article = dict(row)


    # ========================================================
    # DATE
    # ========================================================

    if "date" in article:

        article["date"] = normalize_date(
            article.get("date")
        )


    # ========================================================
    # CONFIANCE
    # ========================================================

    if "confidence" in article:

        article["confidence"] = (
            normalize_confidence(
                article.get("confidence")
            )
        )

    return article


# ============================================================
# ARTICLES PERTINENTS
# ============================================================

def get_relevant_articles() -> List[Dict]:
    """
    Retourne uniquement les articles pertinents.
    """

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM articles
            WHERE relevant = 1
            ORDER BY created_at DESC
            """
        )

        rows = cursor.fetchall()

    finally:

        conn.close()


    articles = []

    for row in rows:

        article = dict(row)


        # ====================================================
        # DATE
        # ====================================================

        if "date" in article:

            article["date"] = normalize_date(
                article.get("date")
            )


        # ====================================================
        # CONFIANCE
        # ====================================================

        if "confidence" in article:

            article["confidence"] = (
                normalize_confidence(
                    article.get("confidence")
                )
            )


        articles.append(
            article
        )

    return articles


# ============================================================
# MISE À JOUR ANALYSE
# ============================================================

def update_article_analysis(
    url: str,
    relevant: bool,
    sentiment: str,
    sentiment_score: float,
    confidence: float,
) -> None:
    """
    Met à jour les résultats de l'analyse IA.

    Une confiance absente ou invalide reste NULL.
    """

    if not url:
        return


    # ========================================================
    # NORMALISATION CONFIANCE
    # ========================================================

    normalized_confidence = (
        normalize_confidence(
            confidence
        )
    )


    # ========================================================
    # SENTIMENT SCORE
    # ========================================================

    try:

        if sentiment_score is None:
            normalized_sentiment_score = None

        else:
            normalized_sentiment_score = float(
                sentiment_score
            )

    except (
        TypeError,
        ValueError,
    ):

        normalized_sentiment_score = None


    # ========================================================
    # CONNEXION
    # ========================================================

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE articles
            SET
                relevant = ?,
                sentiment = ?,
                sentiment_score = ?,
                confidence = ?
            WHERE url = ?
            """,
            (
                int(bool(relevant)),
                sentiment or "",
                normalized_sentiment_score,
                normalized_confidence,
                url,
            ),
        )

        conn.commit()

    finally:

        conn.close()


# ============================================================
# SUPPRESSION
# ============================================================

def delete_articles() -> None:
    """
    Supprime tous les articles.
    """

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM articles
            """
        )

        conn.commit()

    finally:

        conn.close()


# ============================================================
# COMPTEURS
# ============================================================

def count_articles() -> int:
    """
    Nombre total d'articles.
    """

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM articles
            """
        )

        return cursor.fetchone()[0]

    finally:

        conn.close()


def count_relevant_articles() -> int:
    """
    Nombre d'articles pertinents.
    """

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM articles
            WHERE relevant = 1
            """
        )

        return cursor.fetchone()[0]

    finally:

        conn.close()