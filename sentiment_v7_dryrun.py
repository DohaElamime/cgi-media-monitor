import os
import time
import json
import requests
import pandas as pd

# ============================================================
# CONFIG
# ============================================================

INPUT_FILE = "google_news_v7_results.csv"
OUTPUT_FILE = "sentiment_v7_results.csv"
ERROR_FILE = "sentiment_v7_errors.csv"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gpt-oss:120b-cloud"
REQUEST_TIMEOUT = 180


# ============================================================
# PROMPT
# ============================================================

SYSTEM_PROMPT = """
Tu es un expert en analyse sémantique de sentiment.

Ta tâche est de déterminer le sentiment exprimé envers
la Compagnie Générale Immobilière (CGI Maroc).

IMPORTANT :

1. Tu dois analyser le sens global du contenu.
2. INTERDICTION d'utiliser une classification basée uniquement
   sur des mots-clés.
3. Le sentiment doit concerner CGI elle-même.
4. Une nomination n'est PAS automatiquement Positive.
5. Un investissement n'est PAS automatiquement Positive.
6. Un projet immobilier n'est PAS automatiquement Positive.
7. Une procédure judiciaire n'est PAS automatiquement Negative.
8. Une baisse d'action n'est PAS automatiquement Negative sans contexte.
9. Un article sectoriel n'exprime pas nécessairement un sentiment envers CGI.
10. Une mention factuelle de CGI n'est pas automatiquement Positive.
11. Une filiale n'implique pas automatiquement un sentiment envers CGI.
12. Si l'article est principalement descriptif/factuel concernant CGI,
    utilise Neutral.
13. Si le contenu est ambigu ou insuffisant, utilise Neutral et review=true.
14. Ne suppose jamais que Positive ou Negative est correct uniquement
    à partir du titre.

Définitions :

Positive :
Le contenu présente CGI de manière favorable, avec des éléments
explicitement positifs concernant CGI, ses performances, résultats,
réalisations, réputation, développement ou perception.

Negative :
Le contenu présente CGI de manière défavorable, avec des éléments
explicitement négatifs concernant CGI : difficultés, accusations,
controverses, pertes, problèmes, critiques, etc.

Neutral :
Le contenu est factuel, descriptif, équilibré, principalement consacré
à un autre sujet, ou ne permet pas d'établir clairement un sentiment
envers CGI.

Retourne UNIQUEMENT un JSON valide :

{
  "sentiment": "Positive|Neutral|Negative",
  "score": 0.0,
  "confidence": 0.0,
  "margin": 0.0,
  "review": false,
  "reason": "explication courte",
  "content_mismatch": false
}
"""


# ============================================================
# OLLAMA
# ============================================================

def call_ollama(title, content):

    user_prompt = f"""
TITRE :
{title}

CONTENU COMPLET :
{content}

Analyse le sentiment envers CGI Maroc.
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

    if "message" not in data:
        raise ValueError("Réponse Ollama invalide.")

    raw = data["message"].get("content", "")

    if not raw:
        raise ValueError("Réponse Ollama vide.")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON invalide : {raw[:500]}"
        ) from e

    sentiment = result.get("sentiment")

    if sentiment not in ["Positive", "Neutral", "Negative"]:
        raise ValueError(
            f"Sentiment invalide : {sentiment}"
        )

    return {
        "sentiment": sentiment,
        "score": float(result.get("score", 0.0)),
        "confidence": float(result.get("confidence", 0.0)),
        "margin": float(result.get("margin", 0.0)),
        "review": bool(result.get("review", False)),
        "reason": str(result.get("reason", "")),
        "content_mismatch": bool(
            result.get("content_mismatch", False)
        )
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("SENTIMENT V7 DRY-RUN")
    print("=" * 80)

    # --------------------------------------------------------
    # Chargement
    # --------------------------------------------------------

    if not os.path.exists(INPUT_FILE):
        print(f"ERREUR : {INPUT_FILE} introuvable.")
        return

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    print(f"\nArticles CSV             : {len(df)}")

    # --------------------------------------------------------
    # Vérification contenu
    # --------------------------------------------------------

    if "content" not in df.columns:
        print("\nERREUR CRITIQUE : colonne 'content' absente.")
        return

    # --------------------------------------------------------
    # Articles pertinents
    # --------------------------------------------------------

    # V7 reçoit uniquement les articles pertinents depuis
    # le fichier d'extraction.
    #
    # On garde les articles avec du contenu exploitable.
    # Les articles sans contenu seront enregistrés comme erreurs.

    relevant_df = df.copy()

    print(f"Articles à analyser      : {len(relevant_df)}")

    content_available = (
        relevant_df["content"]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    )

    print(
        f"Contenu disponible       : "
        f"{content_available.sum()}"
    )

    print(
        f"Contenu absent           : "
        f"{(~content_available).sum()}"
    )

    # --------------------------------------------------------
    # Analyse
    # --------------------------------------------------------

    results = []
    errors = []

    start_total = time.time()

    for index, row in relevant_df.iterrows():

        start = time.time()

        title = (
            "" if pd.isna(row.get("title"))
            else str(row.get("title")).strip()
        )

        source = (
            "" if pd.isna(row.get("source"))
            else str(row.get("source")).strip()
        )

        date = (
            "" if pd.isna(row.get("date"))
            else str(row.get("date")).strip()
        )

        google_news_url = (
            "" if pd.isna(row.get("google_news_url"))
            else str(row.get("google_news_url")).strip()
        )

        resolved_url = (
            "" if pd.isna(row.get("resolved_url"))
            else str(row.get("resolved_url")).strip()
        )

        content = (
            "" if pd.isna(row.get("content"))
            else str(row.get("content")).strip()
        )

        extraction_status = (
            "" if pd.isna(row.get("extraction_status"))
            else str(row.get("extraction_status")).strip()
        )

        extraction_method = (
            "" if pd.isna(row.get("extraction_method"))
            else str(row.get("extraction_method")).strip()
        )

        try:

            if not content:
                raise ValueError(
                    "Article sans contenu."
                )

            analysis = call_ollama(
                title=title,
                content=content
            )

            elapsed = time.time() - start

            # IMPORTANT :
            # On conserve maintenant le contenu complet.
            results.append({

                # GPT-OSS
                "sentiment": analysis["sentiment"],
                "score": analysis["score"],
                "confidence": analysis["confidence"],
                "margin": analysis["margin"],
                "review": analysis["review"],
                "reason": analysis["reason"],
                "content_mismatch": analysis["content_mismatch"],

                # Modèle
                "model": MODEL_NAME,
                "device": "Ollama Cloud",

                # Article
                "title": title,
                "source": source,
                "date": date,
                "google_news_url": google_news_url,
                "resolved_url": resolved_url,

                # IMPORTANT POUR L'AUDIT
                "content": content,

                # Métadonnées extraction
                "extraction_status": extraction_status,
                "extraction_method": extraction_method,
                "content_chars": len(content),
                "content_words": len(content.split()),

                # Temps
                "analysis_time_sec": round(
                    elapsed,
                    2
                )
            })

        except Exception as e:

            errors.append({
                "title": title,
                "source": source,
                "date": date,
                "google_news_url": google_news_url,
                "resolved_url": resolved_url,
                "error_type": type(e).__name__,
                "error": str(e)
            })

    # --------------------------------------------------------
    # DataFrames
    # --------------------------------------------------------

    results_df = pd.DataFrame(results)
    errors_df = pd.DataFrame(errors)

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

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

    positive = 0
    neutral = 0
    negative = 0
    review_count = 0
    mismatch_count = 0

    if len(results_df) > 0:

        positive = (
            results_df["sentiment"] == "Positive"
        ).sum()

        neutral = (
            results_df["sentiment"] == "Neutral"
        ).sum()

        negative = (
            results_df["sentiment"] == "Negative"
        ).sum()

        review_count = (
            results_df["review"] == True
        ).sum()

        mismatch_count = (
            results_df["content_mismatch"] == True
        ).sum()

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print("\n" + "=" * 80)
    print("SENTIMENT V7 TERMINÉ")
    print("=" * 80)

    print(
        f"\nArticles pertinents     : {len(relevant_df)}"
    )

    print(
        f"Analyses réussies       : {len(results_df)}"
    )

    print(
        f"Erreurs techniques      : {len(errors_df)}"
    )

    print("\nSENTIMENT")

    print(
        f"Positive                : {positive}"
    )

    print(
        f"Neutral                 : {neutral}"
    )

    print(
        f"Negative               : {negative}"
    )

    print("\nQUALITÉ")

    print(
        f"Review                  : {review_count}"
    )

    print(
        f"Content mismatch        : {mismatch_count}"
    )

    print("\nTEMPS")

    print(
        f"Durée totale            : {total_time:.1f} sec"
    )

    if len(results_df) > 0:
        print(
            f"Temps moyen/article     : "
            f"{total_time / len(results_df):.2f} sec"
        )
    else:
        print(
            "Temps moyen/article     : 0.00 sec"
        )

    print(
        f"\nRésultats : "
        f"{os.path.abspath(OUTPUT_FILE)}"
    )

    print(
        f"Erreurs   : "
        f"{os.path.abspath(ERROR_FILE)}"
    )

    print(
        "\nSQLite                  : AUCUNE MODIFICATION"
    )

    print(
        "Pipeline principal      : NON EXÉCUTÉ"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()