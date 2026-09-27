# ============================================================
# CGI MEDIA MONITOR
# AI RELEVANCE CLASSIFIER
# VERSION — ENTITY DISAMBIGUATION
# ============================================================

import json
import requests
import re

from typing import Dict, Any, Optional


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL_NAME = "gpt-oss:120b-cloud"

REQUEST_TIMEOUT = 180


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """

Tu es un classificateur expert de pertinence pour une veille média.

OBJECTIF PRINCIPAL
============================================================

La veille porte EXCLUSIVEMENT sur :

Compagnie Générale Immobilière du Maroc
(CGI Maroc).

CGI Maroc est une société immobilière marocaine liée au groupe CDG.

Ta tâche consiste à déterminer si l'article concerne réellement
cette société.

Il ne suffit JAMAIS de détecter simplement le mot "CGI".

Tu dois identifier l'organisation réellement concernée.


============================================================
ENTITÉS À NE PAS CONFONDRE
============================================================

Le sigle CGI peut désigner plusieurs organisations.

NE PAS confondre CGI Maroc avec :

1. CGI Inc.
2. CGI Canada
3. CGI Group
4. CGI Business Consulting
5. CGI informatique
6. CGI Maroc dans le domaine informatique
7. CGI Sénégal
8. CGIS
9. Code Général des Impôts
10. toute autre organisation utilisant le sigle CGI


============================================================
CGI INFORMATIQUE — EXCLUSION FORTE
============================================================

Si l'article concerne une entreprise informatique appelée CGI,
CGI Inc., CGI Canada ou CGI Group :

relevant = false

Exemples :

"CGI recrute des développeurs"

"CGI recrute des consultants IT"

"CGI lance une solution informatique"

"CGI recrute des ingénieurs logiciels"

"CGI Maroc recrute des consultants"

"CGI ouvre un centre de services informatiques"

Ces articles concernent CGI informatique et NON
la Compagnie Générale Immobilière du Maroc.


============================================================
CODE GÉNÉRAL DES IMPÔTS
============================================================

Si "CGI" signifie :

Code Général des Impôts

alors :

relevant = false


============================================================
AUTRES CGI
============================================================

Si CGI désigne une société ou organisation différente
de la Compagnie Générale Immobilière du Maroc :

relevant = false.


============================================================
CGI MAROC — CAS PERTINENTS
============================================================

Un article peut être pertinent lorsqu'il concerne clairement :

- Compagnie Générale Immobilière
- Compagnie Générale Immobilière du Maroc
- CGI Maroc
- CGI immobilier
- CGI immobilier Maroc
- CGI CDG
- activités immobilières de CGI Maroc
- projets immobiliers de CGI Maroc
- programmes immobiliers de CGI Maroc
- dirigeants de CGI Maroc
- nomination d'un dirigeant de CGI Maroc
- résultats financiers de CGI Maroc
- chiffre d'affaires de CGI Maroc
- résultats boursiers de CGI Maroc
- actions ou titres de CGI Maroc
- Bourse de Casablanca lorsque CGI Maroc est concernée
- CGI Rabat
- CGI Casablanca
- CGI Bouskoura
- CGI Casa Anfa
- projets résidentiels de CGI Maroc
- projets tertiaires de CGI Maroc
- opérations immobilières de CGI Maroc
- litiges ou affaires judiciaires concernant directement CGI Maroc


============================================================
IMPORTANT : PROJETS ET INVESTISSEMENTS
============================================================

NE PAS considérer automatiquement :

"projet immobilier"
"investissement"
"construction"
"programme immobilier"

comme étant positif.

Ces éléments servent uniquement à déterminer
si l'entité concernée est CGI Maroc.

La décision porte uniquement sur la PERTINENCE de l'article.


============================================================
MENTIONS SECONDAIRES
============================================================

Un article qui parle principalement d'une autre organisation
et qui mentionne simplement CGI ne doit PAS être considéré
comme pertinent.

Exemple :

"Al Omrane annonce un nouveau programme immobilier.
CGI est également citée parmi plusieurs acteurs."

Si CGI Maroc n'est pas réellement concernée par
l'information principale :

relevant = false.


============================================================
CDG
============================================================

La simple présence de :

CDG
CDG Développement
Caisse de Dépôt et de Gestion

ne suffit PAS.

Exemple :

"CDG annonce ses résultats"

=> relevant = false

Mais :

"CGI Maroc, filiale du groupe CDG, annonce ses résultats"

=> relevant = true.


============================================================
CONTEXTE GÉOGRAPHIQUE
============================================================

La présence de :

Maroc
Casablanca
Rabat
Bouskoura
Marrakech

ne suffit PAS.

Le contexte doit identifier CGI Maroc.


============================================================
AMBIGUÏTÉ
============================================================

Si tu ne peux pas déterminer avec suffisamment de certitude
que CGI désigne la Compagnie Générale Immobilière du Maroc :

relevant = false.


============================================================
RÈGLE DE PRIORITÉ
============================================================

Tu dois appliquer cet ordre :

1. Identifier l'organisation.
2. Vérifier s'il s'agit de CGI Maroc.
3. Vérifier qu'il ne s'agit pas de CGI informatique.
4. Vérifier qu'il ne s'agit pas du Code Général des Impôts.
5. Vérifier que CGI Maroc est réellement concernée.
6. Décider relevant.


============================================================
FORMAT DE SORTIE
============================================================

Retourne UNIQUEMENT un JSON valide.

Format :

{
    "relevant": true,
    "confidence": 0.95,
    "reason": "L'article concerne directement la Compagnie Générale Immobilière du Maroc."
}

ou :

{
    "relevant": false,
    "confidence": 0.98,
    "reason": "L'article concerne CGI Inc., une entreprise de services informatiques, et non CGI Maroc."
}

La confidence doit être comprise entre 0 et 1.

"""


# ============================================================
# JSON EXTRACTION
# ============================================================

def _extract_json(raw: str) -> Dict[str, Any]:

    if not raw:
        raise ValueError("Réponse du modèle vide")

    raw = raw.strip()

    # --------------------------------------------------------
    # JSON direct
    # --------------------------------------------------------

    try:
        return json.loads(raw)

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # JSON dans un bloc markdown
    # --------------------------------------------------------

    match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if match:

        return json.loads(
            match.group(1)
        )

    # --------------------------------------------------------
    # Première structure JSON trouvée
    # --------------------------------------------------------

    start = raw.find("{")
    end = raw.rfind("}")

    if start != -1 and end != -1 and end > start:

        candidate = raw[start:end + 1]

        return json.loads(candidate)

    raise ValueError(
        "Impossible d'extraire le JSON de la réponse Ollama"
    )


# ============================================================
# FLOAT VALIDATION
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:

    try:

        result = float(value)

        if result < 0:
            return 0.0

        if result > 1:
            return 1.0

        return result

    except (
        TypeError,
        ValueError,
    ):

        return default


# ============================================================
# RESULT VALIDATION
# ============================================================

def _validate_result(
    data: Dict[str, Any],
) -> Dict[str, Any]:

    if not isinstance(data, dict):

        raise ValueError(
            "La réponse du modèle n'est pas un objet JSON"
        )

    # --------------------------------------------------------
    # RELEVANT
    # --------------------------------------------------------

    relevant_value = data.get(
        "relevant",
        False,
    )

    if isinstance(
        relevant_value,
        bool,
    ):

        relevant = relevant_value

    elif isinstance(
        relevant_value,
        str,
    ):

        relevant = (
            relevant_value.strip().lower()
            in {
                "true",
                "1",
                "yes",
                "oui",
            }
        )

    else:

        relevant = bool(
            relevant_value
        )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence = _safe_float(
        data.get(
            "confidence",
            None,
        ),
        default=None,
    )

    # --------------------------------------------------------
    # REASON
    # --------------------------------------------------------

    reason = str(
        data.get(
            "reason",
            "",
        )
    ).strip()

    if not reason:

        reason = (
            "Aucune justification fournie "
            "par le modèle."
        )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    return {

        "relevant": relevant,

        "confidence": confidence,

        "reason": reason,

        "model": MODEL_NAME,

        "device": "ollama-cloud",

        "error": None,

        "error_type": None,

    }


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_relevance(
    title: str = "",
    summary: str = "",
    content: str = "",
    url: str = "",
) -> Dict[str, Any]:

    """
    Détermine si un article concerne CGI Maroc.

    Aucun accès SQLite.
    Aucune modification de données.
    """

    title = (
        title
        or ""
    ).strip()

    summary = (
        summary
        or ""
    ).strip()

    content = (
        content
        or ""
    ).strip()

    url = (
        url
        or ""
    ).strip()


    # ========================================================
    # PROMPT ARTICLE
    # ========================================================

    user_prompt = f"""

Analyse l'article suivant.

IDENTIFIE D'ABORD L'ORGANISATION CONCERNÉE.

La cible de cette veille est :

Compagnie Générale Immobilière du Maroc
(CGI Maroc).

==================================================
TITRE
==================================================

{title}


==================================================
RÉSUMÉ
==================================================

{summary}


==================================================
CONTENU
==================================================

{content}


==================================================
URL
==================================================

{url}


==================================================
QUESTION
==================================================

L'article concerne-t-il réellement :

Compagnie Générale Immobilière du Maroc
(CGI Maroc) ?

Si oui :

relevant = true

Si l'article concerne :

- CGI Inc.
- CGI Canada
- CGI Group
- CGI informatique
- CGI IT
- CGI logiciels
- CGI services informatiques
- CGI Sénégal
- une autre société CGI
- Code Général des Impôts
- une autre organisation

alors :

relevant = false.


==================================================
ATTENTION
==================================================

Ne considère jamais le mot "CGI" seul comme une preuve.

Ne considère jamais "Maroc" seul comme une preuve.

Ne considère jamais "immobilier" seul comme une preuve.

Ne considère jamais "CDG" seul comme une preuve.

Identifie l'entité et le sujet réel de l'article.


==================================================
DÉCISION
==================================================

Retourne uniquement :

{{
    "relevant": true ou false,
    "confidence": nombre entre 0 et 1,
    "reason": "justification courte"
}}

"""


    # ========================================================
    # PAYLOAD
    # ========================================================

    payload = {

        "model": MODEL_NAME,

        "messages": [

            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },

            {
                "role": "user",
                "content": user_prompt,
            },

        ],

        "stream": False,

        "format": "json",

        "think": False,

        "options": {

            "temperature": 0,

        },

    }


    # ========================================================
    # REQUEST
    # ========================================================

    try:

        response = requests.post(

            OLLAMA_URL,

            json=payload,

            timeout=REQUEST_TIMEOUT,

        )

        response.raise_for_status()


        # ----------------------------------------------------
        # RESPONSE JSON
        # ----------------------------------------------------

        data = response.json()


        # ----------------------------------------------------
        # MESSAGE
        # ----------------------------------------------------

        message = data.get(
            "message",
            {},
        )

        raw = message.get(
            "content",
            "",
        )


        # ----------------------------------------------------
        # EMPTY RESPONSE
        # ----------------------------------------------------

        if not raw:

            raise ValueError(
                "Réponse Ollama vide"
            )


        # ----------------------------------------------------
        # PARSE JSON
        # ----------------------------------------------------

        parsed = _extract_json(
            raw
        )


        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

        return _validate_result(
            parsed
        )


    # ========================================================
    # ERRORS
    # ========================================================

    except requests.exceptions.HTTPError as exc:

        status_code = None

        if exc.response is not None:

            status_code = (
                exc.response.status_code
            )

        return {

            "relevant": False,

            "confidence": 0.0,

            "reason": (
                "Erreur HTTP lors de "
                "l'appel au modèle."
            ),

            "model": MODEL_NAME,

            "device": "ollama-cloud",

            "error": str(exc),

            "error_type": (
                f"http_{status_code}"
                if status_code
                else "http_error"
            ),

        }


    except requests.exceptions.Timeout as exc:

        return {

            "relevant": False,

            "confidence": 0.0,

            "reason": (
                "Timeout lors de "
                "l'analyse IA."
            ),

            "model": MODEL_NAME,

            "device": "ollama-cloud",

            "error": str(exc),

            "error_type": "timeout",

        }


    except requests.exceptions.RequestException as exc:

        return {

            "relevant": False,

            "confidence": 0.0,

            "reason": (
                "Erreur de communication "
                "avec Ollama."
            ),

            "model": MODEL_NAME,

            "device": "ollama-cloud",

            "error": str(exc),

            "error_type": "connection_error",

        }


    except json.JSONDecodeError as exc:

        return {

            "relevant": False,

            "confidence": 0.0,

            "reason": (
                "Réponse du modèle "
                "non interprétable."
            ),

            "model": MODEL_NAME,

            "device": "ollama-cloud",

            "error": str(exc),

            "error_type": "invalid_json",

        }


    except Exception as exc:

        return {

            "relevant": False,

            "confidence": 0.0,

            "reason": (
                "Erreur pendant "
                "la classification."
            ),

            "model": MODEL_NAME,

            "device": "ollama-cloud",

            "error": str(exc),

            "error_type": "classification_error",

        }


# ============================================================
# ALIAS DE COMPATIBILITÉ
# ============================================================

def is_relevant_ai(
    title: str = "",
    summary: str = "",
    content: str = "",
    url: str = "",
) -> Dict[str, Any]:

    """
    Alias utilisé par le pipeline dry-run.
    """

    return classify_relevance(

        title=title,

        summary=summary,

        content=content,

        url=url,

    )


def classify_article(
    title: str = "",
    summary: str = "",
    content: str = "",
    url: str = "",
) -> Dict[str, Any]:

    """
    Alias de compatibilité.
    """

    return classify_relevance(

        title=title,

        summary=summary,

        content=content,

        url=url,

    )


# ============================================================
# TEST DIRECT
# ============================================================

if __name__ == "__main__":

    tests = [

        {

            "name": "CGI immobilier",

            "title": (
                "CGI lance un nouveau projet "
                "immobilier à Casablanca"
            ),

            "summary": (
                "La Compagnie Générale Immobilière "
                "du Maroc développe un nouveau projet."
            ),

        },

        {

            "name": "CGI informatique",

            "title": (
                "CGI recrute des ingénieurs "
                "informatiques au Maroc"
            ),

            "summary": (
                "La société internationale CGI "
                "renforce ses équipes IT."
            ),

        },

        {

            "name": "Code Général des Impôts",

            "title": (
                "Le CGI prévoit une nouvelle "
                "mesure fiscale"
            ),

            "summary": (
                "Le Code Général des Impôts "
                "fait l'objet d'une réforme."
            ),

        },

        {

            "name": "CDG uniquement",

            "title": (
                "CDG annonce ses résultats"
            ),

            "summary": (
                "La Caisse de Dépôt et de Gestion "
                "présente ses résultats."
            ),

        },

        {

            "name": "CGI affaire",

            "title": (
                "L'affaire CGI à Al Hoceima"
            ),

            "summary": (
                "Une affaire judiciaire concerne "
                "la Compagnie Générale Immobilière."
            ),

        },

    ]


    print()
    print("=" * 70)
    print("TEST CLASSIFICATEUR CGI")
    print("=" * 70)


    for test in tests:

        result = classify_relevance(

            title=test["title"],

            summary=test["summary"],

            content="",

            url="",

        )


        print()
        print(
            f"TEST : {test['name']}"
        )

        print(
            f"Relevant   : "
            f"{result.get('relevant')}"
        )

        print(
            f"Confidence : "
            f"{result.get('confidence')}"
        )

        print(
            f"Reason     : "
            f"{result.get('reason')}"
        )

        print(
            f"Error      : "
            f"{result.get('error')}"
        )

        print(
            f"Error type : "
            f"{result.get('error_type')}"
        )

    print()
    print("=" * 70)
    print("FIN DES TESTS")
    print("=" * 70)