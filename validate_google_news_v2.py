# test_google_news_v2_validation.py

import csv
import json
import time
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "google_news_v2_results.csv"

OUTPUT_VALIDATION = BASE_DIR / "google_news_v2_validation.csv"
OUTPUT_SUSPECTS = BASE_DIR / "google_news_v2_validation_suspects.csv"
OUTPUT_CONFIRMED = BASE_DIR / "google_news_v2_confirmed.csv"
OUTPUT_CORRECTED = BASE_DIR / "google_news_v2_corrected.csv"
OUTPUT_REVIEW = BASE_DIR / "google_news_v2_review.csv"
OUTPUT_ERRORS = BASE_DIR / "google_news_v2_errors.csv"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gpt-oss:120b-cloud"

# IMPORTANT :
# Un seul appel par article.
# On évite les 3 x 180 secondes de l'ancien script.
REQUEST_TIMEOUT = 60


# ============================================================
# PROMPT SEMANTIQUE
# ============================================================

SYSTEM_PROMPT = """
Tu es un auditeur expert en analyse sémantique des articles de presse.

Ta tâche est de déterminer le sentiment exprimé envers
la société CGI Maroc / Compagnie Générale Immobilière.

IMPORTANT :
- Tu dois analyser le sens global du contenu fourni.
- NE FAIS PAS de classification par mots-clés.
- Un mot positif isolé ne suffit pas pour classer Positive.
- Un mot négatif isolé ne suffit pas pour classer Negative.
- Une nomination n'est pas automatiquement Positive.
- Une récompense concernant CGI peut être Positive si l'article exprime clairement
  une reconnaissance favorable envers CGI.
- Un investissement ou un projet immobilier n'est pas automatiquement Positive.
- Une procédure judiciaire n'est pas automatiquement Negative.
- Une condamnation ou une affaire judiciaire concernant directement CGI peut être
  négative si le contenu établit clairement un impact négatif envers CGI.
- Une radiation/delisting de la Bourse n'est pas automatiquement Negative.
- Un article portant principalement sur une autre société, une filiale,
  une personne ou le secteur immobilier n'est pas automatiquement un sentiment
  envers CGI.
- Une information purement factuelle ou descriptive doit généralement être Neutral.
- Si le contenu ne permet pas de déterminer clairement un sentiment envers CGI,
  choisis Neutral et review=true.
- Si le contenu est ambigu, contradictoire ou insuffisant, choisis Neutral
  et review=true.

Définitions :

Positive :
Le contenu présente CGI de manière clairement favorable, valorisante,
réussie ou reconnaît explicitement une performance, distinction ou appréciation
positive de CGI.

Negative :
Le contenu présente CGI de manière clairement défavorable ou décrit un
événement négatif ayant un lien direct et significatif avec CGI.

Neutral :
Le contenu est principalement factuel, descriptif, informatif, stratégique,
financier ou contextuel sans évaluation clairement positive ou négative
de CGI.

Review :
true si l'interprétation demande une vérification humaine ou si le contenu
est ambigu, insuffisant, contradictoire ou si plusieurs interprétations
sont raisonnablement possibles.

Tu dois répondre UNIQUEMENT avec un JSON valide :

{
  "sentiment": "Positive|Neutral|Negative",
  "confidence": 0.0,
  "review": true,
  "reason": "explication courte et sémantique"
}

confidence doit être comprise entre 0 et 1.
"""


# ============================================================
# VALIDATION JSON
# ============================================================

VALID_SENTIMENTS = {"Positive", "Neutral", "Negative"}


def validate_result(data):
    """
    Vérifie que la réponse GPT-OSS possède une structure correcte.
    """

    if not isinstance(data, dict):
        raise ValueError("Réponse JSON invalide : objet attendu.")

    sentiment = data.get("sentiment")

    if sentiment not in VALID_SENTIMENTS:
        raise ValueError(
            f"Sentiment invalide : {sentiment!r}"
        )

    confidence = data.get("confidence", 0.0)

    try:
        confidence = float(confidence)
    except Exception:
        raise ValueError("Confidence invalide.")

    confidence = max(0.0, min(1.0, confidence))

    review = data.get("review", False)

    if isinstance(review, str):
        review = review.lower() == "true"

    review = bool(review)

    reason = str(data.get("reason", "")).strip()

    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "review": review,
        "reason": reason,
    }


# ============================================================
# APPEL OLLAMA
# ============================================================

def audit_sentiment(title, summary, content):
    """
    Un seul appel à GPT-OSS.

    Aucun retry long.
    En cas d'erreur technique -> exception.
    """

    title = (title or "").strip()
    summary = (summary or "").strip()
    content = (content or "").strip()

    # Pour Google News V2, le contenu complet peut être vide.
    # Dans ce cas GPT-OSS travaille avec titre + résumé disponible.
    if content:
        evidence = f"""
TITRE :
{title}

RÉSUMÉ :
{summary}

CONTENU :
{content}
"""
    else:
        evidence = f"""
TITRE :
{title}

RÉSUMÉ :
{summary}

CONTENU COMPLET :
Non disponible.

Analyse uniquement les informations réellement disponibles ci-dessus.
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": evidence,
            },
        ],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {
            "temperature": 0,
        },
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    result = response.json()

    message = result.get("message", {})
    raw_content = message.get("content", "")

    if not raw_content:
        raise ValueError("Réponse Ollama vide.")

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON GPT-OSS invalide : {raw_content[:500]}"
        ) from exc

    return validate_result(parsed)


# ============================================================
# UTILITAIRES CSV
# ============================================================

def read_csv(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    if not rows:
        # Même avec zéro ligne, créer un fichier exploitable.
        with open(
            path,
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            f.write("")
        return

    fieldnames = []

    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def normalize_sentiment(value):
    value = str(value or "").strip()

    if value in VALID_SENTIMENTS:
        return value

    return ""


# ============================================================
# CLASSIFICATION FINALE
# ============================================================

def determine_category(
    initial_sentiment,
    audit_sentiment_value,
    audit_review,
    content_mismatch,
):
    """
    Aucun mot-clé.
    La catégorie dépend uniquement du résultat de l'audit GPT-OSS
    et des métadonnées déjà présentes.
    """

    if not audit_sentiment_value:
        return "ERROR"

    if initial_sentiment != audit_sentiment_value:
        return "CORRECTED"

    if audit_review or content_mismatch:
        return "REVIEW"

    return "CONFIRMED"


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("VALIDATION SÉMANTIQUE GOOGLE NEWS V2")
    print("=" * 70)
    print()

    if not INPUT_FILE.exists():
        print(f"[ERREUR] Fichier introuvable : {INPUT_FILE}")
        return

    rows = read_csv(INPUT_FILE)

    if not rows:
        print("[ERREUR] Aucun article dans le fichier.")
        return

    # --------------------------------------------------------
    # Articles pertinents uniquement
    # --------------------------------------------------------

    relevant_rows = []

    for row in rows:

        relevant = str(
            row.get("relevant", "")
        ).strip().lower()

        if relevant in {
            "true",
            "1",
            "yes",
            "oui",
        }:
            relevant_rows.append(row)

    print(f"Articles dans CSV       : {len(rows)}")
    print(f"Articles pertinents     : {len(relevant_rows)}")
    print()

    validation_rows = []

    confirmed = []
    corrected = []
    review = []
    errors = []

    initial_counts = {
        "Positive": 0,
        "Neutral": 0,
        "Negative": 0,
    }

    audit_counts = {
        "Positive": 0,
        "Neutral": 0,
        "Negative": 0,
    }

    agreements = 0
    disagreements = 0

    audit_success = 0

    start_time = time.time()

    # --------------------------------------------------------
    # AUDIT
    # --------------------------------------------------------

    for index, row in enumerate(relevant_rows, start=1):

        title = str(
            row.get("title", "")
        ).strip()

        summary = str(
            row.get("summary", "")
        ).strip()

        content = str(
            row.get("content", "")
        ).strip()

        initial_sentiment = normalize_sentiment(
            row.get("sentiment", "")
        )

        if initial_sentiment in initial_counts:
            initial_counts[initial_sentiment] += 1

        print(
            f"[{index}/{len(relevant_rows)}] "
            f"{title[:90]}"
        )

        result = dict(row)

        result["audit_sentiment"] = ""
        result["audit_confidence"] = ""
        result["audit_review"] = ""
        result["audit_reason"] = ""
        result["audit_error"] = ""
        result["agreement"] = ""
        result["final_category"] = ""

        try:

            audit = audit_sentiment(
                title=title,
                summary=summary,
                content=content,
            )

            audited_sentiment = audit["sentiment"]

            audit_counts[audited_sentiment] += 1
            audit_success += 1

            result["audit_sentiment"] = audited_sentiment
            result["audit_confidence"] = audit["confidence"]
            result["audit_review"] = audit["review"]
            result["audit_reason"] = audit["reason"]

            if (
                initial_sentiment
                and initial_sentiment == audited_sentiment
            ):
                result["agreement"] = "MATCH"
                agreements += 1

            elif (
                initial_sentiment
                and initial_sentiment != audited_sentiment
            ):
                result["agreement"] = "DISAGREEMENT"
                disagreements += 1

            else:
                result["agreement"] = ""

            content_mismatch = str(
                row.get("content_mismatch", "")
            ).strip().lower() in {
                "true",
                "1",
                "yes",
            }

            category = determine_category(
                initial_sentiment=initial_sentiment,
                audit_sentiment_value=audited_sentiment,
                audit_review=audit["review"],
                content_mismatch=content_mismatch,
            )

            result["final_category"] = category

            if category == "CONFIRMED":
                confirmed.append(result)

            elif category == "CORRECTED":
                corrected.append(result)

            elif category == "REVIEW":
                review.append(result)

        except Exception as exc:

            error_message = str(exc)

            result["audit_error"] = error_message
            result["final_category"] = "ERROR"

            errors.append(result)

            print(
                f"    -> ERROR : {error_message[:180]}"
            )

        validation_rows.append(result)

    # --------------------------------------------------------
    # STATISTIQUES
    # --------------------------------------------------------

    elapsed = time.time() - start_time

    total = len(relevant_rows)

    print()
    print("=" * 70)
    print("FIN DE LA VALIDATION")
    print("=" * 70)
    print()

    print("ARTICLES")
    print(f"Articles pertinents     : {total}")
    print(f"Audits réussis          : {audit_success}")
    print(f"Erreurs techniques     : {len(errors)}")
    print()

    print("SENTIMENT INITIAL")
    print(
        f"Positive                : "
        f"{initial_counts['Positive']}"
    )
    print(
        f"Neutral                 : "
        f"{initial_counts['Neutral']}"
    )
    print(
        f"Negative               : "
        f"{initial_counts['Negative']}"
    )
    print()

    print("SENTIMENT AUDITÉ")
    print(
        f"Positive                : "
        f"{audit_counts['Positive']}"
    )
    print(
        f"Neutral                 : "
        f"{audit_counts['Neutral']}"
    )
    print(
        f"Negative               : "
        f"{audit_counts['Negative']}"
    )
    print()

    print("ACCORD")
    print(f"Accords                 : {agreements}")
    print(f"Désaccords              : {disagreements}")

    if audit_success:
        agreement_rate = (
            agreements / audit_success
        ) * 100

        print(
            f"Taux d'accord           : "
            f"{agreement_rate:.2f}%"
        )
    else:
        print(
            "Taux d'accord           : N/A"
        )

    print()

    print("CATÉGORIES FINALES")
    print(
        f"CONFIRMED               : "
        f"{len(confirmed)}"
    )
    print(
        f"REVIEW                  : "
        f"{len(review)}"
    )
    print(
        f"CORRECTED               : "
        f"{len(corrected)}"
    )
    print(
        f"ERROR                   : "
        f"{len(errors)}"
    )

    print()

    print("TEMPS")
    print(
        f"Durée totale            : "
        f"{elapsed:.1f} secondes"
    )

    if audit_success:
        print(
            f"Temps moyen/audit      : "
            f"{elapsed / audit_success:.2f} secondes"
        )

    print()

    print("FICHIERS CRÉÉS")

    # --------------------------------------------------------
    # ÉCRITURE DES CSV
    # --------------------------------------------------------

    write_csv(
        OUTPUT_VALIDATION,
        validation_rows,
    )

    suspects = (
        corrected
        + review
        + errors
    )

    write_csv(
        OUTPUT_SUSPECTS,
        suspects,
    )

    write_csv(
        OUTPUT_CONFIRMED,
        confirmed,
    )

    write_csv(
        OUTPUT_CORRECTED,
        corrected,
    )

    write_csv(
        OUTPUT_REVIEW,
        review,
    )

    write_csv(
        OUTPUT_ERRORS,
        errors,
    )

    print(
        f"  {OUTPUT_VALIDATION.name}"
    )
    print(
        f"  {OUTPUT_SUSPECTS.name}"
    )
    print(
        f"  {OUTPUT_CONFIRMED.name}"
    )
    print(
        f"  {OUTPUT_CORRECTED.name}"
    )
    print(
        f"  {OUTPUT_REVIEW.name}"
    )
    print(
        f"  {OUTPUT_ERRORS.name}"
    )

    print()
    print("SQLITE")
    print("AUCUNE MODIFICATION")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()