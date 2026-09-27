# audit_corrected_articles.py

import csv
import json
import time
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "google_news_v2_corrected.csv"

OUTPUT_FILE = (
    BASE_DIR / "google_news_v2_corrected_audit.csv"
)

OUTPUT_SUSPECTS = (
    BASE_DIR / "google_news_v2_corrected_audit_suspects.csv"
)

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL_NAME = "gpt-oss:120b-cloud"

REQUEST_TIMEOUT = 60


# ============================================================
# PROMPT D'AUDIT
# ============================================================

SYSTEM_PROMPT = """
Tu es un auditeur expert en analyse sémantique des articles de presse.

Tu dois auditer une classification de sentiment concernant :

CGI Maroc
Compagnie Générale Immobilière

Le but est de déterminer quel sentiment est le plus défendable
SEMANTIQUEMENT envers CGI.

IMPORTANT :

NE JAMAIS utiliser une classification basée uniquement sur des
mots-clés.

Tu dois comprendre le sens global du contenu disponible.

Ne déduis pas automatiquement :

- nomination = Positive
- récompense = Positive
- investissement = Positive
- projet immobilier = Positive
- chiffre d'affaires = Positive
- condamnation = Negative
- procès = Negative
- justice = Negative
- radiation de la Bourse = Negative
- départ d'un dirigeant = Negative
- problème immobilier = Negative

Ces événements doivent être interprétés dans leur contexte.

Une information peut être importante pour CGI sans exprimer
un sentiment positif ou négatif envers CGI.

RÈGLES :

Positive :
Le contenu présente CGI de manière clairement favorable,
valorisante ou positive, ou reconnaît explicitement une
performance, réussite, distinction ou appréciation favorable
concernant CGI.

Negative :
Le contenu présente CGI de manière clairement défavorable,
ou décrit un événement négatif directement lié à CGI avec
un impact clairement défavorable.

Neutral :
Le contenu est principalement factuel, descriptif,
informatif, stratégique, financier ou contextuel sans
évaluation clairement positive ou négative de CGI.

Review :
true si l'interprétation est ambiguë, si le contenu est
insuffisant, si le sentiment envers CGI n'est pas explicite,
ou si deux interprétations raisonnables existent.

IMPORTANT :

Le sentiment doit concerner CGI elle-même.

Un article concernant principalement :
- une personne,
- une autre société,
- une filiale,
- le secteur immobilier,
- un projet,
- une procédure,
- une opération financière,

ne doit pas automatiquement être classé Positive ou Negative.

Il faut déterminer si le contenu exprime réellement une
évaluation favorable ou défavorable de CGI.

Tu disposes de deux classifications :

INITIAL :
classification originale

AUDIT :
classification issue d'un précédent passage GPT-OSS

Tu dois décider quelle classification est la plus
sémantiquement défendable.

Réponds UNIQUEMENT avec ce JSON :

{
  "final_sentiment": "Positive|Neutral|Negative",
  "initial_correct": true,
  "audit_correct": true,
  "review": true,
  "confidence": 0.0,
  "reason": "explication sémantique courte",
  "decision": "KEEP_INITIAL|KEEP_AUDIT|REVIEW"
}

Règles pour decision :

KEEP_INITIAL :
la classification initiale est la plus défendable.

KEEP_AUDIT :
la classification de l'audit est la plus défendable.

REVIEW :
aucune des deux classifications ne peut être considérée
comme suffisamment certaine sans vérification humaine.

Ne choisis pas REVIEW simplement parce que l'article est
factuel. Utilise REVIEW lorsque l'interprétation du sentiment
est réellement ambiguë ou insuffisamment établie.

La réponse doit être du JSON valide.
"""


# ============================================================
# LECTURE CSV
# ============================================================

def read_csv(path):

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        return list(csv.DictReader(f))


# ============================================================
# ÉCRITURE CSV
# ============================================================

def write_csv(path, rows):

    if not rows:
        with open(
            path,
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as f:
            f.write("")

        return

    fields = []

    for row in rows:
        for key in row:

            if key not in fields:
                fields.append(key)

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# VALIDATION RÉPONSE GPT
# ============================================================

VALID_SENTIMENTS = {
    "Positive",
    "Neutral",
    "Negative"
}


VALID_DECISIONS = {
    "KEEP_INITIAL",
    "KEEP_AUDIT",
    "REVIEW"
}


def validate_response(data):

    if not isinstance(data, dict):
        raise ValueError(
            "Réponse JSON invalide."
        )

    sentiment = data.get(
        "final_sentiment"
    )

    if sentiment not in VALID_SENTIMENTS:

        raise ValueError(
            f"Sentiment invalide : {sentiment}"
        )

    decision = data.get(
        "decision"
    )

    if decision not in VALID_DECISIONS:

        raise ValueError(
            f"Decision invalide : {decision}"
        )

    confidence = data.get(
        "confidence",
        0
    )

    try:
        confidence = float(
            confidence
        )

    except Exception:

        raise ValueError(
            "Confidence invalide."
        )

    confidence = max(
        0,
        min(1, confidence)
    )

    review = data.get(
        "review",
        False
    )

    if isinstance(review, str):

        review = (
            review.lower()
            == "true"
        )

    review = bool(review)

    initial_correct = data.get(
        "initial_correct",
        False
    )

    audit_correct = data.get(
        "audit_correct",
        False
    )

    if isinstance(
        initial_correct,
        str
    ):

        initial_correct = (
            initial_correct.lower()
            == "true"
        )

    if isinstance(
        audit_correct,
        str
    ):

        audit_correct = (
            audit_correct.lower()
            == "true"
        )

    reason = str(
        data.get(
            "reason",
            ""
        )
    ).strip()

    return {
        "final_sentiment": sentiment,
        "initial_correct": bool(
            initial_correct
        ),
        "audit_correct": bool(
            audit_correct
        ),
        "review": review,
        "confidence": confidence,
        "reason": reason,
        "decision": decision
    }


# ============================================================
# APPEL GPT-OSS
# ============================================================

def audit_article(row):

    title = str(
        row.get(
            "title",
            ""
        )
    ).strip()

    summary = str(
        row.get(
            "summary",
            ""
        )
    ).strip()

    content = str(
        row.get(
            "content",
            ""
        )
    ).strip()

    initial = str(
        row.get(
            "sentiment",
            ""
        )
    ).strip()

    previous_audit = str(
        row.get(
            "audit_sentiment",
            ""
        )
    ).strip()

    reason_initial = str(
        row.get(
            "reason",
            ""
        )
    ).strip()

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
"""

    user_prompt = f"""
Analyse cet article.

CLASSIFICATION INITIALE :
{initial}

CLASSIFICATION AUDIT PRÉCÉDENTE :
{previous_audit}

RAISON INITIALE DISPONIBLE :
{reason_initial}

{evidence}

Détermine quelle classification est la plus défendable
sémantiquement envers CGI.
"""

    payload = {

        "model": MODEL_NAME,

        "messages": [

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": user_prompt
            }

        ],

        "stream": False,

        "format": "json",

        "think": False,

        "options": {
            "temperature": 0
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    raw = (
        data
        .get("message", {})
        .get("content", "")
    )

    if not raw:

        raise ValueError(
            "Réponse GPT-OSS vide."
        )

    try:

        parsed = json.loads(
            raw
        )

    except json.JSONDecodeError as exc:

        raise ValueError(
            f"JSON invalide : {raw[:500]}"
        ) from exc

    return validate_response(
        parsed
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("AUDIT DES ARTICLES CORRECTED")
    print("=" * 70)
    print()

    if not INPUT_FILE.exists():

        print(
            f"[ERREUR] "
            f"Fichier introuvable : {INPUT_FILE}"
        )

        return

    rows = read_csv(
        INPUT_FILE
    )

    print(
        f"Articles à auditer : {len(rows)}"
    )

    print()

    results = []

    suspects = []

    keep_initial = 0
    keep_audit = 0
    human_review = 0
    errors = 0

    start = time.time()

    for index, row in enumerate(
        rows,
        start=1
    ):

        title = str(
            row.get(
                "title",
                ""
            )
        ).strip()

        print(
            f"[{index}/{len(rows)}] "
            f"{title[:100]}"
        )

        result = dict(row)

        result[
            "audit_final_sentiment"
        ] = ""

        result[
            "audit_decision"
        ] = ""

        result[
            "audit_confidence"
        ] = ""

        result[
            "audit_review"
        ] = ""

        result[
            "audit_reason"
        ] = ""

        result[
            "audit_error"
        ] = ""

        try:

            audit = audit_article(
                row
            )

            result[
                "audit_final_sentiment"
            ] = audit[
                "final_sentiment"
            ]

            result[
                "audit_decision"
            ] = audit[
                "decision"
            ]

            result[
                "audit_confidence"
            ] = audit[
                "confidence"
            ]

            result[
                "audit_review"
            ] = audit[
                "review"
            ]

            result[
                "audit_reason"
            ] = audit[
                "reason"
            ]

            decision = audit[
                "decision"
            ]

            if decision == "KEEP_INITIAL":

                keep_initial += 1

            elif decision == "KEEP_AUDIT":

                keep_audit += 1

            elif decision == "REVIEW":

                human_review += 1

                suspects.append(
                    result
                )

            results.append(
                result
            )

        except Exception as exc:

            errors += 1

            result[
                "audit_error"
            ] = str(exc)

            result[
                "audit_decision"
            ] = "ERROR"

            suspects.append(
                result
            )

            results.append(
                result
            )

            print(
                f"    ERROR : "
                f"{str(exc)[:200]}"
            )

    elapsed = (
        time.time()
        - start
    )

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    write_csv(
        OUTPUT_FILE,
        results
    )

    write_csv(
        OUTPUT_SUSPECTS,
        suspects
    )

    # ========================================================
    # RAPPORT
    # ========================================================

    print()
    print("=" * 70)
    print("FIN DE L'AUDIT")
    print("=" * 70)
    print()

    print("ARTICLES")
    print(
        f"Articles audités      : {len(rows)}"
    )

    print(
        f"KEEP_INITIAL          : "
        f"{keep_initial}"
    )

    print(
        f"KEEP_AUDIT            : "
        f"{keep_audit}"
    )

    print(
        f"REVIEW HUMAIN         : "
        f"{human_review}"
    )

    print(
        f"ERROR                 : "
        f"{errors}"
    )

    print()

    print("TEMPS")
    print(
        f"Durée totale          : "
        f"{elapsed:.1f} secondes"
    )

    if rows:

        print(
            f"Temps moyen           : "
            f"{elapsed / len(rows):.2f} s/article"
        )

    print()

    print("FICHIERS")

    print(
        f"  {OUTPUT_FILE.name}"
    )

    print(
        f"  {OUTPUT_SUSPECTS.name}"
    )

    print()

    print("SQLITE")
    print(
        "AUCUNE MODIFICATION"
    )

    print()

    print("=" * 70)


if __name__ == "__main__":
    main()