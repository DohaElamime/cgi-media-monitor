from modules.aggregator import collect_articles
from modules.article_extractor import extract_article
from modules.ai_classifier import (
    classifier,
    LABELS,
    RELEVANCE_THRESHOLD,
)
from modules.pre_filter import is_article_candidate


def classify(text: str):
    """
    Classification brute sans appliquer le seuil.
    """

    if not text:
        return 0.0, LABELS[1]

    text = text.strip()[:3000]

    result = classifier(
        text,
        candidate_labels=LABELS,
        multi_label=False,
    )

    predicted_label = result["labels"][0]
    score = float(result["scores"][0])

    return score, predicted_label


def main():

    print("=" * 70)
    print("AUDIT DU FILTRE DE PERTINENCE")
    print("=" * 70)

    articles = collect_articles()

    print(
        f"\nArticles récupérés : {len(articles)}"
    )

    results = []

    for index, article in enumerate(
        articles,
        start=1
    ):

        print("\n" + "-" * 70)

        title = article.get(
            "title",
            ""
        )

        url = article.get(
            "url",
            ""
        )

        print(
            f"[{index}/{len(articles)}]"
        )

        print(
            f"Titre : {title}"
        )

        # --------------------------------------------------
        # Pré-filtre
        # --------------------------------------------------

        if not is_article_candidate(
            article
        ):

            print(
                "⚪ Rejeté par le pré-filtre"
            )

            continue

        # --------------------------------------------------
        # Extraction
        # --------------------------------------------------

        content = extract_article(
            url
        )

        if not content:

            print(
                "❌ Extraction impossible"
            )

            continue

        # --------------------------------------------------
        # Classification
        # --------------------------------------------------

        try:

            score, label = classify(
                content
            )

        except Exception as e:

            print(
                f"❌ Erreur IA : {e}"
            )

            continue

        relevant_at_050 = (
            label == LABELS[0]
            and score >= 0.50
        )

        relevant_at_055 = (
            label == LABELS[0]
            and score >= 0.55
        )

        relevant_at_060 = (
            label == LABELS[0]
            and score >= 0.60
        )

        relevant_at_065 = (
            label == LABELS[0]
            and score >= 0.65
        )

        print(
            f"Score : {score:.2%}"
        )

        print(
            f"Label : {label}"
        )

        print(
            f"0.50 : "
            f"{'✅' if relevant_at_050 else '❌'}"
        )

        print(
            f"0.55 : "
            f"{'✅' if relevant_at_055 else '❌'}"
        )

        print(
            f"0.60 : "
            f"{'✅' if relevant_at_060 else '❌'}"
        )

        print(
            f"0.65 : "
            f"{'✅' if relevant_at_065 else '❌'}"
        )

        results.append({
            "title": title,
            "url": url,
            "score": score,
            "label": label,
            "0.50": relevant_at_050,
            "0.55": relevant_at_055,
            "0.60": relevant_at_060,
            "0.65": relevant_at_065,
        })

    # ======================================================
    # STATISTIQUES
    # ======================================================

    print("\n")
    print("=" * 70)
    print("RÉSULTATS DE L'AUDIT")
    print("=" * 70)

    for threshold in [
        "0.50",
        "0.55",
        "0.60",
        "0.65",
    ]:

        count = sum(
            1
            for r in results
            if r[threshold]
        )

        print(
            f"Seuil {threshold} : "
            f"{count} articles pertinents"
        )

    # ======================================================
    # ARTICLES DANS LA ZONE GRISE
    # ======================================================

    print("\n")
    print("=" * 70)
    print("ZONE GRISE : 0.50 → 0.65")
    print("=" * 70)

    grey_zone = [
        r
        for r in results
        if (
            r["label"] == LABELS[0]
            and 0.50 <= r["score"] < 0.65
        )
    ]

    grey_zone.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    for r in grey_zone:

        print(
            f"\n{r['score']:.2%} | "
            f"{r['title']}"
        )

    # ======================================================
    # ARTICLES ACCEPTÉS À 0.60
    # ======================================================

    accepted = [
        r
        for r in results
        if r["0.60"]
    ]

    print("\n")
    print("=" * 70)
    print(
        f"ARTICLES ACCEPTÉS À 0.60 : "
        f"{len(accepted)}"
    )
    print("=" * 70)

    for r in accepted:

        print(
            f"{r['score']:.2%} | "
            f"{r['title']}"
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