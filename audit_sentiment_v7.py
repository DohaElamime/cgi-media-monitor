import os
import json
import time
import requests
import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "sentiment_v7_results.csv"
OUTPUT_FILE = "sentiment_v7_audit.csv"
ERROR_FILE = "sentiment_v7_audit_errors.csv"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gpt-oss:120b-cloud"

REQUEST_TIMEOUT = 120


# ============================================================
# PROMPT AUDIT
# ============================================================

AUDIT_PROMPT = """
Tu es un auditeur expert en analyse sémantique de sentiment.

Tu dois vérifier le sentiment initial attribué à un article concernant
la Compagnie Générale Immobilière (CGI Maroc).

IMPORTANT :
- Ne fais PAS de classification par mots-clés.
- Analyse le sens global de l'article.
- Le sentiment doit concerner CGI elle-même.
- Une nomination n'est pas automatiquement positive.
- Un investissement n'est pas automatiquement positif.
- Un projet immobilier n'est pas automatiquement positif.
- Une procédure judiciaire n'est pas automatiquement négative.
- Une baisse d'action n'est pas automatiquement négative sans contexte.
- Un article sectoriel n'exprime pas nécessairement un sentiment envers CGI.
- Une filiale n'implique pas automatiquement un sentiment envers CGI.
- Une mention factuelle de CGI n'est pas automatiquement positive ou négative.
- Si le contenu ne permet pas de déterminer clairement le sentiment,
  choisis Neutral et mets review=true.
- Si l'article parle principalement d'un autre sujet ou d'une autre
  organisation et que CGI n'est qu'une mention factuelle, choisis Neutral.

Le but est de vérifier sémantiquement le sentiment initial.

Réponds UNIQUEMENT avec un JSON valide :

{
  "sentiment": "Positive|Neutral|Negative",
  "confidence": 0.0,
  "review": true,
  "reason": "explication courte et précise"
}
"""


# ============================================================
# OLLAMA
# ============================================================

def call_ollama(title, summary, content):

    user_prompt = f"""
ARTICLE À AUDITER

TITRE :
{title}

RÉSUMÉ :
{summary}

CONTENU :
{content}

Analyse maintenant le sentiment envers CGI.
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": AUDIT_PROMPT
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

    if "message" not in data:
        raise ValueError("Réponse Ollama invalide : champ message absent.")

    raw = data["message"].get("content", "")

    if not raw:
        raise ValueError("Réponse Ollama vide.")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON invalide retourné par Ollama : {raw[:500]}"
        ) from e

    sentiment = result.get("sentiment")

    if sentiment not in ["Positive", "Neutral", "Negative"]:
        raise ValueError(
            f"Sentiment invalide : {sentiment}"
        )

    confidence = result.get("confidence", 0.0)
    review = result.get("review", False)
    reason = result.get("reason", "")

    return {
        "sentiment": sentiment,
        "confidence": float(confidence),
        "review": bool(review),
        "reason": str(reason)
    }


# ============================================================
# UTILITAIRES
# ============================================================

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def get_content(row):

    # Priorité au contenu complet
    content = safe_text(row.get("content", ""))

    if content:
        return content, "FULL_CONTENT"

    # Fallback résumé
    summary = safe_text(row.get("summary", ""))

    if summary:
        return summary, "SUMMARY"

    return "", "NONE"


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("AUDIT SENTIMENT V7")
    print("=" * 80)

    if not os.path.exists(INPUT_FILE):
        print(f"\nERREUR : fichier introuvable : {INPUT_FILE}")
        return

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    print(f"\nFichier chargé : {INPUT_FILE}")
    print(f"Nombre total de lignes : {len(df)}")

    print("\nColonnes disponibles :")
    print(list(df.columns))

    # --------------------------------------------------------
    # Vérification colonne sentiment
    # --------------------------------------------------------

    if "sentiment" not in df.columns:
        print("\nERREUR : colonne 'sentiment' absente.")
        return

    # --------------------------------------------------------
    # Articles à auditer
    # --------------------------------------------------------

    # Seulement les analyses valides
    df = df[
        df["sentiment"].isin(
            ["Positive", "Neutral", "Negative"]
        )
    ].copy()

    print(f"\nArticles à auditer : {len(df)}")

    # --------------------------------------------------------
    # Vérification contenu
    # --------------------------------------------------------

    if "content" in df.columns:
        content_count = df["content"].fillna("").astype(str).str.strip().ne("").sum()
    else:
        content_count = 0

    if "summary" in df.columns:
        summary_count = df["summary"].fillna("").astype(str).str.strip().ne("").sum()
    else:
        summary_count = 0

    print(f"Contenus disponibles : {content_count}")
    print(f"Résumés disponibles  : {summary_count}")

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    results = []
    errors = []

    start_total = time.time()

    for index, row in df.iterrows():

        start = time.time()

        title = safe_text(row.get("title", ""))
        summary = safe_text(row.get("summary", ""))

        content, content_source = get_content(row)

        initial_sentiment = safe_text(
            row.get("sentiment", "")
        )

        try:

            if not content:
                raise ValueError(
                    "Article sans contenu ni résumé."
                )

            audit = call_ollama(
                title=title,
                summary=summary,
                content=content
            )

            audit_sentiment = audit["sentiment"]

            agreement = (
                initial_sentiment == audit_sentiment
            )

            # ------------------------------------------------
            # Décision
            # ------------------------------------------------

            if audit["review"]:
                decision = "REVIEW_HUMAN"

            elif agreement:
                decision = "KEEP_INITIAL"

            else:
                decision = "KEEP_AUDIT"

            final_sentiment = (
                audit_sentiment
                if decision == "KEEP_AUDIT"
                else initial_sentiment
            )

            results.append({
                "title": title,
                "source": safe_text(row.get("source", "")),
                "date": safe_text(row.get("date", "")),
                "resolved_url": safe_text(
                    row.get("resolved_url", "")
                ),

                "initial_sentiment": initial_sentiment,

                "audit_sentiment": audit_sentiment,
                "audit_confidence": audit["confidence"],
                "audit_review": audit["review"],
                "audit_reason": audit["reason"],

                "agreement": agreement,
                "decision": decision,
                "final_sentiment": final_sentiment,

                "content_source": content_source,
                "content_chars": len(content),
                "content_words": len(content.split()),

                "audit_time_sec": round(
                    time.time() - start,
                    2
                )
            })

        except Exception as e:

            errors.append({
                "title": title,
                "source": safe_text(row.get("source", "")),
                "resolved_url": safe_text(
                    row.get("resolved_url", "")
                ),
                "initial_sentiment": initial_sentiment,
                "error_type": type(e).__name__,
                "error": str(e)
            })

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    results_df = pd.DataFrame(results)
    errors_df = pd.DataFrame(errors)

    results_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    errors_df.to_csv(
        ERROR_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Statistiques
    # --------------------------------------------------------

    total_time = time.time() - start_total

    audits_ok = len(results_df)
    errors_count = len(errors_df)

    keep_initial = 0
    keep_audit = 0
    review_human = 0
    agreements = 0
    disagreements = 0

    if audits_ok > 0:

        keep_initial = (
            results_df["decision"] == "KEEP_INITIAL"
        ).sum()

        keep_audit = (
            results_df["decision"] == "KEEP_AUDIT"
        ).sum()

        review_human = (
            results_df["decision"] == "REVIEW_HUMAN"
        ).sum()

        agreements = (
            results_df["agreement"] == True
        ).sum()

        disagreements = (
            results_df["agreement"] == False
        ).sum()

    agreement_rate = (
        agreements / audits_ok * 100
        if audits_ok > 0
        else 0
    )

    print("\n" + "=" * 80)
    print("AUDIT SENTIMENT V7 TERMINÉ")
    print("=" * 80)

    print(f"\nArticles à auditer       : {len(df)}")
    print(f"Audits réussis           : {audits_ok}")
    print(f"Erreurs techniques       : {errors_count}")

    print("\nDÉCISIONS")
    print(f"KEEP_INITIAL             : {keep_initial}")
    print(f"KEEP_AUDIT               : {keep_audit}")
    print(f"REVIEW_HUMAN             : {review_human}")

    print("\nCOMPARAISON")
    print(f"Accords                  : {agreements}")
    print(f"Désaccords               : {disagreements}")
    print(f"Taux d'accord            : {agreement_rate:.2f}%")

    corrections = keep_audit

    print(f"Corrections proposées    : {corrections}")

    print("\nSENTIMENT FINAL PROVISOIRE")

    if audits_ok > 0:

        final_counts = (
            results_df["final_sentiment"]
            .value_counts()
        )

        print(
            f"Positive                 : "
            f"{final_counts.get('Positive', 0)}"
        )

        print(
            f"Neutral                  : "
            f"{final_counts.get('Neutral', 0)}"
        )

        print(
            f"Negative                 : "
            f"{final_counts.get('Negative', 0)}"
        )

    else:

        print("Positive                 : 0")
        print("Neutral                  : 0")
        print("Negative                 : 0")

    print("\nTEMPS")
    print(f"Durée totale             : {total_time:.1f} sec")

    if audits_ok:
        print(
            f"Temps moyen/article     : "
            f"{total_time / audits_ok:.2f} sec"
        )
    else:
        print("Temps moyen/article     : 0.00 sec")

    print(f"\nRésultats : {os.path.abspath(OUTPUT_FILE)}")
    print(f"Erreurs   : {os.path.abspath(ERROR_FILE)}")

    print("\nSQLite                   : AUCUNE MODIFICATION")
    print("Pipeline principal       : NON EXÉCUTÉ")

    print("=" * 80)


if __name__ == "__main__":
    main()