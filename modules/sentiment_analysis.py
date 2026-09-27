# modules/sentiment_analysis.py
# CGI MEDIA MONITOR - SEMANTIC SENTIMENT
# GPT-OSS 120B CLOUD
#
# IMPORTANT:
# - GPT-OSS is the ONLY sentiment model here.
# - API/model failures are NOT Neutral.
# - Failure => sentiment=None + review=True.
# - This module does not write SQLite.

import json
import re
from typing import Any, Dict, Optional

import requests

MODEL_NAME = "gpt-oss:120b-cloud"
OLLAMA_URL = "http://localhost:11434/api/chat"

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 180

MAX_TITLE_CHARS = 500
MAX_SUMMARY_CHARS = 1200
MAX_CONTENT_CHARS = 4000

SYSTEM_PROMPT = """
Tu es un analyste expert du sentiment des articles concernant CGI Maroc.

ENTITE CIBLE:
CGI Maroc = Compagnie Générale Immobilière du Maroc.

OBJECTIF:
Déterminer le sentiment exprimé par l'article envers CGI Maroc elle-même.

Classes obligatoires:
- Positive
- Neutral
- Negative

REGLES:
1. Ne fais JAMAIS une classification basée uniquement sur des mots-clés.
2. Analyse le contexte global.
3. Une nomination n'est pas automatiquement Positive.
4. Un projet immobilier ou un investissement n'est pas automatiquement Positive.
5. Un article général sur l'immobilier n'est pas automatiquement Positive.
6. Une affaire judiciaire, critique ou controverse visant directement CGI peut être Negative.
7. Une information factuelle sans orientation claire envers CGI = Neutral.
8. Le sentiment doit concerner CGI Maroc, pas seulement CDG ou une autre organisation.
9. Si le sentiment est ambigu, choisis Neutral et review=true.
10. Ne considère aucune ancienne valeur SQLite comme vérité terrain.

Réponds UNIQUEMENT avec:
{
  "sentiment": "Positive|Neutral|Negative",
  "score": 0.0,
  "confidence": 0.0,
  "margin": 0.0,
  "review": false,
  "reason": "explication courte"
}
"""

VALID_SENTIMENTS = {"Positive", "Neutral", "Negative"}


def _compact_text(value: Any, max_chars: int) -> str:
    if value is None:
        return ""

    text = re.sub(r"\s+", " ", str(value)).strip()

    if len(text) <= max_chars:
        return text

    first = int(max_chars * 0.7)
    last = max_chars - first
    return text[:first] + " ... " + text[-last:]


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None

    try:
        if isinstance(value, str):
            value = value.strip().replace("%", "")

        result = float(value)

        if result > 1:
            result /= 100.0

        return max(0.0, min(1.0, result))

    except (TypeError, ValueError):
        return None


def _extract_json(raw: str) -> Dict[str, Any]:
    if not raw:
        raise ValueError("Réponse vide du modèle.")

    text = raw.strip()

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    start = text.find("{")

    if start >= 0:
        depth = 0
        in_string = False
        escaped = False

        for i in range(start, len(text)):
            ch = text[i]

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1

                if depth == 0:
                    candidate = text[start:i + 1]

                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        repaired = re.sub(
                            r",\s*([}])",
                            r"\1",
                            candidate,
                        )
                        try:
                            obj = json.loads(repaired)
                            if isinstance(obj, dict):
                                return obj
                        except json.JSONDecodeError:
                            pass

                    break

    raise ValueError(
        "Impossible d'extraire un JSON valide de la réponse du modèle."
    )


def _validate_result(data: Dict[str, Any]) -> Dict[str, Any]:
    sentiment = str(data.get("sentiment", "")).strip().title()

    if sentiment not in VALID_SENTIMENTS:
        raise ValueError(
            f"Sentiment invalide retourné par le modèle: {sentiment!r}"
        )

    score = _safe_float(data.get("score"))
    confidence = _safe_float(data.get("confidence"))
    margin = _safe_float(data.get("margin"))

    review = data.get("review", False)

    if isinstance(review, str):
        review = review.strip().lower() in {
            "true", "1", "yes", "oui"
        }
    else:
        review = bool(review)

    # Low confidence / missing confidence should remain reviewable.
    if confidence is None or confidence < 0.70:
        review = True

    return {
        "sentiment": sentiment,
        "score": score,
        "confidence": confidence,
        "margin": margin,
        "review": review,
        "reason": str(
            data.get("reason") or "Aucune justification fournie."
        ).strip(),
        "model": MODEL_NAME,
        "device": "ollama-cloud",
        "error": None,
        "error_type": None,
        "classified": True,
    }


def _error_result(
    reason: str,
    error: Optional[str] = None,
    error_type: str = "model_error",
) -> Dict[str, Any]:
    """
    CRITICAL:
    A model/API error is NOT Neutral.
    """
    return {
        "sentiment": None,
        "score": None,
        "confidence": None,
        "margin": None,
        "review": True,
        "reason": reason,
        "model": MODEL_NAME,
        "device": "ollama-cloud",
        "error": error or reason,
        "error_type": error_type,
        "classified": False,
    }


def analyze_cgi_sentiment(
    title: str = "",
    summary: str = "",
    content: str = "",
) -> Dict[str, Any]:

    title_clean = _compact_text(title, MAX_TITLE_CHARS)
    summary_clean = _compact_text(summary, MAX_SUMMARY_CHARS)
    content_clean = _compact_text(content, MAX_CONTENT_CHARS)

    user_prompt = f"""
Analyse sémantiquement le sentiment envers CGI Maroc.

TITRE:
{title_clean or "(vide)"}

RESUME:
{summary_clean or "(vide)"}

CONTENU:
{content_clean or "(vide)"}

Retourne uniquement le JSON demandé.
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.strip(),
            },
            {
                "role": "user",
                "content": user_prompt.strip(),
            },
        ],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {
            "temperature": 0,
        },
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )

        response.raise_for_status()

        body = response.json()
        raw = body.get("message", {}).get("content", "")

        return _validate_result(_extract_json(raw))

    except requests.exceptions.Timeout as exc:
        print(f"[SENTIMENT][OLLAMA] Timeout : {exc}")
        return _error_result(
            "GPT-OSS indisponible: timeout.",
            str(exc),
            "timeout",
        )

    except requests.exceptions.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)

        print(f"[SENTIMENT][OLLAMA] Erreur HTTP/API : {exc}")

        if status == 429:
            return _error_result(
                "GPT-OSS indisponible: limite/quota Ollama Cloud atteint.",
                str(exc),
                "cloud_quota_429",
            )

        return _error_result(
            f"Erreur HTTP GPT-OSS: {exc}",
            str(exc),
            "http_error",
        )

    except requests.exceptions.RequestException as exc:
        print(f"[SENTIMENT][OLLAMA] Erreur réseau/API : {exc}")
        return _error_result(
            f"Erreur réseau GPT-OSS: {exc}",
            str(exc),
            "network_error",
        )

    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[SENTIMENT][OLLAMA] Erreur parsing : {exc}")
        return _error_result(
            f"Réponse GPT-OSS invalide: {exc}",
            str(exc),
            "parsing_error",
        )

    except Exception as exc:
        print(f"[SENTIMENT][OLLAMA] Erreur inattendue : {exc}")
        return _error_result(
            f"Erreur GPT-OSS: {exc}",
            str(exc),
            "model_error",
        )


if __name__ == "__main__":
    print("=" * 70)
    print("TEST SENTIMENT - GPT-OSS 120B CLOUD")
    print("=" * 70)

    result = analyze_cgi_sentiment(
        title="La CGI lance un nouveau projet immobilier à Casablanca",
        summary=(
            "La Compagnie Générale Immobilière du Maroc "
            "annonce un nouveau projet."
        ),
        content=(
            "La CGI Maroc poursuit son développement avec "
            "un nouveau projet immobilier à Casablanca."
        ),
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("=" * 70)
