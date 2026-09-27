from modules.aggregator import collect_articles
from modules.article_extractor import extract_article
from modules.ai_classifier import classifier, LABELS


# ==========================================================
# CONFIGURATION
# ==========================================================

GREY_MIN = 0.50
GREY_MAX = 0.65

# Mots présents dans les titres de la zone grise
# pour cibler les articles déjà identifiés par l'audit.
GREY_TITLE_PATTERNS = [
    "Mohammed Amin El Hajhouj",
    "Ce qu'il faut savoir sur la CGI",
    "meilleur promoteur immobilier marocain",
    "La CGI en bourse",
    "La CGI annonce la réouverture",
    "cdg développement",
    "Fès: Un nouvel investissement",
    "La CGI change de dimension",
    "La CGI investira 11 milliards",
    "demande de logements",
    "Compagnie Générale Immobilière",
]


# ==========================================================
# CLASSIFICATION
# ==========================================================

def classify_text(text: str):

    if not text:
        return 0.0, LABELS[1]

    text = text.strip()[:5000]

    result = classifier(
        text,
        candidate_labels=LABELS,
        multi_label=False,
    )

    predicted_label = result["labels"][0]
    score = float(result["scores"][0])

    return score, predicted_label


# ==========================================================
# CONSTRUCTION DU TEXTE
# ==========================================================

def build_title_content_text(article, content):

    title = (
        article.get("title")
        or ""
    ).strip()

    summary = (
        article.get("summary")
        or article.get("description")
        or ""
    ).strip()

    content = (
        content
        or ""
    ).strip()

    text = f"""
TITRE DE L'ARTICLE :
{title}

RÉSUMÉ :
{summary}

CONTENU DE L'ARTICLE :
{content[:4000]}
"""

    return text.strip()


# ==========================================================
# DÉTECTION DES ARTICLES CIBLES
# ==========================================================

def is_grey_zone_candidate(title):

    title_lower = title.lower()

    for pattern in GREY_TITLE_PATTERNS:

        if pattern.lower() in title_lower:
            return True

    return False


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=" * 70)
    print("AUDIT PERTINENCE : TITRE + RÉSUMÉ + CONTENU")
    print("=" * 70)

    print("\nRécupération des articles...")

    articles = collect_articles()

    print(
        f"Articles récupérés : {len(articles)}"
    )

    results = []

    for index, article in enumerate(
        articles,
        start=1
    ):

        title = (
            article.get("title")
            or ""
        ).strip()

        if not is_grey_zone_candidate(
            title
        ):
            continue

        print("\n")
        print("-" * 70)
        print(
            f"[ARTICLE {index}/{len(articles)}]"
        )
        print(
            f"Titre : {title}"
        )

        url = (
            article.get("url")
            or ""
        )

        # ==================================================
        # EXTRACTION
        # ==================================================

        content = extract_article(
            url
        )

        if not content:

            print(
                "❌ Extraction impossible"
            )

            continue

        # ==================================================
        # ANCIENNE MÉTHODE
        # ==================================================

        old_text = content[:3000]

        old_score, old_label = (
            classify_text(
                old_text
            )
        )

        old_relevant = (
            old_label == LABELS[0]
            and old_score >= 0.60
        )

        # ==================================================
        # NOUVELLE MÉTHODE
        # ==================================================

        new_text = build_title_content_text(
            article,
            content
        )

        new_score, new_label = (
            classify_text(
                new_text
            )
        )

        new_relevant_050 = (
            new_label == LABELS[0]
            and new_score >= 0.50
        )

        new_relevant_055 = (
            new_label == LABELS[0]
            and new_score >= 0.55
        )

        new_relevant_060 = (
            new_label == LABELS[0]
            and new_score >= 0.60
        )

        # ==================================================
        # AFFICHAGE
        # ==================================================

        print("\nANCIENNE MÉTHODE")
        print(
            f"Score : {old_score:.2%}"
        )
        print(
            f"Label : {old_label}"
        )
        print(
            f"Pertinent à 0.60 : "
            f"{'✅' if old_relevant else '❌'}"
        )

        print("\nNOUVELLE MÉTHODE")
        print(
            "Titre + résumé + contenu"
        )
        print(
            f"Score : {new_score:.2%}"
        )
        print(
            f"Label : {new_label}"
        )
        print(
            f"0.50 : "
            f"{'✅' if new_relevant_050 else '❌'}"
        )
        print(
            f"0.55 : "
            f"{'✅' if new_relevant_055 else '❌'}"
        )
        print(
            f"0.60 : "
            f"{'✅' if new_relevant_060 else '❌'}"
        )

        # ==================================================
        # VARIATION
        # ==================================================

        difference = (
            new_score - old_score
        )

        print(
            f"\nVariation du score : "
            f"{difference:+.2%}"
        )

        results.append({
            "title": title,
            "old_score": old_score,
            "old_label": old_label,
            "old_relevant": old_relevant,
            "new_score": new_score,
            "new_label": new_label,
            "new_050": new_relevant_050,
            "new_055": new_relevant_055,
            "new_060": new_relevant_060,
        })

    # ======================================================
    # RÉSUMÉ
    # ======================================================

    print("\n")
    print("=" * 70)
    print("RÉSUMÉ DE L'AUDIT")
    print("=" * 70)

    print(
        f"Articles examinés : {len(results)}"
    )

    old_count = sum(
        r["old_relevant"]
        for r in results
    )

    new_050_count = sum(
        r["new_050"]
        for r in results
    )

    new_055_count = sum(
        r["new_055"]
        for r in results
    )

    new_060_count = sum(
        r["new_060"]
        for r in results
    )

    print(
        f"\nAncienne méthode "
        f"(contenu seul / seuil 0.60) : "
        f"{old_count}"
    )

    print(
        f"Titre + contenu / seuil 0.50 : "
        f"{new_050_count}"
    )

    print(
        f"Titre + contenu / seuil 0.55 : "
        f"{new_055_count}"
    )

    print(
        f"Titre + contenu / seuil 0.60 : "
        f"{new_060_count}"
    )

    # ======================================================
    # ARTICLES QUI CHANGENT
    # ======================================================

    print("\n")
    print("=" * 70)
    print("ARTICLES DONT LE RÉSULTAT CHANGE")
    print("=" * 70)

    changed = [
        r
        for r in results
        if (
            r["old_relevant"]
            != r["new_060"]
        )
    ]

    if not changed:

        print(
            "Aucun changement à 0.60."
        )

    else:

        for r in changed:

            print(
                f"\n{r['title']}"
            )

            print(
                f"Ancien : "
                f"{r['old_score']:.2%} "
                f"-> "
                f"{'PERTINENT' if r['old_relevant'] else 'NON PERTINENT'}"
            )

            print(
                f"Nouveau : "
                f"{r['new_score']:.2%} "
                f"-> "
                f"{'PERTINENT' if r['new_060'] else 'NON PERTINENT'}"
            )

    print("\n")
    print("=" * 70)
    print("FIN DE L'AUDIT")
    print("=" * 70)

    print(
        "\n⚠️ SQLite : AUCUNE MODIFICATION"
    )


if __name__ == "__main__":
    main()