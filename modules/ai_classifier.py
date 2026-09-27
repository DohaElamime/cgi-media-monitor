# modules/ai_classifier.py
# ============================================================
# CGI MEDIA MONITOR
# RELEVANCE CLASSIFIER — ENTITY-FIRST + SEMANTIC EMBEDDINGS
# ============================================================
#
# Objectif:
#   Déterminer si un article concerne réellement :
#   Compagnie Générale Immobilière (CGI) du Maroc.
#
# Principe:
#   1. Vérification d'entité
#   2. Exclusion des faux CGI
#   3. Embedding sémantique nomic-embed-text
#   4. Décision basée sur l'entité + similarité
#
# IMPORTANT:
#   - Pas de classification par mots-clés seule.
#   - CDG seul ne rend PAS un article pertinent.
#   - "CGI Canada", "CGI Inc", fiscalité, CGIS, etc. sont exclus.
#   - Une erreur technique retourne relevant=None.
#   - Ce module ne modifie jamais SQLite.
# ============================================================

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, List, Sequence, Tuple

import requests


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
MODEL_NAME = "nomic-embed-text:latest"

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 45

# Similarité minimale avec le contexte CGI Maroc.
SEMANTIC_THRESHOLD = 0.70

# Pour un article où le sigle CGI est ambigu, on exige un peu plus.
AMBIGUOUS_THRESHOLD = 0.73

# Marge très légère: l'embedding sert à confirmer la cohérence,
# mais l'identification de l'entité reste prioritaire.
MIN_MARGIN = -0.015


# ============================================================
# NETTOYAGE
# ============================================================

def _clean_text(value: Any, max_length: int = 12000) -> str:
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()

    return text[:max_length]


def _normalize(value: Any) -> str:
    text = _clean_text(value, 20000).lower()

    text = (
        text.replace("’", "'")
        .replace("œ", "oe")
        .replace("æ", "ae")
    )

    table = str.maketrans(
        "àáâäãåçèéêëìíîïñòóôöõùúûüýÿ",
        "aaaaaaceeeeiiiinooooouuuuyy",
    )

    return text.translate(table)


# ============================================================
# ENTITÉS
# ============================================================

DIRECT_CGI_PATTERNS: Sequence[str] = (
    "compagnie generale immobiliere du maroc",
    "compagnie generale immobiliere",
    "cgi maroc",
    "cgi immobilier",
    "cgi immobiliere",
    "cgi bourse de casablanca",
    "cgi rabat",
    "cgi casablanca",
    "cgi bouskoura",
    "cgi casa anfa",
)

# Ces expressions désignent explicitement d'autres entités.
OTHER_CGI_PATTERNS: Sequence[str] = (
    "cgi inc",
    "cgi group",
    "cgi canada",
    "cgi informatique",
    "cgi software",
    "cgi technology",
    "cgi technologies",
    "cgi senegal",
    "cgi cote d'ivoire",
    "cgi côte d'ivoire",
    "compagnie generale immobiliere du sahel",
)

TAX_PATTERNS: Sequence[str] = (
    "code general des impots",
    "code général des impôts",
    "article du cgi",
    "article 160 bis du cgi",
)

# Entités qui ne doivent pas être considérées comme CGI
# simplement parce qu'elles apparaissent dans un contexte immobilier.
OTHER_ORGANIZATIONS: Sequence[str] = (
    "cdg developpement",
    "cdg développement",
    "cdgdev",
    "al omrane",
    "tgcc",
)


def _contains_any(text: str, patterns: Sequence[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def _has_direct_cgi(text: str) -> bool:
    return _contains_any(text, DIRECT_CGI_PATTERNS)


def _has_other_cgi(text: str) -> bool:
    return _contains_any(text, OTHER_CGI_PATTERNS)


def _has_tax_cgi(text: str) -> bool:
    return _contains_any(text, TAX_PATTERNS)


def _cgi_mentions(text: str) -> int:
    return len(re.findall(r"\bcgi\b", text))


# ============================================================
# CONTEXTE D'ENTITÉ
# ============================================================

def _entity_analysis(
    title: str,
    summary: str,
    content: str,
    url: str,
) -> Dict[str, Any]:

    t = _normalize(title)
    s = _normalize(summary)
    c = _normalize(content)
    u = _normalize(url)

    title_summary = f"{t} {s}"
    all_text = f"{t} {s} {c} {u}"

    direct_title = _has_direct_cgi(t)
    direct_title_summary = _has_direct_cgi(title_summary)
    direct_anywhere = _has_direct_cgi(all_text)

    other_cgi = _has_other_cgi(all_text)
    tax_cgi = _has_tax_cgi(all_text)

    cgi_count = _cgi_mentions(all_text)

    # --------------------------------------------------------
    # Contextes marocain / immobilier.
    # --------------------------------------------------------

    context_patterns = (
        "maroc",
        "immobilier",
        "immobiliere",
        "promoteur",
        "promotion immobiliere",
        "rabat",
        "casablanca",
        "bouskoura",
        "casa anfa",
        "bourse de casablanca",
    )

    context_hits = [
        p for p in context_patterns
        if p in all_text
    ]

    return {
        "direct_title": direct_title,
        "direct_title_summary": direct_title_summary,
        "direct_anywhere": direct_anywhere,
        "other_cgi": other_cgi,
        "tax_cgi": tax_cgi,
        "cgi_count": cgi_count,
        "context_hits": context_hits,
        "normalized": all_text,
    }


# ============================================================
# EMBEDDINGS
# ============================================================

def _article_embedding_text(
    title: str,
    summary: str,
    content: str,
    url: str,
) -> str:

    # Le titre et résumé sont prioritaires.
    title = _clean_text(title, 1800)
    summary = _clean_text(summary, 3000)
    content = _clean_text(content, 6500)
    url = _clean_text(url, 1000)

    return (
        f"TITRE: {title}\n"
        f"RESUME: {summary}\n"
        f"CONTENU: {content}\n"
        f"URL: {url}"
    ).strip()


def _embed(inputs: Sequence[str]) -> List[List[float]]:

    response = requests.post(
        OLLAMA_EMBED_URL,
        json={
            "model": MODEL_NAME,
            "input": list(inputs),
        },
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )

    response.raise_for_status()

    body = response.json()
    embeddings = body.get("embeddings")

    if not isinstance(embeddings, list) or not embeddings:
        raise RuntimeError(
            "Ollama /api/embed n'a retourné aucun embedding."
        )

    vectors: List[List[float]] = []

    for vector in embeddings:
        if not isinstance(vector, list) or not vector:
            raise RuntimeError(
                "Embedding Ollama invalide."
            )

        vectors.append(
            [float(x) for x in vector]
        )

    return vectors


# ============================================================
# PROTOTYPES
# ============================================================

@lru_cache(maxsize=1)
def _load_prototypes() -> Dict[str, List[List[float]]]:

    positive = [
        (
            "Compagnie Générale Immobilière du Maroc, CGI Maroc, "
            "société immobilière marocaine, promoteur immobilier, "
            "projets immobiliers, activités, dirigeants, résultats, "
            "opérations et actualités concernant directement CGI Maroc."
        ),
        (
            "Article consacré à la Compagnie Générale Immobilière "
            "du Maroc et à ses projets, activités immobilières, "
            "gouvernance, finances, décisions ou opérations."
        ),
        (
            "Actualité de CGI Maroc : Compagnie Générale Immobilière, "
            "promotion immobilière, projets, résultats, dirigeants, "
            "Bourse, litiges ou activités de la société."
        ),
        (
            "Affaire, projet ou actualité concernant directement "
            "la Compagnie Générale Immobilière du Maroc, également "
            "appelée CGI Maroc."
        ),
    ]

    negative = [
        (
            "CGI Inc, CGI Group, CGI Canada, entreprise internationale "
            "de services informatiques et technologies."
        ),
        (
            "Code Général des Impôts, fiscalité, loi fiscale ou "
            "article fiscal utilisant l'abréviation CGI."
        ),
        (
            "CDG Développement ou Groupe CDG uniquement, sans sujet "
            "direct concernant la Compagnie Générale Immobilière."
        ),
        (
            "Article général sur le marché immobilier marocain "
            "sans implication réelle de CGI Maroc."
        ),
        (
            "Al Omrane, TGCC ou autre société immobilière marocaine "
            "sans implication directe de CGI Maroc."
        ),
        (
            "CGIS, Compagnie Générale Immobilière du Sahel ou "
            "autre organisation utilisant un nom similaire."
        ),
    ]

    vectors = _embed(
        positive + negative
    )

    split = len(positive)

    return {
        "positive": vectors[:split],
        "negative": vectors[split:],
    }


def _cosine(
    a: Sequence[float],
    b: Sequence[float],
) -> float:

    if len(a) != len(b):
        raise ValueError(
            "Dimensions d'embeddings incompatibles."
        )

    dot = sum(
        x * y
        for x, y in zip(a, b)
    )

    norm_a = sum(
        x * x
        for x in a
    ) ** 0.5

    norm_b = sum(
        y * y
        for y in b
    ) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def _max_similarity(
    vector: Sequence[float],
    prototypes: Sequence[Sequence[float]],
) -> float:

    return max(
        _cosine(vector, prototype)
        for prototype in prototypes
    )


# ============================================================
# CLASSIFICATION
# ============================================================

def is_relevant_ai(
    content: str,
    title: str = "",
    summary: str = "",
    url: str = "",
) -> Dict[str, Any]:

    title = _clean_text(title, 2000)
    summary = _clean_text(summary, 4000)
    content = _clean_text(content, 12000)
    url = _clean_text(url, 2000)

    if not any(
        (title, summary, content)
    ):
        return {
            "relevant": False,
            "confidence": 0.0,
            "positive_similarity": None,
            "negative_similarity": None,
            "entity_strength": 0.0,
            "margin": None,
            "reason": "Aucun contenu exploitable.",
            "model": MODEL_NAME,
            "device": "ollama-local",
            "error": None,
            "error_type": None,
        }

    entity = _entity_analysis(
        title,
        summary,
        content,
        url,
    )

    # --------------------------------------------------------
    # 1. EXCLUSIONS FORTES
    # --------------------------------------------------------

    if (
        entity["other_cgi"]
        and not entity["direct_anywhere"]
    ):
        return {
            "relevant": False,
            "confidence": 0.98,
            "positive_similarity": None,
            "negative_similarity": None,
            "entity_strength": 0.0,
            "margin": None,
            "reason": (
                "L'article concerne une autre organisation utilisant "
                "le sigle CGI, sans identification de CGI Maroc."
            ),
            "model": MODEL_NAME,
            "device": "ollama-local",
            "error": None,
            "error_type": None,
        }

    if (
        entity["tax_cgi"]
        and not entity["direct_anywhere"]
    ):
        return {
            "relevant": False,
            "confidence": 0.98,
            "positive_similarity": None,
            "negative_similarity": None,
            "entity_strength": 0.0,
            "margin": None,
            "reason": (
                "CGI désigne ici le Code Général des Impôts "
                "et non la Compagnie Générale Immobilière."
            ),
            "model": MODEL_NAME,
            "device": "ollama-local",
            "error": None,
            "error_type": None,
        }

    # --------------------------------------------------------
    # 2. EMBEDDING
    # --------------------------------------------------------

    try:
        article_vector = _embed(
            [
                _article_embedding_text(
                    title,
                    summary,
                    content,
                    url,
                )
            ]
        )[0]

        prototypes = _load_prototypes()

        positive_similarity = _max_similarity(
            article_vector,
            prototypes["positive"],
        )

        negative_similarity = _max_similarity(
            article_vector,
            prototypes["negative"],
        )

    except Exception as exc:

        return {
            "relevant": None,
            "confidence": None,
            "positive_similarity": None,
            "negative_similarity": None,
            "entity_strength": None,
            "margin": None,
            "reason": (
                "Erreur du modèle d'embeddings de pertinence."
            ),
            "model": MODEL_NAME,
            "device": "ollama-local",
            "error": str(exc),
            "error_type": "embedding_error",
        }

    margin = (
        positive_similarity
        - negative_similarity
    )

    # --------------------------------------------------------
    # 3. FORCE D'ENTITÉ
    # --------------------------------------------------------

    entity_strength = 0.0

    if entity["direct_title"]:
        entity_strength = 1.00

    elif entity["direct_title_summary"]:
        entity_strength = 0.96

    elif entity["direct_anywhere"]:
        entity_strength = 0.90

    elif entity["cgi_count"] > 0:
        entity_strength = 0.45

    # --------------------------------------------------------
    # 4. DECISION ENTITY-FIRST
    # --------------------------------------------------------

    # Cas A:
    # CGI Maroc explicitement identifié.
    explicit_cgi = entity["direct_anywhere"]

    # Cas B:
    # Sigle CGI ambigu mais contexte marocain/immobilier.
    contextual_cgi = (
        entity["cgi_count"] > 0
        and len(entity["context_hits"]) >= 2
    )

    # Cas C:
    # CDG uniquement sans CGI.
    cdg_only = (
        "cdg" in entity["normalized"]
        and entity["cgi_count"] == 0
        and not explicit_cgi
    )

    if cdg_only:
        relevant = False
        confidence = 0.95
        reason = (
            "L'article concerne CDG/CDG Développement mais "
            "ne fournit pas de preuve que CGI Maroc est réellement "
            "le sujet."
        )

    elif explicit_cgi:

        # Pour une CGI explicitement identifiée, la similarité
        # confirme la cohérence mais une marge minuscule n'annule
        # pas une identification d'entité forte.
        relevant = (
            positive_similarity >= SEMANTIC_THRESHOLD
            and margin >= MIN_MARGIN
        )

        if relevant:
            confidence = min(
                0.99,
                0.75
                + max(
                    0.0,
                    positive_similarity
                    - SEMANTIC_THRESHOLD,
                )
                + 0.05 * max(
                    0.0,
                    margin,
                ),
            )

            reason = (
                "CGI Maroc est explicitement identifiée dans "
                "l'article et la représentation sémantique est "
                "cohérente avec CGI Maroc."
            )
        else:
            confidence = max(
                0.0,
                min(
                    0.90,
                    positive_similarity,
                ),
            )

            reason = (
                "CGI Maroc est mentionnée, mais le contenu présente "
                "une cohérence sémantique insuffisante avec le contexte "
                "attendu de CGI Maroc."
            )

    elif contextual_cgi:

        relevant = (
            positive_similarity >= AMBIGUOUS_THRESHOLD
            and margin >= MIN_MARGIN
        )

        confidence = max(
            0.0,
            min(
                0.90,
                positive_similarity,
            ),
        )

        if relevant:
            reason = (
                "Le sigle CGI apparaît dans un contexte marocain/"
                "immobilier suffisamment cohérent avec CGI Maroc."
            )
        else:
            reason = (
                "Le sigle CGI apparaît, mais le contexte ne permet "
                "pas de confirmer suffisamment CGI Maroc."
            )

    else:

        relevant = False
        confidence = 0.95
        reason = (
            "Aucune identification suffisante de CGI Maroc. "
            "Une simple proximité avec l'immobilier, le Maroc "
            "ou CDG ne suffit pas."
        )

    return {
        "relevant": bool(relevant),
        "confidence": round(confidence, 4),
        "positive_similarity": round(
            positive_similarity,
            4,
        ),
        "negative_similarity": round(
            negative_similarity,
            4,
        ),
        "entity_strength": round(
            entity_strength,
            4,
        ),
        "margin": round(
            margin,
            4,
        ),
        "reason": reason,
        "model": MODEL_NAME,
        "device": "ollama-local",
        "error": None,
        "error_type": None,
    }


# ============================================================
# COMPATIBILITE PIPELINE
# ============================================================

def classify_relevance(
    content: str,
    title: str = "",
    summary: str = "",
    url: str = "",
) -> Dict[str, Any]:

    return is_relevant_ai(
        content=content,
        title=title,
        summary=summary,
        url=url,
    )


# ============================================================
# TESTS
# ============================================================

if __name__ == "__main__":

    tests = [

        {
            "name": "CGI Maroc immobilier",
            "title": (
                "CGI lance un nouveau projet immobilier "
                "à Casablanca"
            ),
            "summary": (
                "La Compagnie Générale Immobilière poursuit "
                "son activité au Maroc."
            ),
            "content": (
                "La Compagnie Générale Immobilière du Maroc "
                "(CGI) annonce un nouveau projet immobilier "
                "à Casablanca."
            ),
        },

        {
            "name": "CDG uniquement",
            "title": (
                "Un nouveau directeur général adjoint "
                "pour CDG Développement"
            ),
            "summary": (
                "CDG Développement annonce une nomination."
            ),
            "content": (
                "Le groupe CDG présente un nouveau responsable "
                "de CDG Développement. L'article porte sur "
                "la gouvernance de CDG Développement."
            ),
        },

        {
            "name": "CGI informatique",
            "title": (
                "CGI Canada lance une nouvelle solution "
                "informatique"
            ),
            "summary": (
                "CGI Inc présente une nouvelle solution "
                "technologique."
            ),
            "content": (
                "CGI Canada, groupe international de services "
                "informatiques, annonce une nouvelle solution."
            ),
        },

        {
            "name": "CGI affaire",
            "title": (
                "Affaire CGI: les auditions reportées "
                "au mois d'avril"
            ),
            "summary": (
                "Une affaire judiciaire concerne la CGI au Maroc."
            ),
            "content": (
                "L'affaire concerne la Compagnie Générale "
                "Immobilière du Maroc et plusieurs anciens "
                "responsables."
            ),
        },

        {
            "name": "Immobilier Maroc sans CGI",
            "title": (
                "Le marché immobilier marocain poursuit "
                "sa transformation"
            ),
            "summary": (
                "Les promoteurs immobiliers marocains "
                "adaptent leurs stratégies."
            ),
            "content": (
                "Al Omrane et plusieurs promoteurs analysent "
                "le marché immobilier marocain."
            ),
        },

        {
            "name": "CDG + CGI Maroc",
            "title": (
                "CDG et CGI annoncent une nouvelle opération"
            ),
            "summary": (
                "La Compagnie Générale Immobilière du Maroc "
                "est directement concernée."
            ),
            "content": (
                "CDG et la Compagnie Générale Immobilière du Maroc "
                "annoncent une opération immobilière à Rabat."
            ),
        },
    ]

    print("=" * 78)
    print("TEST CLASSIFIEUR DE PERTINENCE — CGI MEDIA MONITOR")
    print("=" * 78)

    for index, test in enumerate(tests, 1):

        result = is_relevant_ai(
            content=test["content"],
            title=test["title"],
            summary=test["summary"],
            url="",
        )

        print()
        print(
            f"[{index}] {test['name']}"
        )
        print(
            f"Relevant              : "
            f"{result.get('relevant')}"
        )
        print(
            f"Confidence            : "
            f"{result.get('confidence')}"
        )
        print(
            f"Positive similarity   : "
            f"{result.get('positive_similarity')}"
        )
        print(
            f"Negative similarity   : "
            f"{result.get('negative_similarity')}"
        )
        print(
            f"Entity strength       : "
            f"{result.get('entity_strength')}"
        )
        print(
            f"Margin                : "
            f"{result.get('margin')}"
        )
        print(
            f"Reason                : "
            f"{result.get('reason')}"
        )

        if result.get("error"):
            print(
                f"ERROR                 : "
                f"{result.get('error')}"
            )
