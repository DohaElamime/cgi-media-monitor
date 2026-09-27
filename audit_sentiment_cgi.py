# -*- coding: utf-8 -*-
"""
CGI Media Monitor - AUDIT SENTIMENT COMPLET
================================================

OBJECTIF
--------
Ce script vérifie la qualité des résultats de sentiment déjà présents
dans SQLite, SANS modifier la base.

Il cherche notamment :
    1. sentiments manquants ou invalides ;
    2. scores hors [0, 1] ;
    3. scores nuls sur des articles RELEVANT ;
    4. sentiments présents sur des NON_RELEVANT / REVIEW ;
    5. contradictions lexicales fortes entre le texte et le label ;
    6. articles RELEVANT avec contenu vide/très court ;
    7. incohérences entre label et score ;
    8. doublons de titres ayant des sentiments différents ;
    9. répartition finale des sentiments ;
   10. distribution des scores pour repérer un modèle anormalement
       concentré vers 0, 50% ou 100%.

IMPORTANT
---------
- AUCUN UPDATE / DELETE / INSERT n'est effectué.
- Le script lit uniquement la table articles.
- Une alerte ne signifie pas automatiquement que le sentiment est faux.
  Elle indique un cas qui mérite une vérification.

EXECUTION
---------
Depuis la racine du projet :

    python audit_sentiment_cgi.py

Le script crée aussi :

    outputs/sentiment_audit.csv

avec les articles signalés.
"""

from __future__ import annotations

import csv
import math
import re
import sqlite3
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


# ============================================================
# RACINE DU PROJET
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent

# Le script peut être placé à la racine OU dans modules/.
if ROOT_DIR.name.lower() == "modules":
    PROJECT_ROOT = ROOT_DIR.parent
else:
    PROJECT_ROOT = ROOT_DIR

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# DATABASE
# ============================================================

try:
    from config import DATABASE_PATH
except Exception as exc:
    raise SystemExit(
        "Impossible d'importer DATABASE_PATH depuis config.py : "
        f"{exc}"
    )


# ============================================================
# CONSTANTES
# ============================================================

VALID_SENTIMENTS = {
    "Positive",
    "Negative",
    "Neutral",
}

VALID_STATUSES = {
    "RELEVANT",
    "NON_RELEVANT",
    "REVIEW",
}

# Indices négatifs volontairement conservateurs.
NEGATIVE_TERMS = (
    "condamnation",
    "condamné",
    "condamnee",
    "condamnée",
    "procès",
    "proces",
    "enquête",
    "enquete",
    "affaire",
    "limogé",
    "limogee",
    "limogée",
    "viré",
    "vire",
    "virée",
    "licencié",
    "licencie",
    "licenciée",
    "retrait",
    "quitte la bourse",
    "mauvaise note",
    "perte",
    "déficit",
    "deficit",
    "sanction",
    "plainte",
    "litige",
    "contentieux",
    "mécontent",
    "mécontente",
    "mécontents",
    "critique",
    "crise",
    "baisse",
    "recul",
    "effondrement",
    "échec",
    "echec",
    "fraude",
    "irrégularité",
    "irregularite",
)

# Indices positifs volontairement conservateurs.
POSITIVE_TERMS = (
    "récompensé",
    "recompense",
    "récompensée",
    "recompensee",
    "distinction",
    "élu service client",
    "elue service client",
    "excellence",
    "succès",
    "succes",
    "croissance",
    "progression",
    "record",
    "certification",
    "meilleur promoteur",
    "premier promoteur",
    "innovation",
    "performance",
    "développement",
    "developpement",
)

STOPWORDS = {
    "avec",
    "dans",
    "pour",
    "sur",
    "une",
    "des",
    "les",
    "aux",
    "par",
    "est",
    "sont",
    "mais",
    "plus",
    "que",
    "qui",
    "the",
    "and",
    "from",
    "this",
    "that",
}


# ============================================================
# TEXTE
# ============================================================

def normalize_text(text: object) -> str:
    value = str(text or "")

    value = unicodedata.normalize("NFD", value)
    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.lower()
    value = value.replace("’", "'")
    value = value.replace("œ", "oe")
    value = value.replace("æ", "ae")

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def clean_title(title: object) -> str:
    value = str(title or "").strip()

    patterns = [
        r"\s*-\s*Hespress Français.*$",
        r"\s*-\s*Hespress.*$",
        r"\s*-\s*Le360\.ma\s*$",
        r"\s*-\s*Le360\s*$",
        r"\s*-\s*LesEco\.ma\s*$",
        r"\s*-\s*LesEco\s*$",
        r"\s*-\s*Médias24.*$",
        r"\s*-\s*Medias24.*$",
        r"\s*-\s*Challenge\.ma\s*$",
        r"\s*-\s*La Vie éco\s*$",
        r"\s*-\s*La Vie eco\s*$",
        r"\s*-\s*Le Matin\.ma\s*$",
        r"\s*-\s*Le Matin\s*$",
        r"\s*-\s*L'Économiste\s*$",
        r"\s*-\s*L’Économiste\s*$",
        r"\s*-\s*L'Economiste\s*$",
        r"\s*-\s*MAP\s*$",
        r"\s*-\s*Boursenews\s*$",
    ]

    for pattern in patterns:
        value = re.sub(
            pattern,
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

    return re.sub(r"\s+", " ", value).strip()


def count_terms(
    text: str,
    terms: Iterable[str],
) -> list[str]:
    normalized = normalize_text(text)
    hits = []

    for term in terms:
        token = normalize_text(term)

        if token and token in normalized:
            hits.append(term)

    return hits


def meaningful_title(title: str) -> str:
    normalized = normalize_text(
        clean_title(title)
    )

    tokens = [
        token
        for token in normalized.split()
        if len(token) >= 3
        and token not in STOPWORDS
    ]

    return " ".join(tokens)


# ============================================================
# STATUT
# ============================================================

def normalize_status(row: sqlite3.Row) -> str:
    keys = set(row.keys())

    if "relevance_status" in keys:
        value = str(
            row["relevance_status"] or ""
        ).strip().upper()

        if value in VALID_STATUSES:
            return value

    if "relevant" in keys:
        value = row["relevant"]

        if value == 1:
            return "RELEVANT"

        if value == 0:
            return "NON_RELEVANT"

    return "REVIEW"


# ============================================================
# SENTIMENT
# ============================================================

def normalize_sentiment(value: object) -> str:
    raw = str(value or "").strip()

    mapping = {
        "positive": "Positive",
        "positif": "Positive",
        "Positif": "Positive",
        "negative": "Negative",
        "negatif": "Negative",
        "négatif": "Negative",
        "Négatif": "Negative",
        "neutral": "Neutral",
        "neutre": "Neutral",
        "Neutre": "Neutral",
    }

    return mapping.get(raw, raw)


def parse_score(value: object) -> float | None:
    if value is None:
        return None

    try:
        score = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(score):
        return None

    return score


# ============================================================
# CONTENU
# ============================================================

def content_quality(row: sqlite3.Row) -> str:
    keys = set(row.keys())

    if "content_quality" in keys:
        quality = str(
            row["content_quality"] or ""
        ).strip().upper()

        if quality:
            return quality

    content = str(
        row["content"] or ""
    ).strip()

    if not content:
        return "MISSING"

    if len(content) < 200:
        return "SHORT"

    return "UNKNOWN"


# ============================================================
# AUDIT D'UNE LIGNE
# ============================================================

def audit_row(row: sqlite3.Row) -> dict:
    status = normalize_status(row)

    title = str(
        row["title"] or ""
    ).strip()

    content = str(
        row["content"] or ""
    ).strip()

    text = f"{title}\n{content}".strip()

    sentiment = normalize_sentiment(
        row["sentiment"]
    )

    score = parse_score(
        row["sentiment_score"]
    )

    negative_hits = count_terms(
        text,
        NEGATIVE_TERMS,
    )

    positive_hits = count_terms(
        text,
        POSITIVE_TERMS,
    )

    quality = content_quality(row)

    alerts = []

    # --------------------------------------------------------
    # 1. LABEL
    # --------------------------------------------------------

    if status == "RELEVANT":
        if not sentiment:
            alerts.append(
                "SENTIMENT_MANQUANT"
            )
        elif sentiment not in VALID_SENTIMENTS:
            alerts.append(
                "SENTIMENT_INVALIDE"
            )

    # --------------------------------------------------------
    # 2. SCORE
    # --------------------------------------------------------

    if score is None:
        if status == "RELEVANT":
            alerts.append(
                "SCORE_MANQUANT"
            )
    else:
        if score < 0 or score > 1:
            alerts.append(
                "SCORE_HORS_BORNES"
            )

        if status == "RELEVANT" and score == 0:
            alerts.append(
                "SCORE_ZERO_RELEVANT"
            )

    # --------------------------------------------------------
    # 3. SENTIMENT SUR NON_RELEVANT / REVIEW
    # --------------------------------------------------------

    if status != "RELEVANT":
        if sentiment in VALID_SENTIMENTS:
            # Neutral = 0 sur ces lignes est attendu.
            if not (
                sentiment == "Neutral"
                and (
                    score is None
                    or score == 0
                )
            ):
                alerts.append(
                    "SENTIMENT_PRESENT_SUR_NON_RELEVANT"
                )

    # --------------------------------------------------------
    # 4. QUALITÉ CONTENU
    # --------------------------------------------------------

    if status == "RELEVANT":
        if quality in {
            "MISSING",
            "SHORT",
            "MISMATCH",
        }:
            alerts.append(
                "SENTIMENT_SUR_CONTENU_NON_FIABLE"
            )

    # --------------------------------------------------------
    # 5. CONTRADICTIONS LEXICALES
    # --------------------------------------------------------

    strong_negative = len(
        negative_hits
    ) >= 2

    strong_positive = len(
        positive_hits
    ) >= 2

    if status == "RELEVANT":
        if (
            sentiment == "Positive"
            and strong_negative
            and not strong_positive
        ):
            alerts.append(
                "POSITIF_MALGRE_INDICES_NEGATIFS"
            )

        if (
            sentiment == "Negative"
            and strong_positive
            and not strong_negative
        ):
            alerts.append(
                "NEGATIF_MALGRE_INDICES_POSITIFS"
            )

    # --------------------------------------------------------
    # 6. CAS TRÈS FORTEMENT NEUTRES
    # --------------------------------------------------------

    if (
        status == "RELEVANT"
        and sentiment == "Neutral"
        and score is not None
        and score >= 0.90
        and (
            strong_negative
            or strong_positive
        )
    ):
        alerts.append(
            "NEUTRE_AVEC_INDICE_FORT"
        )

    # --------------------------------------------------------
    # 7. SCORE / LABEL SUSPECT
    # --------------------------------------------------------

    if status == "RELEVANT" and score is not None:
        if score >= 0.995:
            alerts.append(
                "SCORE_QUASI_100"
            )

        elif score <= 0.505:
            alerts.append(
                "SCORE_FAIBLE"
            )

    # --------------------------------------------------------
    # 8. TITRE / CONTENU
    # --------------------------------------------------------

    if (
        status == "RELEVANT"
        and len(content) < 100
    ):
        alerts.append(
            "CONTENU_TROP_COURT"
        )

    return {
        "id": row["id"],
        "status": status,
        "title": title,
        "source": str(
            row["source"] or ""
        ).strip(),
        "sentiment": sentiment,
        "score": score,
        "quality": quality,
        "positive_hits": positive_hits,
        "negative_hits": negative_hits,
        "alerts": alerts,
    }


# ============================================================
# DOUBLONS
# ============================================================

def duplicate_title_alerts(
    rows: list[sqlite3.Row],
) -> dict[int, str]:
    groups = defaultdict(list)

    for row in rows:
        key = meaningful_title(
            str(row["title"] or "")
        )

        if key:
            groups[key].append(row)

    result = {}

    for key, group in groups.items():
        if len(group) < 2:
            continue

        relevant_sentiments = {
            normalize_sentiment(
                row["sentiment"]
            )
            for row in group
            if normalize_status(row) == "RELEVANT"
        }

        relevant_sentiments.discard("")

        if len(relevant_sentiments) >= 2:
            for row in group:
                if normalize_status(row) == "RELEVANT":
                    result[row["id"]] = (
                        "DOUBLON_TITRE_SENTIMENT_DIFFERENT"
                    )

    return result


# ============================================================
# DISTRIBUTION
# ============================================================

def print_distribution(
    relevant_results: list[dict],
) -> None:
    labels = Counter(
        item["sentiment"]
        for item in relevant_results
        if item["sentiment"] in VALID_SENTIMENTS
    )

    scores = [
        item["score"]
        for item in relevant_results
        if item["score"] is not None
        and 0 < item["score"] <= 1
    ]

    print("\n" + "=" * 80)
    print("RÉPARTITION DES SENTIMENTS — ARTICLES RELEVANT")
    print("=" * 80)

    print(
        f"Positive : {labels.get('Positive', 0)}"
    )

    print(
        f"Negative : {labels.get('Negative', 0)}"
    )

    print(
        f"Neutral  : {labels.get('Neutral', 0)}"
    )

    invalid_count = sum(
        1
        for item in relevant_results
        if item["sentiment"] not in VALID_SENTIMENTS
    )

    print(
        f"Invalides/vides : {invalid_count}"
    )

    if scores:
        print("\nSCORES")
        print("-" * 80)

        print(
            f"Min    : {min(scores):.2%}"
        )
        print(
            f"Moyenne: {statistics.mean(scores):.2%}"
        )
        print(
            f"Médiane: {statistics.median(scores):.2%}"
        )
        print(
            f"Max    : {max(scores):.2%}"
        )

        almost_100 = sum(
            1
            for score in scores
            if score >= 0.995
        )

        low = sum(
            1
            for score in scores
            if score <= 0.505
        )

        print(
            f"Scores >= 99.5% : {almost_100}"
        )

        print(
            f"Scores <= 50.5% : {low}"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    db_path = Path(DATABASE_PATH)

    if not db_path.exists():
        raise SystemExit(
            "Base SQLite introuvable : "
            f"{db_path}"
        )

    print("=" * 80)
    print("AUDIT SENTIMENT CGI MEDIA MONITOR")
    print("=" * 80)
    print("Base :", db_path)
    print("Mode : LECTURE SEULE — aucune modification SQLite")
    print()

    conn = sqlite3.connect(
        str(db_path)
    )

    conn.row_factory = sqlite3.Row

    try:
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(articles)"
            ).fetchall()
        }

        rows = conn.execute(
            """
            SELECT *
            FROM articles
            ORDER BY id ASC
            """
        ).fetchall()

    except sqlite3.Error as exc:
        conn.close()
        raise SystemExit(
            f"Erreur SQLite : {exc}"
        )

    conn.close()

    print(
        f"Articles trouvés : {len(rows)}"
    )

    print(
        "Colonnes disponibles : "
        + ", ".join(sorted(columns))
    )

    results = [
        audit_row(row)
        for row in rows
    ]

    relevant_results = [
        item
        for item in results
        if item["status"] == "RELEVANT"
    ]

    duplicate_alerts = duplicate_title_alerts(
        rows
    )

    # Ajouter les alertes de doublons.
    for item in results:
        duplicate_reason = duplicate_alerts.get(
            item["id"]
        )

        if duplicate_reason:
            item["alerts"].append(
                duplicate_reason
            )

    # ========================================================
    # COMPTEURS
    # ========================================================

    status_counts = Counter(
        item["status"]
        for item in results
    )

    alert_counts = Counter()

    for item in results:
        for alert in item["alerts"]:
            alert_counts[alert] += 1

    # ========================================================
    # SYNTHÈSE
    # ========================================================

    print("\n" + "=" * 80)
    print("SYNTHÈSE")
    print("=" * 80)

    print(
        f"Total            : {len(results)}"
    )

    print(
        f"RELEVANT         : {status_counts.get('RELEVANT', 0)}"
    )

    print(
        f"NON_RELEVANT     : {status_counts.get('NON_RELEVANT', 0)}"
    )

    print(
        f"REVIEW            : {status_counts.get('REVIEW', 0)}"
    )

    print_distribution(
        relevant_results
    )

    # ========================================================
    # ALERTES
    # ========================================================

    print("\n" + "=" * 80)
    print("TYPES D'ALERTES")
    print("=" * 80)

    if not alert_counts:
        print(
            "Aucune anomalie détectée par les règles de cet audit."
        )
    else:
        for alert, count in sorted(
            alert_counts.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            print(
                f"{alert:<45} : {count}"
            )

    # ========================================================
    # ARTICLES À VÉRIFIER
    # ========================================================

    flagged = [
        item
        for item in results
        if item["alerts"]
    ]

    print("\n" + "=" * 80)
    print(
        f"ARTICLES À VÉRIFIER : {len(flagged)}"
    )
    print("=" * 80)

    if not flagged:
        print(
            "✅ Aucun article signalé."
        )
    else:
        for item in flagged:
            print()
            print(
                f"ID={item['id']} | "
                f"{item['status']} | "
                f"{item['sentiment'] or '(vide)'} | "
                f"score="
                f"{item['score']:.2%}"
                if item["score"] is not None
                else
                f"ID={item['id']} | "
                f"{item['status']} | "
                f"{item['sentiment'] or '(vide)'} | "
                "score=(vide)"
            )

            print(
                "SOURCE : "
                + item["source"]
            )

            print(
                "TITRE  : "
                + item["title"]
            )

            print(
                "QUALITÉ : "
                + item["quality"]
            )

            print(
                "ALERTES : "
                + " | ".join(item["alerts"])
            )

            if item["positive_hits"]:
                print(
                    "INDICES + : "
                    + ", ".join(
                        item["positive_hits"]
                    )
                )

            if item["negative_hits"]:
                print(
                    "INDICES - : "
                    + ", ".join(
                        item["negative_hits"]
                    )
                )

    # ========================================================
    # CSV
    # ========================================================

    output_dir = PROJECT_ROOT / "outputs"
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_path = (
        output_dir
        / "sentiment_audit.csv"
    )

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "id",
                "status",
                "title",
                "source",
                "sentiment",
                "score",
                "quality",
                "positive_hits",
                "negative_hits",
                "alerts",
            ],
        )

        writer.writeheader()

        for item in flagged:
            writer.writerow(
                {
                    "id": item["id"],
                    "status": item["status"],
                    "title": item["title"],
                    "source": item["source"],
                    "sentiment": item["sentiment"],
                    "score": (
                        ""
                        if item["score"] is None
                        else f"{item['score']:.6f}"
                    ),
                    "quality": item["quality"],
                    "positive_hits": ", ".join(
                        item["positive_hits"]
                    ),
                    "negative_hits": ", ".join(
                        item["negative_hits"]
                    ),
                    "alerts": " | ".join(
                        item["alerts"]
                    ),
                }
            )

    print("\n" + "=" * 80)
    print("FICHIER D'AUDIT")
    print("=" * 80)
    print(
        "CSV créé : "
        + str(csv_path)
    )

    print("\nFIN DE L'AUDIT")
    print(
        "Ce script signale des cas suspects ; "
        "il ne décide pas à votre place qu'un sentiment est faux."
    )


if __name__ == "__main__":
    main()
