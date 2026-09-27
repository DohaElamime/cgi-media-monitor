from transformers import pipeline

# ==========================================================
# Chargement du modèle
# ==========================================================

classifier = pipeline(
    "zero-shot-classification",
    model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
)

LABELS = [
    "Article de presse ou actualité économique concernant la Compagnie Générale Immobilière (CGI Maroc)",
    "Page institutionnelle, page d'accueil, archive, formulaire, catégorie ou contenu sans intérêt pour une veille médiatique"
]

# Seuil de pertinence
RELEVANCE_THRESHOLD = 0.60


# ==========================================================
# Classification IA
# ==========================================================

def is_relevant_ai(text: str):
    """
    Détermine si un texte est un véritable article de presse
    concernant CGI Maroc.

    Retour :
        relevant (bool)
        score (float)
        predicted_label (str)
    """

    if not text:
        return False, 0.0, "Texte vide"

    # Limitation de taille
    text = text.strip()[:3000]

    try:

        result = classifier(
            text,
            candidate_labels=LABELS,
            multi_label=False
        )

        predicted_label = result["labels"][0]
        score = float(result["scores"][0])

        relevant = (
            predicted_label == LABELS[0]
            and score >= RELEVANCE_THRESHOLD
        )

        return relevant, score, predicted_label

    except Exception as e:
        print(f"Erreur IA : {e}")
        return False, 0.0, "Erreur"