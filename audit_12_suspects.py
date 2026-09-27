# ============================================================
# audit_12_suspects.py
# ============================================================
# Audit sémantique final des 12 cas suspects
#
# Entrée :
#   sentiment_v7_suspects.csv
#
# Sortie :
#   sentiment_v7_suspects_final.csv
#
# Modèle :
#   GPT-OSS 120B Cloud via Ollama
#
# IMPORTANT :
#   - Aucun mot-clé pour déterminer le sentiment
#   - Aucun accès / aucune modification SQLite
#   - Analyse basée sur le sens global de l'article
#   - Le sentiment doit concerner CGI elle-même
# ============================================================

import os
import json
import time
import requests
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "sentiment_v7_suspects.csv"
OUTPUT_FILE = "sentiment_v7_suspects_final.csv"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gpt-oss:120b-cloud"

REQUEST_TIMEOUT = 180


# ============================================================
# PROMPT SÉMANTIQUE
# ============================================================

SYSTEM_PROMPT = """
Tu es un auditeur expert en analyse sémantique de sentiment dans les médias.

Ta mission est d'analyser des articles de presse concernant CGI
(Compagnie Générale Immobilière).

IMPORTANT :
Le sentiment doit représenter le TON et l'IMPACT SÉMANTIQUE de l'article
À L'ÉGARD DE CGI elle-même.

Tu dois analyser le sens global du contenu et non rechercher simplement
des mots positifs ou négatifs.

============================================================
RÈGLES FONDAMENTALES
============================================================

1. PAS DE CLASSIFICATION PAR MOTS-CLÉS

Ne déduis jamais le sentiment simplement parce qu'un article contient
un mot ou une expression apparemment positive ou négative.

Analyse :
- le contexte ;
- le sujet réel de l'article ;
- les faits rapportés ;
- la manière dont CGI est présentée ;
- les conséquences décrites pour CGI ;
- le ton global de l'article.

------------------------------------------------------------

2. LE SENTIMENT DOIT CONCERNER CGI

Un article peut parler de CGI sans exprimer de sentiment envers CGI.

Exemples :
- article sur une autre entreprise où CGI est seulement citée ;
- article sur le secteur immobilier ;
- article sur une personne liée à CGI ;
- article sur une nomination ;
- article sur une procédure administrative ;
- article décrivant simplement un événement.

Dans ces situations, le sentiment peut être NEUTRAL.

------------------------------------------------------------

3. NOMINATION ≠ POSITIF AUTOMATIQUE

Une nomination ou une promotion concernant CGI ne signifie pas
automatiquement que le sentiment est positif.

Si l'article présente uniquement :
- le nom de la personne ;
- sa fonction ;
- son parcours ;
- la nomination ;

sans jugement favorable ou défavorable concernant CGI,
la classification doit généralement être NEUTRAL.

------------------------------------------------------------

4. PROJET / INVESTISSEMENT ≠ POSITIF AUTOMATIQUE

La présence de :
- projet immobilier ;
- investissement ;
- construction ;
- développement ;
- partenariat ;
- nouveau programme ;

ne signifie pas automatiquement POSITIVE.

Il faut déterminer comment CGI est réellement présentée
dans l'ensemble de l'article.

------------------------------------------------------------

5. PROCÉDURE / JUSTICE ≠ NÉGATIF AUTOMATIQUE

La présence de :
- justice ;
- enquête ;
- audition ;
- affaire ;
- procédure ;
- tribunal ;
- litige ;

ne suffit pas pour classer l'article NEGATIVE.

Il faut analyser le contexte et la manière dont CGI est présentée.

------------------------------------------------------------

6. OPR / DELISTING ≠ NÉGATIF AUTOMATIQUE

Une opération de retrait de cotation, OPR ou changement stratégique
ne doit pas être classée NEGATIVE uniquement à cause de sa nature.

Analyse ce que l'article dit réellement de CGI.

------------------------------------------------------------

7. BAISSE DU COURS ≠ NÉGATIF AUTOMATIQUE

Une baisse du cours de l'action CGI peut être un élément négatif,
mais il faut vérifier si l'article présente réellement cette situation
comme défavorable à CGI.

Analyse le contexte global.

------------------------------------------------------------

8. ARTICLE SECTORIEL

Si l'article traite principalement :
- du marché immobilier ;
- du secteur ;
- de la réglementation ;
- de la fiscalité ;
- de l'économie ;

et que CGI n'est qu'une référence secondaire,
ne force pas un sentiment envers CGI.

------------------------------------------------------------

9. ARTICLE SUR UNE FILIALE

Une filiale ou une société liée à CGI ne doit pas automatiquement
être considérée comme CGI.

Détermine si le contenu exprime réellement quelque chose concernant
CGI elle-même.

------------------------------------------------------------

10. ARTICLE FACTUEL

Si l'article rapporte principalement des faits sans jugement clair
sur CGI :

=> NEUTRAL

------------------------------------------------------------

11. AMBIGUÏTÉ

Si les informations disponibles ne permettent pas de déterminer
raisonnablement le sentiment :

=> NEUTRAL
=> review = true

Ne force jamais une classification.

------------------------------------------------------------

12. CONTENU INSUFFISANT

Si le contenu est trop court, incomplet ou ne permet pas de comprendre
le contexte :

=> NEUTRAL
=> review = true

============================================================
DÉFINITION DES SENTIMENTS
============================================================

POSITIVE :
L'article présente CGI de manière globalement favorable, valorisante
ou décrit clairement des éléments favorables à CGI.

NEGATIVE :
L'article présente CGI de manière globalement défavorable, critique,
préjudiciable ou décrit clairement des éléments négatifs concernant CGI.

NEUTRAL :
L'article est principalement factuel, descriptif, ambigu ou ne permet
pas d'établir un sentiment clair envers CGI.

============================================================
REVIEW
============================================================

review = true si :
- le contenu est ambigu ;
- plusieurs interprétations raisonnables existent ;
- CGI n'est pas le sujet principal ;
- le contenu ne permet pas de déterminer clairement le sentiment ;
- le contexte est insuffisant ;
- le jugement dépend fortement d'une interprétation.

review = false uniquement lorsque le sentiment est suffisamment clair.

============================================================
COMPARAISON AVEC LES CLASSIFICATIONS EXISTANTES
============================================================

Le fichier fournit :
- initial_sentiment
- audit_sentiment

Ces valeurs sont des informations de comparaison uniquement.

Ne suppose jamais que l'une des deux est correcte.

Tu dois refaire ton propre jugement sémantique à partir du contenu.

============================================================
DÉCISION FINALE
============================================================

Après ton analyse, retourne également :

KEEP_INITIAL
si initial_sentiment est le meilleur choix et que l'analyse est suffisamment claire.

KEEP_AUDIT
si audit_sentiment est le meilleur choix et que l'analyse est suffisamment claire.

REVIEW_HUMAN
si le cas reste suffisamment ambigu pour nécessiter une validation humaine.

IMPORTANT :
Si review = true, la décision doit être REVIEW_HUMAN.

============================================================
FORMAT DE SORTIE
============================================================

Retourne UNIQUEMENT un JSON valide :

{
  "sentiment": "Positive|Neutral|Negative",
  "confidence": 0.0,
  "review": true,
  "decision": "KEEP_INITIAL|KEEP_AUDIT|REVIEW_HUMAN",
  "reason": "Explication courte et sémantique de la décision"
}

confidence doit être comprise entre 0 et 1.

Ne retourne aucun Markdown.
Ne retourne aucun texte avant ou après le JSON.
"""


# ============================================================
# APPEL OLLAMA
# ============================================================

def call_ollama(title, content, initial_sentiment, audit_sentiment):
    """
    Envoie un article à GPT-OSS 120B Cloud.
    """

    user_prompt = f"""
Analyse l'article suivant.

============================================================
TITRE
============================================================

{title}

============================================================
CONTENU COMPLET
============================================================

{content}

============================================================
CLASSIFICATIONS EXISTANTES
============================================================

Sentiment initial :
{initial_sentiment}

Sentiment du premier audit :
{audit_sentiment}

============================================================
MISSION
============================================================

Refais une analyse sémantique indépendante.

Détermine le sentiment réel de l'article envers CGI.

Ne te contente pas de choisir entre les deux classifications
existantes.

Si le contenu est ambigu ou insuffisant :
- sentiment = Neutral
- review = true
- decision = REVIEW_HUMAN

Retourne uniquement le JSON demandé.
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
        raise ValueError("Réponse Ollama invalide : champ 'message' absent.")

    raw_content = data["message"].get("content", "")

    if not raw_content:
        raise ValueError("Réponse Ollama vide.")

    return raw_content


# ============================================================
# VALIDATION DU JSON
# ============================================================

def validate_result(result):
    """
    Vérifie et normalise la réponse du modèle.
    """

    if not isinstance(result, dict):
        raise ValueError("Résultat JSON invalide.")

    sentiment = result.get("sentiment")
    confidence = result.get("confidence")
    review = result.get("review")
    decision = result.get("decision")
    reason = result.get("reason")

    valid_sentiments = {
        "Positive",
        "Neutral",
        "Negative"
    }

    valid_decisions = {
        "KEEP_INITIAL",
        "KEEP_AUDIT",
        "REVIEW_HUMAN"
    }

    if sentiment not in valid_sentiments:
        raise ValueError(
            f"Sentiment invalide : {sentiment}"
        )

    if decision not in valid_decisions:
        raise ValueError(
            f"Décision invalide : {decision}"
        )

    if not isinstance(review, bool):
        raise ValueError(
            "Le champ review doit être booléen."
        )

    try:
        confidence = float(confidence)
    except Exception:
        raise ValueError(
            "Confidence invalide."
        )

    confidence = max(0.0, min(1.0, confidence))

    if not isinstance(reason, str):
        reason = str(reason)

    reason = reason.strip()

    if not reason:
        raise ValueError(
            "La raison est vide."
        )

    # --------------------------------------------------------
    # RÈGLE DE SÉCURITÉ
    # --------------------------------------------------------

    # Si le modèle indique review=true,
    # la décision finale doit obligatoirement être REVIEW_HUMAN.

    if review:
        decision = "REVIEW_HUMAN"

    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "review": review,
        "decision": decision,
        "reason": reason
    }


# ============================================================
# ANALYSE D'UN ARTICLE
# ============================================================

def analyze_article(row):
    """
    Analyse un seul article.
    """

    title = str(row.get("title", "") or "").strip()
    content = str(row.get("content", "") or "").strip()

    initial_sentiment = str(
        row.get("initial_sentiment", "Neutral")
    ).strip()

    audit_sentiment = str(
        row.get("audit_sentiment", "Neutral")
    ).strip()

    if not title:
        raise ValueError("Article sans titre.")

    if not content:
        raise ValueError("Article sans contenu.")

    start = time.time()

    raw_response = call_ollama(
        title=title,
        content=content,
        initial_sentiment=initial_sentiment,
        audit_sentiment=audit_sentiment
    )

    elapsed = time.time() - start

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON invalide retourné par Ollama : {exc}"
        )

    result = validate_result(result)

    result["analysis_time_sec"] = round(elapsed, 2)

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("AUDIT FINAL DES 12 CAS SUSPECTS")
    print("=" * 80)

    # --------------------------------------------------------
    # Vérification fichier entrée
    # --------------------------------------------------------

    if not os.path.exists(INPUT_FILE):
        print()
        print(f"ERREUR : fichier introuvable : {INPUT_FILE}")
        print()
        return

    # --------------------------------------------------------
    # Chargement
    # --------------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    print()
    print(f"Articles chargés : {len(df)}")

    if len(df) == 0:
        print("ERREUR : aucun article.")
        return

    # --------------------------------------------------------
    # Vérification contenu
    # --------------------------------------------------------

    if "content" not in df.columns:
        print("ERREUR : colonne 'content' absente.")
        return

    missing_content = (
        df["content"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    print(f"Contenu disponible : {len(df) - missing_content}")
    print(f"Contenu absent     : {missing_content}")

    if missing_content > 0:
        print()
        print(
            "ERREUR : tous les cas doivent disposer du contenu complet."
        )
        print(
            "Aucune analyse partielle ne sera effectuée."
        )
        return

    # --------------------------------------------------------
    # Colonnes de sortie
    # --------------------------------------------------------

    results = []

    total = len(df)

    print()
    print("=" * 80)
    print("ANALYSE GPT-OSS")
    print("=" * 80)
    print()

    # --------------------------------------------------------
    # Analyse
    # --------------------------------------------------------

    for index, row in df.iterrows():

        number = index + 1

        title = str(row.get("title", "") or "").strip()

        print(
            f"[{number:02d}/{total:02d}] "
            f"{title[:100]}"
        )

        start = time.time()

        try:

            result = analyze_article(row)

            elapsed = time.time() - start

            print(
                f"    Sentiment : {result['sentiment']}"
            )

            print(
                f"    Confidence: {result['confidence']:.2f}"
            )

            print(
                f"    Review    : {result['review']}"
            )

            print(
                f"    Decision  : {result['decision']}"
            )

            print(
                f"    Temps     : {elapsed:.2f}s"
            )

            print(
                f"    Reason    : {result['reason'][:180]}"
            )

            row_result = row.to_dict()

            row_result["final_ai_sentiment"] = result["sentiment"]
            row_result["final_ai_confidence"] = result["confidence"]
            row_result["final_ai_review"] = result["review"]
            row_result["final_ai_decision"] = result["decision"]
            row_result["final_ai_reason"] = result["reason"]
            row_result["final_ai_time_sec"] = result["analysis_time_sec"]
            row_result["final_ai_model"] = MODEL_NAME
            row_result["final_ai_status"] = "SUCCESS"

        except Exception as exc:

            elapsed = time.time() - start

            print(
                f"    ERREUR : {type(exc).__name__}: {exc}"
            )

            row_result = row.to_dict()

            row_result["final_ai_sentiment"] = ""
            row_result["final_ai_confidence"] = ""
            row_result["final_ai_review"] = ""
            row_result["final_ai_decision"] = "ERROR"
            row_result["final_ai_reason"] = str(exc)
            row_result["final_ai_time_sec"] = round(
                elapsed,
                2
            )
            row_result["final_ai_model"] = MODEL_NAME
            row_result["final_ai_status"] = "ERROR"

        results.append(row_result)

        print()

    # --------------------------------------------------------
    # DataFrame final
    # --------------------------------------------------------

    output_df = pd.DataFrame(results)

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    output_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Statistiques
    # --------------------------------------------------------

    success_df = output_df[
        output_df["final_ai_status"] == "SUCCESS"
    ]

    error_df = output_df[
        output_df["final_ai_status"] == "ERROR"
    ]

    print("=" * 80)
    print("AUDIT FINAL TERMINÉ")
    print("=" * 80)

    print()
    print(f"Articles analysés     : {len(output_df)}")
    print(f"Analyses réussies     : {len(success_df)}")
    print(f"Erreurs techniques    : {len(error_df)}")

    print()
    print("SENTIMENT FINAL GPT-OSS")

    if len(success_df) > 0:

        sentiment_counts = (
            success_df["final_ai_sentiment"]
            .value_counts()
        )

        print(
            f"Positive              : "
            f"{sentiment_counts.get('Positive', 0)}"
        )

        print(
            f"Neutral               : "
            f"{sentiment_counts.get('Neutral', 0)}"
        )

        print(
            f"Negative              : "
            f"{sentiment_counts.get('Negative', 0)}"
        )

    print()
    print("DÉCISIONS")

    if len(success_df) > 0:

        decision_counts = (
            success_df["final_ai_decision"]
            .value_counts()
        )

        print(
            f"KEEP_INITIAL          : "
            f"{decision_counts.get('KEEP_INITIAL', 0)}"
        )

        print(
            f"KEEP_AUDIT            : "
            f"{decision_counts.get('KEEP_AUDIT', 0)}"
        )

        print(
            f"REVIEW_HUMAN          : "
            f"{decision_counts.get('REVIEW_HUMAN', 0)}"
        )

    print()
    print("REVIEW")

    if len(success_df) > 0:

        review_count = (
            success_df["final_ai_review"]
            .astype(str)
            .str.lower()
            .eq("true")
            .sum()
        )

        print(
            f"Review = True         : {review_count}"
        )

    print()
    print("Fichier créé :")
    print(
        os.path.abspath(OUTPUT_FILE)
    )

    print()
    print("SQLite                  : AUCUNE MODIFICATION")
    print("Pipeline principal      : NON EXÉCUTÉ")
    print("GPT-OSS                  : UTILISÉ UNIQUEMENT POUR L'AUDIT")

    print("=" * 80)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()